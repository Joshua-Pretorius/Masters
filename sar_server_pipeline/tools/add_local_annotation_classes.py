"""Add reef/rain to saved annotation forms without changing feature data.

Run using QGIS Python. Only active batch.qgz, scene.qgz and task.qgz projects
are migrated; backups are excluded. Saves are staged and verified first.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer,
                      QgsEditorWidgetSetup, QgsCategorizedSymbolRenderer,
                      QgsRendererCategory, QgsSymbol)
from qgis.PyQt.QtGui import QColor

ADDITIONS = {'reef': '#00a896', 'rain': '#377eb8'}

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def choices(layer):
    config = layer.editorWidgetSetup(layer.fields().indexOf('Class')).config()
    values = config.get('map', [])
    return dict(values) if isinstance(values, dict) else {k: v for entry in values for k, v in entry.items()}

def source_key(layer):
    source = layer.source()
    # QGIS assigns a new transient UID whenever a memory layer is reopened.
    return re.sub(r'&uid=\{[^}]+\}', '', source) if layer.providerType() == 'memory' else source

def memory_contents(layer):
    return [(f.id(), repr(f.attributes()), bytes(f.geometry().asWkb())) for f in layer.getFeatures()]

def migrate(path):
    original_hash = digest(path)
    project = QgsProject()
    if not project.read(str(path)):
        raise RuntimeError('Cannot read project')
    root = project.layerTreeRoot()
    original = {key: (source_key(l), l.isValid(), root.findLayer(key).itemVisibilityChecked() if root.findLayer(key) else None)
                for key, l in project.mapLayers().items()}
    memory = {key: memory_contents(l) for key, l in project.mapLayers().items() if isinstance(l, QgsVectorLayer) and l.providerType() == 'memory'}
    updated = []
    data_hashes = {}
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        if 'layername=annotations' not in layer.source().lower() and not ('annotations' in layer.name().lower() and layer.fields().indexOf('Class') >= 0):
            continue
        if not layer.isValid():
            raise RuntimeError('Invalid annotation layer: ' + layer.source())
        source = Path(layer.source().split('|')[0])
        if not source.is_file():
            raise RuntimeError('Annotation source is not a local file')
        data_hashes[str(source)] = digest(source)
        index = layer.fields().indexOf('Class')
        old = layer.editorWidgetSetup(index)
        if old.type() != 'ValueMap':
            raise RuntimeError('Unexpected Class widget: ' + old.type())
        values = choices(layer)
        renderer = layer.renderer()
        if not isinstance(renderer, QgsCategorizedSymbolRenderer) or renderer.classAttribute() != 'Class':
            raise RuntimeError('Unexpected annotation renderer')
        existing = {c.value() for c in renderer.categories()}
        if set(ADDITIONS) <= set(values.values()) and set(ADDITIONS) <= existing:
            continue
        for name in ADDITIONS:
            if name not in values.values():
                values[name] = name
        config = old.config(); config['map'] = [{k: v} for k, v in values.items()]
        layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup('ValueMap', config))
        renderer = renderer.clone()
        for name, colour in ADDITIONS.items():
            if name in existing:
                continue
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            color = QColor(colour); color.setAlpha(90); symbol.setColor(color)
            renderer.addCategory(QgsRendererCategory(name, symbol, name))
        layer.setRenderer(renderer)
        updated.append(layer.id())
    if not updated:
        project.clear()
        return {'project': str(path), 'status': 'unchanged', 'layers': 0}
    staged = path.with_name(path.stem + '.classes_staged.qgz')
    if not project.write(str(staged)):
        raise RuntimeError('Cannot stage project')
    verify = QgsProject()
    assert verify.read(str(staged))
    for key, (source, valid, checked) in original.items():
        layer = verify.mapLayer(key)
        assert layer and source_key(layer) == source, 'Original source changed: ' + key
        assert not valid or layer.isValid()
        if checked is not None:
            assert verify.layerTreeRoot().findLayer(key).itemVisibilityChecked() == checked
    for key, contents in memory.items():
        assert memory_contents(verify.mapLayer(key)) == contents, 'Memory layer contents changed'
    for key in updated:
        layer = verify.mapLayer(key)
        assert set(ADDITIONS) <= set(choices(layer).values())
        assert set(ADDITIONS) <= {c.value() for c in layer.renderer().categories()}
    for source, before in data_hashes.items():
        assert digest(Path(source)) == before, 'Annotation data changed during migration'
    assert digest(path) == original_hash, 'Project changed concurrently'
    backup = path.with_name(path.stem + '.before_reef_rain_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.qgz')
    shutil.copy2(path, backup)
    os.replace(staged, path)
    result = {'project': str(path), 'status': 'updated', 'layers': len(updated),
              'backup': str(backup), 'annotation_data_unchanged': data_hashes,
              'original_sources_visibility_preserved': True}
    verify.clear(); project.clear()
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--retry-errors', action='store_true')
    args = parser.parse_args()
    app = QgsApplication([], False); app.initQgis()
    paths = sorted(p for p in args.root.rglob('*.qgz') if p.name in ('batch.qgz', 'scene.qgz', 'task.qgz') and not any('backup' in part.lower() for part in p.parts))
    results = []
    if args.retry_errors:
        previous = json.loads(args.report.read_text())
        paths = [Path(r['project']) for r in previous if r['status'] == 'error']
        results = [r for r in previous if r['status'] != 'error']
    args.report.parent.mkdir(parents=True, exist_ok=True)
    for path in paths:
        try:
            result = migrate(path)
        except Exception as exc:
            result = {'project': str(path), 'status': 'error', 'error': repr(exc)}
        results.append(result)
        args.report.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(result['status'], result.get('layers'), path, result.get('error', ''), flush=True)
    return int(any(r['status'] == 'error' for r in results))

if __name__ == '__main__':
    raise SystemExit(main())
