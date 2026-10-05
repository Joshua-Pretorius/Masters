# MERIA SAR Processing and QGIS Digitising System

## 1. Purpose

This system converts optical marine-debris observations into carefully reviewed Sentinel-1 SAR annotations for later patch extraction and machine-learning work.

The main stages are:

1. Catalogue optical observations and their positions and dates.
2. Associate each observation with nearby Sentinel-1 SLC acquisitions.
3. Download and process the required Sentinel-1 data on Skua.
4. Use OpenDrift to estimate where an observed object may have moved by the SAR acquisition time.
5. Generate portable QGIS projects and editable GeoPackages on Skua without running a graphical QGIS session.
6. Transfer selected batches through the Ubuntu transfer laptop to `D:\Joshua`.
7. Digitise manually in QGIS Desktop from `D:\Joshua`.
8. Return only edited GeoPackages to Skua.
9. Validate the annotations and export accepted polygons for patch extraction.

The processed SAR archive remains authoritative on Skua. Preparing a batch does not duplicate processed rasters elsewhere on Skua.

## 2. Machines and responsibilities

### 2.1 Windows development repository

Location:

```text
D:\Masters
```

This is where the source code, catalogues, tests, job definitions, documentation and research source material are maintained.

It is not the working QGIS batch directory and is not the authoritative server data archive.

### 2.2 Skua server

Code checkout:

```text
~/students/Joshua/src/Masters
```

Authoritative data root:

```text
/mnt/storage/bolelang_mount/Joshua/sar-data
```

Skua performs the expensive, headless work:

- Sentinel-1 downloading;
- SNAP SLC processing;
- raster-product generation;
- CMEMS and ERA5 forcing retrieval and caching;
- OpenDrift predictions;
- GeoPackage creation;
- portable QGIS project creation;
- transfer-manifest generation;
- returned-annotation validation;
- canonical annotation export;
- patch extraction and stacking.

QGIS Desktop does not run on Skua. PyQGIS runs off-screen only to create project files, layers, forms and styling.

### 2.3 Ubuntu transfer laptop

Transfer root:

```text
/home/bsibolla/Desktop/Joshua
```

This machine is now only a transfer and temporary staging machine. It pulls selected batch files from Skua with `rsync`, after which the complete batch directory is moved through Google Drive or another transfer method to the Windows digitising workspace.

Digitising is not performed here under the current workflow.

### 2.4 Windows QGIS digitising workspace

Location:

```text
D:\Joshua
```

This is the actual local QGIS workspace. All material used for manual digitising must be present here with the complete generated directory structure intact.

QGIS projects should be opened from inside the appropriate batch directory under `D:\Joshua`.

## 3. Three important identities

### 3.1 Physical SAR scene

A physical scene is one Sentinel-1 acquisition and its processed raster products.

It normally has one processed scene directory and one scene manifest. The same physical acquisition may support several optical observations.

### 3.2 Digitising task

A task is one optical-reference/SAR relationship, not merely one raster.

For example, one Sentinel-1 acquisition can be:

- the `after` scene for one observation; and
- the `before` scene for a later observation.

These remain independent optical relationships with separate metadata and predictions. They share one editable
annotation GeoPackage and raster stack for the physical SAR acquisition. The original optical points appear on
both the before and after SAR views, with their observation dates and roles visible.

### 3.3 Batch

A batch is a selected group of physical SAR scenes prepared for transfer and manual review. Each scene includes
all of its linked optical relationships.

A batch directory contains small project and manifest files. Its transfer manifest points directly to the required processed rasters in their existing Skua locations. It does not create a second server-side raster archive.

## 4. Development repository structure

The relevant structure under `D:\Masters` is:

```text
D:\Masters\
├── Data_Creation\
├── Domain_SSL\
├── Ghana_Drift\
├── Jamila_Floating_Debris\
├── MARIDA\
├── MERIA\
├── PlanetData\
├── SADrift\
├── SAR_PP\
├── sar_server_pipeline\
├── Scripts\
├── tools\
├── docs\
├── outputs\
├── Progress_Tracker\
└── Writing\
```

### 4.1 `Data_Creation`

This contains the catalogue, scene-selection and training-data preparation code.

```text
D:\Masters\Data_Creation\
├── global_s1_slc_inventory\
├── meria_global_s1_slc\
├── meria_sa_plastic_s1_slc\
├── Library\
├── Patches\
└── tests\
```

Important global files include:

```text
Data_Creation\global_s1_slc_inventory\
├── global_s1_slc_associations.csv
├── global_s1_slc_points.csv
├── global_s1_slc_processing_targets.csv
├── global_s1_slc_processing_points.csv
├── global_s1_slc_job.yaml
├── ghana_oct25_partial_job.yaml
├── optical_groups.csv
├── optical_groups.geojson
└── README.md
```

- `global_s1_slc_associations.csv` records optical-observation/SAR relationships, including incomplete-coverage audit associations.
- `global_s1_slc_points.csv` contains source-label positions, supplied observation positions and non-seed AOI context points.
- `global_s1_slc_processing_targets.csv` contains deduplicated physical SAR scenes selected by the standard processing policy.
- `global_s1_slc_processing_points.csv` supplies processing bounds for the standard physical scenes.
- `global_s1_slc_job.yaml` defines the standard global processing job.
- `ghana_oct25_partial_job.yaml` explicitly processes the two selected partial-coverage Ghana acquisitions from 25 October 2018.
- `optical_groups.csv` and `optical_groups.geojson` describe the source optical groups and their spatial footprints.

### 4.2 Source datasets

The research source directories include:

- `Ghana_Drift`: supplied Ghana observation positions and supporting data.
- `Jamila_Floating_Debris`: hand-labelled Sentinel-2 floating-object observations.
- `MARIDA`: labelled optical masks, where class DN 1 represents marine debris.
- `MERIA`: the South African observation catalogue and associated inputs.
- `PlanetData`: PlanetScope-related data and metadata.

These sources establish where and when debris was observed. They do not automatically become final SAR polygons.

### 4.3 `Domain_SSL`

Relevant OpenDrift scripts are under:

```text
D:\Masters\Domain_SSL\Scripts\Preprocessing\
├── fetch_drift_forcing.py
├── run_planet_to_sar_opendrift.py
└── run_opendrift_batch.py
```

These scripts retrieve or reuse environmental forcing and project eligible source positions to the SAR acquisition time.

### 4.4 `sar_server_pipeline`

```text
D:\Masters\sar_server_pipeline\
├── digitising\
├── docker\
├── docs\
├── jobs\
├── local\
├── pipeline\
├── secrets\
├── stages\
├── tests\
├── tools\
├── vendor\
├── compose.yml
├── digitising-requirements.txt
└── requirements.txt
```

- `digitising`: task discovery, QGIS scaffolding, GeoPackages, OpenDrift orchestration and annotation validation.
- `docker`: the separate SNAP and digitising Docker images.
- `docs`: operational documentation.
- `jobs`: checked-in example job manifests.
- `pipeline`: manifest loading and pipeline execution.
- `secrets`: local CMEMS and CDS credential files mounted read-only into the digitising container.
- `stages`: SLC processing, patch extraction and patch stacking.
- `tests`: automated regression tests.
- `tools`: operational helper scripts.
- `vendor`: processing scripts included in the SNAP image.

## 5. Skua server directory structure

The main host structure is:

```text
/mnt/storage/bolelang_mount/Joshua/
├── server.env
├── jobs/
└── sar-data/
    ├── raw/
    ├── processed/
    ├── biophysical/
    ├── digitising_batches/
    ├── digitising_returns/
    ├── shapefiles/
    ├── patches/
    ├── stacks/
    ├── manifests/
    └── logs/
```

### 5.1 `server.env`

Expected location:

```text
/mnt/storage/bolelang_mount/Joshua/server.env
```

It supplies Docker Compose paths and relevant processing credentials, conceptually:

```dotenv
DATA_ROOT=/mnt/storage/bolelang_mount/Joshua/sar-data
JOB_DIR=/mnt/storage/bolelang_mount/Joshua/jobs
EDL_USER=...
EDL_PASS=...
```

### 5.2 `jobs`

```text
/mnt/storage/bolelang_mount/Joshua/jobs/
```

Job YAML files specify:

- dataset mode;
- exact targets;
- catalogue inputs;
- raw and processed roots;
- enabled stages;
- SNAP processing settings;
- worker and memory settings.

### 5.3 `sar-data/raw`

```text
/mnt/storage/bolelang_mount/Joshua/sar-data/raw/
```

This contains installed catalogues and downloaded Sentinel-1 source data. Shared downloads are cached conceptually as:

```text
raw/
└── slc/
    └── _shared_slc_zips/
        └── <sentinel-1-granule>/
            └── <sentinel-1-granule>.zip
```

The shared cache prevents repeated downloads when several tasks use the same physical SAR acquisition.

### 5.4 `sar-data/processed`

```text
/mnt/storage/bolelang_mount/Joshua/sar-data/processed/
```

This is the authoritative processed SAR archive.

A typical global scene is:

```text
processed/
└── Global_S1_S1_<sentinel-1-granule>/
    └── scene_<timestamp>/
        ├── *_slc_manifest.json
        ├── *_slc_native_vv.tif
        ├── *_slc_native_vh.tif
        ├── *_slc_native_vv_refined_lee.tif
        ├── *_slc_native_vv_refined_lee_db.tif
        ├── *_slc_native_vv_glcm_mean.tif
        ├── *_slc_native_vv_glcm_std.tif
        ├── *_slc_native_vv_glcm_entropy.tif
        ├── *_slc_native_decomp_entropy.tif
        ├── *_slc_native_decomp_anisotropy.tif
        ├── *_slc_native_decomp_alpha.tif
        └── digitising/
```

A South African scene typically follows:

```text
processed/
└── MERIA_SA_<number>_<area>/
    ├── before_<timestamp>/
    └── after_<timestamp>/
```

The scene manifest records the physical granule, scene identity, acquisition time, processing status and output paths.

Temporary SNAP work is stored under:

```text
processed/_slc_work/
```

This temporary directory is not transferred to the QGIS machine.

### 5.5 Task directories

Each relationship receives a task directory beneath its physical scene:

```text
processed/<physical-scene>/<scene>/digitising/<task-id>/
├── task.gpkg
├── task_manifest.json
└── drift/
```

The task GeoPackage carries read-only original optical points, prediction layers and metadata. The scene's
`digitising/scene_annotations.gpkg`, `scene.qgz` and `scene_manifest.json` provide the single editable review.
Existing `task.qgz` files from earlier batches remain legacy projects; new scene batches do not generate them.
The physical TIFFs remain at scene level.

### 5.6 `sar-data/biophysical`

```text
sar-data/biophysical/forcing_cache/
```

This stores reusable CMEMS and ERA5 forcing. The forcing data stay on Skua and are not transferred to QGIS. Prediction results are placed in the task GeoPackage.

### 5.7 `sar-data/digitising_batches`

```text
sar-data/digitising_batches/<batch-name>/
├── README.txt
├── batch.qgz
├── batch_manifest.json
├── transfer_files.txt
├── return_files.txt
├── import_report.json
└── import_backups/
```

- `batch.qgz`: combined QGIS project for the selected SAR scenes.
- `batch_manifest.json`: scene and optical-association selection, dataset and prediction status.
- `transfer_files.txt`: exact files that must be pulled from Skua.
- `return_files.txt`: exact editable GeoPackages that may be returned.
- `README.txt`: generated transfer and import commands.
- `import_report.json`: validation results after return.
- `import_backups`: backups of earlier canonical GeoPackages before replacement.

The batch directory does not contain duplicated copies of the processed SAR rasters.

### 5.8 `sar-data/digitising_returns`

```text
sar-data/digitising_returns/<batch-name>/
```

This is the incoming quarantine area for returned GeoPackages. A returned file is not canonical until the import command validates it.

### 5.9 `sar-data/shapefiles`

Validated annotations are exported as:

```text
sar-data/shapefiles/<physical-scene-id>/scene_annotations.geojson
```

Despite the directory name, the canonical current export is GeoJSON. Reference points and OpenDrift predictions are never exported as manual annotation polygons.

### 5.10 `patches`, `stacks`, `manifests` and `logs`

- `patches`: image windows and masks extracted around accepted annotations.
- `stacks`: combined SAR and biophysical model inputs.
- `manifests`: pipeline execution and stage state.
- `logs`: operational logs.

These directories are not part of normal QGIS batch transfers.

## 6. Docker services on Skua

### 6.1 `pipeline`

The SNAP processing service:

- downloads missing Sentinel-1 SLC ZIPs;
- extracts `.SAFE` products;
- processes VV and VH;
- creates Refined-Lee, GLCM and decomposition products;
- writes scene manifests;
- can later extract and stack patches.

Its important mounts are:

```text
Host DATA_ROOT -> /data
Host JOB_DIR   -> /job
```

### 6.2 `digitising`

The separate headless digitising-preparation service:

- discovers processed scenes;
- creates independent optical/SAR tasks;
- reconciles completed annotations;
- runs or reuses OpenDrift;
- creates GeoPackages and QGIS projects;
- writes transfer and return manifests;
- validates returned work.

Its mounts are:

```text
Host sar-data   -> /data
Host repository -> /repo         read-only
Host secrets    -> /run/secrets  read-only
```

The containers are disposable. Persistent outputs survive because they are written through the mounted host directories.

## 7. Contents of a task GeoPackage

Each `task.gpkg` contains:

```text
annotations
reference_points
predicted_points
prediction_envelopes
task_metadata
```

### 7.1 `annotations`

This is the only layer that the operator edits.

Classes are:

```text
plastic
ship
wake
slick
calm_water
open_ocean
other
uncertain
```

Feature-confidence values are:

```text
high
medium
low
not_assessed
```

Correspondence confidence uses the same values. Feature confidence describes how clearly the SAR feature itself
can be distinguished and delineated. Correspondence confidence describes how strongly the spatial, temporal,
optical and drift evidence connects it to the source observation.

Training-status values are:

```text
candidate
accepted_proxy
excluded
```

- `candidate` is a provisional digitised feature that still requires a final include/exclude decision. It stays in
  the local GeoPackage, keeps the task pending and is not exported for training.
- `accepted_proxy` is a reviewed feature judged suitable for use as a weak or proxy SAR label. It is not claimed to
  be direct material ground truth. Both confidence dimensions must be assessed before acceptance.
- `excluded` is a reviewed feature retained for provenance, such as a confuser, unsupported correspondence or
  unusable boundary. It completes the review decision but is never exported into the training annotation GeoJSON.

When a polygon is created, database triggers populate:

- an immutable UUID;
- a readable task-prefixed patch ID;
- task and observation identity;
- dataset and role;
- physical scene ID;
- optical and SAR times;
- optical-to-SAR time difference.

### 7.2 `reference_points`

These show the original optical/source positions.

Eligible seeds include:

- supplied Ghana observation points;
- MARIDA class-1 connected-component points;
- representative points from non-absence Jamila geometries;
- supplied South African observations.

Broad AOI points are retained for context but marked as ineligible OpenDrift seeds.

### 7.3 `predicted_points` and `prediction_envelopes`

These show the OpenDrift estimate at the SAR acquisition time and its search region. They guide inspection but are not accepted as ground truth.

### 7.4 `task_metadata`

This contains task provenance, times, scene identity, source dataset, browser links, coverage information and prediction status.

## 8. OpenDrift's role

OpenDrift transforms an eligible optical observation position from the optical observation time toward the Sentinel-1 acquisition time.

It uses environmental forcing such as:

- CMEMS currents;
- CMEMS wave/Stokes information;
- ERA5 wind;
- particle ensembles and windage variation.

Forward modelling is used when SAR is after optical. Backward modelling is used when SAR is before optical.

The result is a probable search area, not an automatic annotation. Coastal physics, forcing resolution and object behaviour introduce uncertainty. The human operator still decides what is visible in SAR.

## 9. Batch preparation on Skua

A typical preparation command is:

```bash
sudo docker compose run --rm digitising prepare \
  --dataset global \
  --limit 3 \
  --batch-name example_batch \
  --prediction-mode auto
```

Preparation performs the following:

1. Discover processed scene manifests.
2. Match optical/SAR associations to physical scenes.
3. Group relationships by physical SAR acquisition and reconcile scene annotations.
4. Skip scenes that already contain valid completed annotations.
5. Select the requested number of pending SAR scenes, bringing all linked optical relationships.
6. Create or refresh reference and prediction layers.
7. Preserve any existing scene and legacy task annotation layers.
8. Run or reuse OpenDrift.
9. Create one project and editable annotation GeoPackage per SAR scene.
10. Create the combined batch project.
11. Generate `transfer_files.txt`.
12. Generate `return_files.txt`.
13. Print the exact pull and return commands.

Processed partial-coverage relationships remain excluded by default. They can be deliberately included using:

```text
--include-partial
```

This does not relabel them as complete. Their true coverage status remains in task metadata.

## 10. Transfer from Skua to the Ubuntu staging laptop

The generated pull command follows this pattern:

```bash
rsync -avhP --info=progress2 --relative \
  --files-from=:/mnt/storage/bolelang_mount/Joshua/sar-data/digitising_batches/<batch>/transfer_files.txt \
  bolelang@146.64.214.137:/mnt/storage/bolelang_mount/Joshua/sar-data/ \
  /home/bsibolla/Desktop/Joshua/<batch>/
```

Before a real transfer, run a dry run:

```bash
rsync -avhnP --stats --relative \
  --files-from=:/mnt/storage/bolelang_mount/Joshua/sar-data/digitising_batches/<batch>/transfer_files.txt \
  bolelang@146.64.214.137:/mnt/storage/bolelang_mount/Joshua/sar-data/ \
  /home/bsibolla/Desktop/Joshua/<batch>/
```

Check free space with:

```bash
df -h /home/bsibolla/Desktop/Joshua
```

Check the current batch size with:

```bash
du -sh /home/bsibolla/Desktop/Joshua/<batch>
```

`--relative` preserves the server-relative directory hierarchy required by the portable QGIS project. `-P` displays progress and retains partial files if a transfer is interrupted. Re-running the same command skips matching completed files.

The transfer includes only listed material such as:

- required SAR TIFFs;
- scene manifests;
- task GeoPackages;
- scene projects and annotation GeoPackages;
- the combined batch project;
- batch and task metadata.

It excludes:

- raw SLC ZIPs;
- extracted `.SAFE` directories;
- `_slc_work`;
- forcing-cache data;
- unrelated scenes;
- patch stacks;
- server logs.

## 11. Moving a batch into `D:\Joshua`

The complete batch directory must be moved from the Ubuntu staging laptop to Windows. Google Drive may be used, but it must preserve the hierarchy.

Correct Windows structure:

```text
D:\Joshua\
└── <batch-name>\
    ├── digitising_batches\
    │   └── <batch-name>\
    │       ├── batch.qgz
    │       ├── batch_manifest.json
    │       ├── transfer_files.txt
    │       ├── return_files.txt
    │       └── README.txt
    └── processed\
        └── <required physical scenes and task directories>
```

Example:

```text
D:\Joshua\ghana_all_001\digitising_batches\ghana_all_001\batch.qgz
```

Open that file in QGIS Desktop.

Do not copy only `batch.qgz`. The project uses relative paths to find `processed\...` beneath the batch root. Moving the whole batch folder is safe; reorganising its contents can produce missing-layer warnings.

## 12. Manual QGIS procedure

For each SAR scene:

1. Open the batch project from `D:\Joshua`.
2. Select the SAR scene and its dated optical before/after subgroups.
3. Inspect the original reference points on both comparison scenes.
4. Inspect the OpenDrift predicted points and envelopes.
5. confirm the optical and SAR timestamps and their time difference.
6. Stream or open the closest relevant PlanetScope or Sentinel-2 imagery.
7. Inspect the available SAR layers, particularly Refined-Lee VV dB, VV/VH, texture and decomposition products.
8. Draw the final polygon in `Scene annotations (EDIT THIS)` against the SAR evidence.
9. Select the class, feature confidence and correspondence confidence.
10. Leave the feature as `candidate` while it still needs review, then change it to `accepted_proxy` or `excluded`.
11. For accepted proxies, enter the supporting optical observation IDs in `evidence_obs_ids`; add notes where uncertainty or confusers are important.
12. Save the GeoPackage edits.

The evidence roles are:

- optical imagery establishes the original observation;
- OpenDrift narrows the SAR-time search area;
- the SAR imagery is used for the final SAR polygon;
- the human annotation is the only layer accepted for training export.

## 13. Returning edited work

Only edited `scene_annotations.gpkg` files need to travel back. The TIFFs must not be uploaded again.

Because digitising now happens on Windows, the edited GeoPackages are first moved back to the matching Ubuntu batch hierarchy. The generated `return_files.txt` still defines the exact files that may be returned.

From Ubuntu, the return command follows:

```bash
rsync -avP --relative \
  --files-from=/home/bsibolla/Desktop/Joshua/<batch>/digitising_batches/<batch>/return_files.txt \
  /home/bsibolla/Desktop/Joshua/<batch>/ \
  bolelang@146.64.214.137:/mnt/storage/bolelang_mount/Joshua/sar-data/digitising_returns/<batch>/
```

The edited Windows `scene_annotations.gpkg` files must replace their corresponding copies in the Ubuntu batch before this command is run. No raster files need to be copied back from Windows.

## 14. Import and validation on Skua

After the returned GeoPackages reach `digitising_returns`, run:

```bash
cd ~/students/Joshua/src/Masters/sar_server_pipeline

sudo docker compose run --rm digitising import \
  --batch <batch-name>
```

Validation requires:

- at least one polygon;
- an allowed class;
- allowed feature-confidence and correspondence-confidence values;
- a final `accepted_proxy` or `excluded` training decision rather than unresolved `candidate` status;
- populated and unique IDs;
- matching scene identity and valid supporting optical observation IDs for accepted proxies;
- geometry intersecting the corresponding SAR raster;
- no conflict with an independently completed canonical server GeoPackage.

Invalid returns stay in the incoming area and are reported in:

```text
sar-data/digitising_batches/<batch>/import_report.json
```

Valid annotation-only GeoJSON is exported to:

```text
sar-data/shapefiles/<physical-scene-id>/scene_annotations.geojson
```

## 15. Patch extraction and model preparation

After annotations are accepted:

1. Patch extraction finds canonical annotation GeoJSON files.
2. It identifies the exact physical scene from `scene_id`.
3. It reads the corresponding scene manifest and raster products.
4. It creates image patches and annotation masks.
5. Patch stacking can combine SAR channels and selected biophysical variables.
6. The resulting samples become inputs for model training and evaluation.

Reference points and OpenDrift predictions never enter this stage as if they were manual SAR polygons.

## 16. Data ownership and duplication rules

- Skua is authoritative for raw downloads, processed SAR, environmental forcing and accepted annotations.
- Git is authoritative for code, catalogues, tests, documentation and job definitions.
- `D:\Joshua` is the active manual-QGIS workspace.
- The Ubuntu laptop is a temporary transfer/staging location.
- Google Drive is a transport method, not an authoritative data layout.
- A prepared batch does not duplicate processed rasters on Skua.
- The laptop and Windows machine intentionally receive working copies of only the selected files.
- Shared SAR acquisitions remain one physical raster set but may support several independent task GeoPackages.
- Only edited GeoPackages return to Skua; SAR TIFFs remain unchanged.

## 17. Operational safety rules

1. Never pull the entire Skua `processed` archive onto a laptop.
2. Use batches small enough for the available local disk space.
3. Run `rsync -avnP --stats` before each large transfer.
4. Check `df -h` before starting.
5. Transfer batches sequentially rather than concurrently.
6. Preserve the complete batch hierarchy when using Google Drive.
7. Keep the Windows batch until its annotations are returned and accepted.
8. Do not delete the Ubuntu staging batch until the returned GeoPackages have reached Skua.
9. Do not edit reference, prediction or metadata layers in QGIS.
10. Do not treat OpenDrift output as ground truth.
11. Do not collapse tasks merely because they share a physical Sentinel-1 acquisition.
12. Do not use catalogue selection alone as proof that a scene is processed; confirm its processed manifest and TIFFs on Skua.

## 18. Current end-to-end working arrangement

```text
D:\Masters
Code, catalogues, jobs and tests
        │
        │ Git push/pull
        ▼
Skua repository checkout
        │
        ▼
Skua sar-data
Raw SLC → SNAP processing → processed SAR
        │
        ▼
OpenDrift + headless QGIS preparation
        │
        ▼
transfer_files.txt
        │
        │ rsync
        ▼
Ubuntu staging laptop
/home/bsibolla/Desktop/Joshua/<batch>
        │
        │ Google Drive or equivalent whole-folder transfer
        ▼
Windows QGIS workspace
D:\Joshua\<batch>
        │
        │ manual digitising in task.gpkg
        ▼
Edited GeoPackages copied back to Ubuntu batch
        │
        │ rsync using return_files.txt
        ▼
Skua digitising_returns
        │
        ▼
Validation and canonical GeoJSON export
        │
        ▼
Patch extraction and model-ready stacks
```
