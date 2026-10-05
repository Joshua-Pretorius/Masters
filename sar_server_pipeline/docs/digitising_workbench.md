# Headless QGIS digitisation workbench

The `digitising` service uses the pinned QGIS 3.44.13 Noble LTR image on the terminal-only Skua server. It never starts a QGIS desktop session. PyQGIS
runs with `QT_QPA_PLATFORM=offscreen` only to create portable `.qgz` projects, forms, styles, and GeoPackages.
The generated project is opened later with QGIS Desktop on the separate work machine.

## Configuration

Set these values in the Compose environment file:

```dotenv
DATA_ROOT=/mnt/storage/bolelang_mount/Joshua/sar-data
REPO_ROOT=/path/to/Masters
DIGITISING_REMOTE=bolelang@146.64.214.137
REMOTE_DATA_ROOT=/mnt/storage/bolelang_mount/Joshua/sar-data
DESKTOP_ROOT=/home/bsibolla/Desktop/Joshua
DIGITISING_SECRETS_DIR=./secrets
```

The read-only repository mount supplies the checked-in SA/global association catalogs and existing OpenDrift
scripts. Put the following files in `DIGITISING_SECRETS_DIR` when automatic forcing retrieval is required:

- `cmems_credentials`: Copernicus Marine credentials JSON.
- `cdsapirc`: CDS API configuration, using the normal `.cdsapirc` contents.

Missing credentials do not prevent task preparation. The task records `forcing_unavailable` and QGIS still opens
with its SAR and reference layers.

## Prepare and transfer a batch

Build the dedicated image without rebuilding SNAP:

```bash
docker compose build digitising
```

Preview selection without creating or exporting anything:

```bash
docker compose run --rm digitising prepare \
  --dataset all \
  --limit 10 \
  --batch-name batch_001 \
  --dry-run
```

Create the batch:

```bash
docker compose run --rm digitising prepare \
  --dataset all \
  --limit 10 \
  --batch-name batch_001
```

Preparation now groups by physical Sentinel-1 acquisition. `--limit 10` selects ten pending SAR scenes, not ten
optical relationships. Within each scene, the project shows every linked optical observation in its own dated
before/after subgroup. The same original optical points therefore appear on both of their SAR comparisons. If a
SAR acquisition is after one observation and before another, both subgroups appear beneath that single SAR scene.
`--task TASK_ID` selects the entire scene containing that task, including its other optical associations. Use
`--prediction-mode cached-only` to prohibit forcing downloads, or `skip` when preparing without predictions.

The scene has one editable `scene_annotations.gpkg` and one SAR raster stack. Each association retains a separate
`task.gpkg` for original reference points, per-SAR-time drift predictions, metadata and image links. Those task
GeoPackages are reference material in the scene project; their legacy annotation layers are not loaded for editing.
Preparation preserves existing legacy GeoPackages and their polygons. To create an old observation-centred batch
explicitly, pass `--grouping observation`.

The scene project includes every relationship and reference point in the checked-in catalog. Points added only to
an older desktop GeoPackage are not automatically present in a newly prepared server batch; reconcile those
additions into the catalog before regenerating that scene. A partial association included with `--include-partial`
also needs a valid-pixel coverage review before its points are used as SAR evidence.

Global associations with incomplete buffered-AOI coverage remain excluded by default. To deliberately prepare a
processed partial association, pass `--include-partial` together with explicit `--task TASK_ID` arguments. The
batch manifest records this choice so the same tasks remain available during return validation and import.

The command prints exact pull and return commands. The pull command uses the generated
`digitising_batches/<batch>/transfer_files.txt` on the remote server with `rsync --relative`. It transfers only the
selected processed GeoTIFFs, GeoPackages, manifests, and projects; it does not stage another raster copy on Skua.

On the work machine, open:

```text
/home/bsibolla/Desktop/Joshua/<batch>/digitising_batches/<batch>/batch.qgz
```

Edit only layers named `Scene annotations (EDIT THIS)`. Class, feature confidence, correspondence confidence and
training status are controlled dropdowns. GeoPackage triggers populate a stable UUID, readable scene-prefixed
patch ID and SAR identity when each polygon is inserted. For an accepted proxy, enter the supporting optical
observation ID or comma-separated IDs in `evidence_obs_ids`; use the IDs shown in the dated optical subgroups and
`scene_manifest.json`. The field records the actual evidence used for that polygon rather than assigning every
polygon to whichever optical observation happened to be closest in time.

Every new polygon starts as `candidate`. Feature confidence records how clearly the SAR feature itself can be
distinguished and delineated. Correspondence confidence records how strongly the temporal, spatial, optical and
drift evidence links that SAR feature to the source observation. Set `training_status=accepted_proxy` only after
both confidence dimensions have been assessed and the polygon is suitable as a weak/proxy training label. Use
`excluded` after review when the feature must remain in the audit record but must not enter training. Candidate
features keep a task pending, excluded features complete review without being exported, and only accepted proxies
are written to the canonical training GeoJSON.

## Return and import

Run the return command printed by `prepare`. It uses `return_files.txt`, so only the edited scene GeoPackages are copied to:

```text
sar-data/digitising_returns/<batch>/
```

Validate and import on Skua:

```bash
docker compose run --rm digitising import --batch batch_001
```

An imported scene must contain at least one valid polygon, permitted class, split-confidence and training-status
values, unique IDs, matching SAR identity, accepted-proxy optical provenance, and geometry intersecting its SAR
raster. Invalid returns remain quarantined and are listed
in `digitising_batches/<batch>/import_report.json`. The prior server GeoPackage is backed up under
`digitising_batches/<batch>/import_backups/` before replacement.

Valid annotation-only GeoJSON is written to:

```text
shapefiles/<physical-scene-id>/scene_annotations.geojson
```

Reference and prediction layers remain inside the task GeoPackages and cannot be ingested by patch extraction.

## Task identity

A task represents one optical-reference/SAR association. Shared acquisitions such as SA001-after and SA002-before
keep separate dated reference and prediction layers, but their scene has one editable annotation layer and one
canonical export. Existing observation-centred batches remain importable through their original manifests.

Global tasks are created from complete coverage associations by default. Explicitly requested processed partial
associations can be included with `--include-partial`; their original coverage ratios and incomplete status remain
recorded in task metadata. Their 30 km AOI boundary points remain non-seed context. Source-label points are eligible
for drift only when their provenance supports it: MARIDA class-1 mask components, non-absence Jamila debris
geometries, and supplied Ghana observation points. A source group with no positive debris label correctly has no
drift seed.
