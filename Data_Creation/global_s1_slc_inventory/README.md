# Global optical-reference Sentinel-1 SLC inventory

This directory contains the reproducible global processing inventory generated
by `Data_Creation/build_global_s1_slc_inventory.py`.

## Selection policy

- 141 optical-reference groups: 63 MARIDA, 43 NASA PlanetScope, 5 Ghana,
  4 Greece Sentinel-2, and 26 Jamila Floating Debris groups.
- Every source AOI is expanded by 30 km.
- Jamila uses the nominal observation timestamp stored in the Ocean Scan JSON;
  optical catalogue confirmation is not required.
- Sentinel-1 candidates must be IW SLC dual-polarisation VV/VH products and
  fall within 72 hours before or after the reference time.
- Multiple adjacent SLC frames may form one coverage set, but their sensing
  starts must span no more than 12 hours.
- A role is processable only when the selected scene set covers at least 99.9%
  of the buffered AOI.
- Sentinel-1 granules are deduplicated before server processing. Associations
  with every optical group remain in the audit table.

## Generated files

- `optical_groups.csv` and `optical_groups.geojson`: source inventory and exact
  buffered AOIs.
- `global_s1_slc_points.csv`: QGIS/OpenDrift reference catalogue. It retains the
  30 km AOI corners as non-seed context and adds eligible source-label points:
  connected Marine Debris (class 1) components from MARIDA masks, representative
  points from non-absence Jamila geometries, and supplied Ghana observation points.
  MARIDA folders without class-1 pixels correctly receive no drift seed.
- `global_s1_slc_selection_summary.csv`: one audit row for every before/after
  decision, including failures.
- `global_s1_slc_associations.csv`: selected SLC-to-optical associations,
  including partial sets for audit.
- `global_s1_slc_processing_targets.csv`: one row per unique processable SLC.
- `global_s1_slc_processing_points.csv`: compact AOI bounds consumed by the
  server processor.
- `global_s1_slc_job.yaml`: server job containing every unique processable SLC.
- `copernicus_s1_slc_cache.json`: cached catalogue responses for reproducible
  reruns without repeated requests.

The current catalogue run produced 106 complete source-role selections and
116 unique SLC granules. The remaining 176 source-role checks did not achieve
99.9% coverage within the fixed 72-hour search and 12-hour set-span rules; they
remain documented but are not silently added to the server job.

## Server handoff

From the repository root on the server:

```bash
sudo install -m 0644 \
  Data_Creation/global_s1_slc_inventory/global_s1_slc_processing_targets.csv \
  /mnt/storage/bolelang_mount/Joshua/sar-data/raw/

sudo install -m 0644 \
  Data_Creation/global_s1_slc_inventory/global_s1_slc_processing_points.csv \
  /mnt/storage/bolelang_mount/Joshua/sar-data/raw/

sudo install -m 0644 \
  Data_Creation/global_s1_slc_inventory/global_s1_slc_job.yaml \
  /mnt/storage/bolelang_mount/Joshua/jobs/
```

Rebuild the pipeline image because the processor now accepts deduplicated
long-form `scene` targets:

```bash
cd ~/students/Joshua/src/Masters/sar_server_pipeline
sudo docker compose \
  --env-file /mnt/storage/bolelang_mount/Joshua/server.env \
  build pipeline
```

Validate target loading without downloading by temporarily adding
`prepare_only: true` under `stages.slc_process` in the mounted job YAML, then
run:

```bash
sudo docker compose \
  --env-file /mnt/storage/bolelang_mount/Joshua/server.env \
  run --rm pipeline slc_process \
  --manifest /job/global_s1_slc_job.yaml
```

Remove `prepare_only: true` after the validation run and execute the same
command to begin downloading and processing. The generated job sets
`pad_deg: 0` because its processing points already describe the 30 km buffered
AOI bounds; this avoids applying the buffer twice.
