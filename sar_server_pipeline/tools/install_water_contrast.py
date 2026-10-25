"""Install completed four-band contrasts into existing desktop QGIS projects.

Run with QGIS Python: install_water_contrast.py --inventory inventory.json
    --results results.json --report project_checks.json
Only complete projects are migrated; missing inputs are explicitly reported.
Old derived rasters are retained on disk so project backups remain usable.
"""

from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from digitising.water_contrast_style import add_qgis_layers, VERSION, LABELS

OLD_GROUPS = {
    "Area | filtered, patch and VV-VH views v1",
    "Signed water-relative SAR | fixed v1",
}


def key(path):
    return os.path.normcase(str(Path(path).resolve()))


def migrate(path, results):
    from qgis.core import QgsProject

    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    project = QgsProject()
    if not project.read(str(path)):
        raise RuntimeError(f"Cannot read {path}")
    root = project.layerTreeRoot()
    groups = []
    unavailable = []
    for group in root.findGroups(True):
        if group.name() != "SAR rasters":
            continue
        source = next(
            (
                n.layer().source().split("|")[0]
                for n in group.findLayers()
                if n.layer()
                and n.layer().source().split("|")[0].endswith("_slc_native_vv.tif")
            ),
            None,
        )
        if source is None:
            continue
        result = results.get(key(source))
        if result is None:
            project.clear()
            return dict(
                project=str(path),
                status="pending",
                reason="Scene calculation not complete",
            )
        if result.get("status") != "complete":
            unavailable.append(
                dict(
                    source=source,
                    status=result.get("status"),
                    detail=result.get("error", result.get("missing")),
                )
            )
        else:
            groups.append((group, result))
    if not groups:
        project.clear()
        return dict(project=str(path), status="unavailable", scenes=unavailable)
    # Repeated installation is a no-op when the same four sources and bands exist.
    old_groups = [g for g in root.findGroups(True) if g.name() in OLD_GROUPS]

    def matches(group, result):
        existing = [
            n.layer()
            for n in group.findLayers()
            if n.layer()
            and n.layer().customProperty("water_contrast/version") == VERSION
        ]
        return (
            len(existing) == 4
            and {l.name() for l in existing} == set(LABELS)
            and all(key(l.source()) == key(result["path"]) for l in existing)
            and sorted(l.renderer().inputBand() for l in existing) == [1, 2, 3, 4]
        )

    if not old_groups and all(matches(g, r) for g, r in groups):
        project.clear()
        return dict(
            project=str(path),
            status="already_installed",
            groups=len(groups),
            unavailable=unavailable,
        )
    removed = set()
    for group in old_groups:
        removed.update(n.layerId() for n in group.findLayers())
    for group, _ in groups:
        removed.update(
            n.layerId()
            for n in group.findLayers()
            if n.layer()
            and n.layer().customProperty("water_contrast/version") == VERSION
        )
    original = {
        k: dict(source=l.source(), valid=l.isValid())
        for k, l in project.mapLayers().items()
        if k not in removed
    }
    checked = {
        n.layerId(): n.itemVisibilityChecked()
        for n in root.findLayers()
        if n.layerId() not in removed
    }
    old_order = [l for l in root.layerOrder() if l.id() not in removed]
    for layer_id in removed:
        project.removeMapLayer(layer_id)
    for group in old_groups:
        if group.parent():
            group.parent().removeChildNode(group)
    new = []
    insertion = {}
    for group, result in groups:
        old_first = next((n.layerId() for n in group.findLayers() if n.layer()), None)
        layers = add_qgis_layers(project, group, result)
        new.extend(layers)
        if old_first:
            insertion[old_first] = layers
    order = []
    for layer in old_order:
        order.extend(insertion.get(layer.id(), []))
        order.append(layer)
    order.extend(l for l in new if l not in order)
    root.setHasCustomLayerOrder(True)
    root.setCustomLayerOrder(order)
    staged = path.with_name(path.stem + ".water_contrast_staged.qgz")
    if not project.write(str(staged)):
        raise RuntimeError("Cannot write staged project")
    verification = QgsProject()
    if not verification.read(str(staged)):
        raise RuntimeError("Cannot reopen staged project")
    for layer in new:
        if not verification.mapLayer(layer.id()).isValid():
            raise RuntimeError("New raster invalid after reopening")
    for layer_id, info in original.items():
        layer = verification.mapLayer(layer_id)
        if layer is None or layer.source() != info["source"]:
            raise RuntimeError("Original layer source changed")
        if info["valid"] and not layer.isValid():
            raise RuntimeError("Previously valid layer became invalid")
        if (
            verification.layerTreeRoot().findLayer(layer_id).itemVisibilityChecked()
            != checked[layer_id]
        ):
            raise RuntimeError("Original layer visibility changed")
    for g in verification.layerTreeRoot().findGroups(True):
        if g.name() in OLD_GROUPS:
            raise RuntimeError("Legacy group remains")
    if hashlib.sha256(path.read_bytes()).hexdigest() != original_hash:
        raise RuntimeError("Project changed concurrently; refusing overwrite")
    backup = path.with_name(
        path.stem
        + ".before_water_contrast_"
        + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".qgz"
    )
    shutil.copy2(path, backup)
    os.replace(staged, path)
    result = dict(
        project=str(path),
        status="updated",
        backup=str(backup),
        added_layers=len(new),
        removed_layers=len(removed),
        groups=len(groups),
        unavailable=unavailable,
        original_sources_and_visibility_preserved=True,
        new_layers_valid=True,
    )
    verification.clear()
    project.clear()
    return result


def main():
    from qgis.core import QgsApplication

    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    app = QgsApplication([], False)
    app.initQgis()
    results = {key(r["source"]): r for r in json.loads(args.results.read_text())}
    report = []
    for item in json.loads(args.inventory.read_text()):
        try:
            result = migrate(Path(item["project"]), results)
        except Exception as exc:
            result = dict(project=item["project"], status="error", error=str(exc))
        print(json.dumps(result), flush=True)
        report.append(result)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
