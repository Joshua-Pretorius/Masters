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

Selection is ordered by absolute optical-to-SAR time difference. A valid, populated task is exported and skipped
before the limit is applied, so `--limit 10` selects ten pending tasks. Use `--task TASK_ID` one or more times for
an explicit selection. Use `--prediction-mode cached-only` to prohibit forcing downloads, or `skip` when preparing
projects without predictions.

The command prints exact pull and return commands. The pull command uses the generated
`digitising_batches/<batch>/transfer_files.txt` on the remote server with `rsync --relative`. It transfers only the
selected processed GeoTIFFs, GeoPackages, manifests, and projects; it does not stage another raster copy on Skua.

On the work machine, open:

```text
/home/bsibolla/Desktop/Joshua/<batch>/digitising_batches/<batch>/batch.qgz
```

Edit only layers named `Annotations (EDIT THIS)`. Class and confidence are controlled dropdowns. GeoPackage
triggers populate a stable UUID, readable task-prefixed patch ID, and task metadata when each polygon is inserted.

## Return and import

Run the return command printed by `prepare`. It uses `return_files.txt`, so only the task GeoPackages are copied to:

```text
sar-data/digitising_returns/<batch>/
```

Validate and import on Skua:

```bash
docker compose run --rm digitising import --batch batch_001
```

An imported task must contain at least one valid polygon, permitted `Class` and `confidence` values, unique IDs,
matching task metadata, and geometry intersecting its SAR raster. Invalid returns remain quarantined and are listed
in `digitising_batches/<batch>/import_report.json`. The prior server GeoPackage is backed up under
`digitising_batches/<batch>/import_backups/` before replacement.

Valid annotation-only GeoJSON is written to:

```text
shapefiles/<physical-scene-id>/<task-id>_annotations.geojson
```

Reference and prediction layers remain inside the task GeoPackage and cannot be ingested by patch extraction.

## Task identity

A task represents one optical-reference/SAR association, not one raster folder. Shared acquisitions such as
SA001-after and SA002-before therefore have separate task directories, forms, annotations, statuses, and exports,
while both projects refer to the same processed SAR files.

Global tasks are created only from complete coverage associations. Their 30 km AOI boundary points remain
non-seed context. Source-label points are eligible for drift only when their provenance supports it: MARIDA class-1
mask components, non-absence Jamila debris geometries, and supplied Ghana observation points. A source group with
no positive debris label correctly has no drift seed.
