"""Copy FDI rasters into the supplied digitising batch and add QGIS layers."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import uuid
from zipfile import ZipFile

_rasterio_package = Path(importlib.util.find_spec("rasterio").origin).parent
os.environ["PROJ_LIB"] = str(_rasterio_package / "proj_data")

from lxml import etree as ET
import rasterio
from rasterio.warp import transform_bounds


PROJECT = Path(r"D:\Joshua\golden_marida_16pdc_2018\digitising_batches\golden_marida_16pdc_2018\batch.qgz")
SOURCE = Path(r"D:\Masters\MARIDA\downloads\16PDC\2018-10-24\copernicus_products\fdi")
TARGET = PROJECT.parent / "optical_fdi"
STYLE_PROJECT = Path(r"D:\Masters\Writing\DataCreation.qgz")
GROUP_NAME = "Sentinel-2 FDI | 2018-10-24 | Copernicus SAFE"


def text_element(parent: ET._Element, name: str, value: str) -> None:
    element = parent.find(name)
    if element is None:
        element = ET.SubElement(parent, name)
    element.text = value


def set_extent(parent: ET._Element, name: str, bounds) -> None:
    extent = parent.find(name)
    if extent is None:
        extent = ET.SubElement(parent, name)
    for key, value in zip(("xmin", "ymin", "xmax", "ymax"), bounds):
        text_element(extent, key, f"{value:.12f}")


def color_source(color: str) -> str:
    red, green, blue = (int(color[i:i+2], 16) for i in (1, 3, 5))
    return f"{red},{green},{blue},255,rgb:{red/255:.17g},{green/255:.17g},{blue/255:.17g},1"


def style_renderer(renderer: ET._Element, low: float, high: float) -> None:
    # Stretch around the water range; bright land can otherwise dominate a
    # whole-tile percentile and conceal small marine FDI differences.
    low = max(min(low, -0.005), -0.05)
    high = min(max(high, 0.005), 0.10)
    renderer.set("classificationMin", str(low))
    renderer.set("classificationMax", str(high))
    shader = renderer.find("./rastershader/colorrampshader")
    shader.set("minimumValue", str(low))
    shader.set("maximumValue", str(high))
    shader.set("classificationMode", "1")
    ramp = shader.find("colorramp")
    options = {option.get("name"): option for option in ramp.findall("./Option/Option")}
    options["color1"].set("value", color_source("#15315b"))
    options["color2"].set("value", color_source("#b71930"))
    stops = [
        (0.25, "#4f8dae"),
        (0.5, "#f6f5ea"),
        (0.75, "#f5a340"),
    ]
    options["stops"].set(
        "value", ":".join(f"{fraction};{color_source(color)};rgb;ccw" for fraction, color in stops)
    )
    for item in shader.findall("item"):
        shader.remove(item)
    for value, color, label in (
        (low, "#15315b", f"≤ {low:.4f}"),
        (low / 2, "#4f8dae", f"{low/2:.4f}"),
        (0.0, "#f6f5ea", "0"),
        (high / 2, "#f5a340", f"{high/2:.4f}"),
        (high, "#b71930", f"≥ {high:.4f}"),
    ):
        item = ET.Element("item", color=color, alpha="255", value=str(value), label=label)
        legend = shader.find("rampLegendSettings")
        shader.insert(shader.index(legend), item)


def main() -> None:
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if len(manifest) != 3:
        raise ValueError("Expected three FDI products")
    with ZipFile(PROJECT) as z:
        qgs_name = next(name for name in z.namelist() if name.endswith(".qgs"))
        original = z.read(qgs_name)
    root = ET.fromstring(original)
    tree = root.find("layer-tree-group")
    if any(group.get("name") == GROUP_NAME for group in tree.findall("layer-tree-group")):
        raise ValueError("FDI group already exists; refusing duplicate edit")
    maplayers = root.find("projectlayers")
    template = next(layer for layer in maplayers.findall("maplayer") if layer.get("type") == "raster")
    tree_template = next(layer for layer in tree.iter("layer-tree-layer") if layer.get("id") == template.findtext("id"))

    with ZipFile(STYLE_PROJECT) as z:
        style_root = ET.fromstring(z.read(next(name for name in z.namelist() if name.endswith(".qgs"))))
    style_layer = next(
        layer for layer in style_root.findall("./projectlayers/maplayer")
        if layer.get("type") == "raster"
        and layer.findtext("./srs/spatialrefsys/authid") == "EPSG:32616"
        and layer.find("./pipe/rasterrenderer") is not None
        and layer.find("./pipe/rasterrenderer").get("type") == "singlebandpseudocolor"
    )
    srs_template = style_layer.find("srs")
    renderer_template = style_layer.find("./pipe/rasterrenderer")

    group = ET.Element("layer-tree-group", groupLayer="", checked="Qt::Checked", name=GROUP_NAME, expanded="1")
    group.append(copy.deepcopy(tree.find("layer-tree-group/customproperties")))
    added = []
    for item in manifest:
        source = Path(item["fdi"])
        if not source.is_file():
            raise FileNotFoundError(source)
        target = TARGET / source.name
        with rasterio.open(source) as raster:
            if raster.crs is None or raster.nodata != -9999.0:
                raise ValueError(f"FDI raster lacks expected CRS/nodata: {source}")
            bounds = raster.bounds
            wgs84 = transform_bounds(raster.crs, "EPSG:4326", *bounds, densify_pts=21)
        tile = item["product"].split("_T")[1][:5]
        level = item["level"]
        name = f"FDI {tile} | {level} {'BOA' if level == 'L2A' else 'TOA'} | 2018-10-24 16:13 UTC"
        layer_id = f"FDI_{tile}_{level}_{uuid.uuid4().hex}"
        relative = "./optical_fdi/" + source.name
        layer = copy.deepcopy(template)
        text_element(layer, "id", layer_id)
        text_element(layer, "layername", name)
        text_element(layer, "datasource", relative)
        text_element(layer, "provider", "gdal")
        set_extent(layer, "extent", bounds)
        set_extent(layer, "wgs84extent", wgs84)
        old_srs = layer.find("srs")
        layer.replace(old_srs, copy.deepcopy(srs_template))
        old_renderer = layer.find("./pipe/rasterrenderer")
        new_renderer = copy.deepcopy(renderer_template)
        low, _, high = item["sample_p02_p50_p98"]
        style_renderer(new_renderer, low, high)
        old_renderer.getparent().replace(old_renderer, new_renderer)
        # The copied layer came from SAR; avoid carrying its descriptive metadata.
        for field in ("resourceMetadata", "keywordList"):
            element = layer.find(field)
            if element is not None:
                layer.remove(element)
        maplayers.append(layer)

        node = copy.deepcopy(tree_template)
        node.set("id", layer_id)
        node.set("name", name)
        node.set("source", relative)
        node.set("checked", "Qt::Checked" if tile == "16PDC" else "Qt::Unchecked")
        group.append(node)
        added.append((source, target, layer_id, name))

    tree.insert(1, group)
    custom_order = tree.find("custom-order")
    for _, _, layer_id, _ in added:
        ET.SubElement(custom_order, "item").text = layer_id
    layerorder = root.find("layerorder")
    for _, _, layer_id, _ in reversed(added):
        layerorder.insert(0, ET.Element("layer", id=layer_id))

    # Complete all checks before mutating the user's batch directory.
    ids = [layer.findtext("id") for layer in maplayers.findall("maplayer")]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate QGIS layer ID")
    TARGET.mkdir(parents=True, exist_ok=True)
    for source, target, _, _ in added:
        if target.exists() and target.stat().st_size != source.stat().st_size:
            raise ValueError(f"Different existing target: {target}")
        if not target.exists():
            shutil.copy2(source, target)
        with rasterio.open(target) as raster:
            if raster.crs is None or raster.count != 1:
                raise ValueError(f"Invalid copied FDI raster: {target}")

    backup = PROJECT.with_name(
        f"batch.before_fdi_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.qgz"
    )
    shutil.copy2(PROJECT, backup)
    temp = PROJECT.with_suffix(".fdi_partial.qgz")
    new_qgs = ET.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    with ZipFile(PROJECT) as original_zip, ZipFile(temp, "w") as output_zip:
        for entry in original_zip.infolist():
            data = new_qgs if entry.filename == qgs_name else original_zip.read(entry.filename)
            output_zip.writestr(entry, data)
    with ZipFile(temp) as check_zip:
        checked = ET.fromstring(check_zip.read(qgs_name))
        for _, target, layer_id, _ in added:
            assert target.is_file()
            assert checked.find(f"./projectlayers/maplayer[id='{layer_id}']") is not None
    os.replace(temp, PROJECT)
    print(f"PROJECT {PROJECT}")
    print(f"BACKUP {backup}")
    for _, target, _, name in added:
        print(f"LAYER {name} -> {target}")


if __name__ == "__main__":
    main()
