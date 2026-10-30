# MARIDA 16PEC January 16 local follow-up

Batch: `marida_16pec_20190116_followup`.
Parent: `marida_16pec_20190111_03` (both 23:57:57 / 7CEB and 23:58:22 / 4D98).

Two Sentinel-1A IW SLC VV/VH scenes, descending relative orbit 55:
- 2019-01-16 11:37:14 UTC, FC33; 87.04% of buffered AOI.
- 2019-01-16 11:37:41 UTC, B06D; 26.29% of buffered AOI.
Their catalogue footprints jointly cover 100% of the original 30 km buffered processing rectangle. Actual valid-pixel coverage requires output verification.

User requested this follow-up on 2026-10-30 after reporting thick debris in the area. The existing January 12 16:16:31 UTC optical reference is historical context (91.35 hours earlier), not a January 16 label. Both slices require review. No new optical observation date or confirmed plastic label is asserted.

## Local execution
`local_job.yaml` uses the existing pipeline with SNAP native resolution, full-swath IW1/IW2/IW3, one worker and 8 GB cache. Patch extraction and stacking are disabled pending annotation.
Data: `D:/Masters/outputs/marida_16pec_20190116_followup`.
Preflight passed for two targets. Background local download/processing started 2026-10-30. See `run.stderr.log` (INFO lines), `process.pid`, and the stage marker under `manifests/marida_16pec_20190116_followup-local-v1/stages/slc_process.json`.
A success marker plus processed scene manifests and valid rasters are required before calling this complete. No Skua connection is required.

Resume from `D:/Masters/sar_server_pipeline` with the opendrift conda Python:
`python -m pipeline slc_process --manifest jobs/marida_16pec_20190116/local_job.yaml`
Do not start a duplicate while the process in process.pid is running.

## Registration
Updated global associations, processing targets, processing points, selection summary, global job, named batch registry and MERIA scene/batch workbook. `manual_followup_associations.json` preserves the explicit exception during inventory rebuilds. Catalogue provenance is in `asf_catalogue.json`; backups precede each original file change.

## Verified setup and automatic finalization
Both targets passed pipeline preflight. Four batch-registry tests and five global-inventory tests passed. The QGIS completion environment passed imports and EPSG:4326 checks. The workbook was updated through its existing Excel session after saving a backup of unsaved edits; existing rows were preserved.

`finish_local.py` is running locally alongside the processor. It waits for the SLC stage result, checks both processed manifests, raster readability, sampled valid pixels and within-scene grid alignment, then prepares the QGIS batch with drift prediction skipped. Current status and errors are recorded in `batch.json`. This setup does not mean processing has completed.

For a later restart, use `run_local.ps1` only after both existing workers have stopped. Keep the computer awake and the D: drive connected while the job runs. Data remain under the local outputs directory; no remote server is used. The QGIS project will be at `D:/Masters/outputs/marida_16pec_20190116_followup/digitising_batches/marida_16pec_20190116_followup/batch.qgz` after successful finalization.

## Delivery to D:\Joshua
On 2026-10-30 the user requested the prepared digitising batch under D:\Joshua. After both scenes pass processing and raster checks, prepare_qgis.py builds the batch, copies its portable transfer files into `D:/Joshua/New/marida_16pec_20190116_followup.preparing`, verifies all copy sizes and QGIS layer validity, then renames that staging folder to `D:/Joshua/New/marida_16pec_20190116_followup`. Existing destination folders are never overwritten. The prepared project will be `digitising_batches/marida_16pec_20190116_followup/batch.qgz` within that folder. Progress is recorded in delivery_status.json and batch.json. The waiting completion worker reads this script when processing finishes, so no processing restart is necessary.
