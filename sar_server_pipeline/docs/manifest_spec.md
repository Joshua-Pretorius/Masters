# Manifest Spec

The server pipeline consumes one manifest file per run. `schema_version: 1` is the stable v1 contract.

Supported top-level fields:

```yaml
schema_version: 1
run_id: run-001
dataset_mode: sa
targets:
  - MERIA_SA_001:after
inputs:
  match_csv: /data/raw/matches.csv
  points_csv: /data/raw/points.csv
  raw_slc_root: /data/raw/slc
  shapefiles_root: /data/shapefiles
  biophysical_root: /data/biophysical
outputs:
  processed_root: /data/processed
  patches_root: /data/patches
  stacks_root: /data/stacks
  logs_root: /data/logs
  manifests_root: /data/manifests
stages:
  slc_process:
    enabled: true
    overwrite: false
    # Optional when SNAP_GPT is provided by the container environment.
    gpt: /usr/local/snap/bin/gpt
  patch_extract:
    enabled: true
    overwrite: false
  patch_stack:
    enabled: true
    overwrite: false
processing:
  # snap-native preserves SNAP's terrain-corrected scene grid.
  resolution_policy: snap-native
  # scene writes one full-scene mosaic per requested feature.
  output_mode: scene
  subset_mode: aoi
  subswaths: [IW1, IW2, IW3]
  workers: 1
  cache_gb: 8
  patch_size: 256
  sar_band_order:
    - vv_db
    - vh_db
    - vv_vh_ratio_db
    - vv_minus_vh_db
    - vv_glcm_mean
    - vv_glcm_std
    - vv_glcm_entropy
    - decomp_entropy
    - decomp_anisotropy
    - decomp_alpha
  biophysical_bands: [uo, vo, swh]
```

Canonical feature-file layout for v1:

- `/data/shapefiles/<scene_id>/*.geojson`
- `/data/shapefiles/<scene_id>/*.shp`

Canonical biophysical layout for v1:

- `/data/biophysical/<scene_id>/<band>.tif`

Stage markers are written under:

- `/data/manifests/<run_id>/stages/slc_process.json`
- `/data/manifests/<run_id>/stages/patch_extract.json`
- `/data/manifests/<run_id>/stages/patch_stack.json`

SLC stage options:

- `stages.slc_process.gpt`: optional explicit path to the SNAP `gpt` binary inside the container.
- `stages.slc_process.graphs_dir`: optional override for the SNAP graph directory.
- `stages.slc_process.processor_script`: optional override for the vendored SLC entrypoint.

SLC processing options:

- `processing.resolution_policy`: `snap-native` (default) or `utm-grid`.
- `processing.output_mode`: `scene` (default), `subswaths`, or `both`.
- `processing.subset_mode`: `aoi` or `full-swath`.
