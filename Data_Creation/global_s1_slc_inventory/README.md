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
- `global_s1_slc_processing_targets.csv`: one row per unique processable SLC,
  including the five Portovenere control acquisitions and three selected Greece
  PLP 2024 monitoring acquisitions.
- `global_s1_slc_processing_points.csv`: compact AOI bounds consumed by the
  server processor. The Portovenere rows define a 15 km processing rectangle;
  the PLP monitoring rows define a 10 km processing rectangle. These added
  points are AOI corners, not optical labels or drift seeds.
- `global_s1_slc_job.yaml`: server job containing every unique processable SLC,
  including the Portovenere and PLP monitoring acquisitions.
- `plp_greece_2024_monitoring_job.yaml`: three-scene job for the selected PLP
  monitoring acquisitions only.
- `ghana_oct25_partial_job.yaml`: explicit two-scene server job for the processed-on-demand
  25 October 2018 Ghana partial-coverage acquisitions.
- `copernicus_s1_slc_cache.json`: cached catalogue responses for reproducible
  reruns without repeated requests.

The optical catalogue run produced 106 complete source-role selections and
116 unique SLC granules. Five SAR-only Portovenere control acquisitions and
three Greece PLP monitoring acquisitions were added to the processing inputs,
making 124 physical SLC targets in the global server job. The remaining 176 optical source-role checks did not achieve
99.9% coverage within the fixed 72-hour search and 12-hour set-span rules; they
remain documented but are not silently added to the server job.

The Portovenere window is 2025-04-11 00:00 to 2025-04-29 00:00 UTC (end
exclusive). Its three supplied positions are 44.07443 N, 9.83910 E;
44.07437 N, 9.83883 E; and 44.07431 N, 9.83873 E. The five Sentinel-1 IW SLC
catalogue footprints fully contained the 15 km processing rectangle bounded by
9.65143632–10.02638451 E and 43.93931368–44.20946855 N. A 30 km buffer
would not have been fully covered by the 2025-04-28 scene. The collections were
reported as not visible in the initial optical imagery, so no optical-derived
association or training label was added. `coverage_complete` in the five
processing rows means SAR catalogue footprint coverage of this rectangle only;
it does not confirm valid pixels or optical visibility. `association_count` is
zero for these rows, and patch extraction remains disabled.

The Greece PLP 2024 monitoring period is 2024-05-31 through 2024-06-27 UTC
(inclusive). The supplied positions are 39.03915 N, 26.52452 E and 39.03958 N,
26.52461 E. The user selected the 4, 16, and 23 June 2024 Sentinel-1 IW SLC
acquisitions from eight catalogue candidates in the period. Each selected
footprint fully contains the 10 km processing rectangle bounded by
26.40873464–26.64039536 E and 38.94921796–39.12951204 N. Their processing
rows use SAR acquisition times as references and have no optical association;
footprint coverage alone does not establish optical-label or valid-pixel
coverage. Use the focused PLP job to run these three scenes without processing
the full global target list.

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

sudo install -m 0644 \
  Data_Creation/global_s1_slc_inventory/plp_greece_2024_monitoring_job.yaml \
  /mnt/storage/bolelang_mount/Joshua/jobs/
```

To process only the three PLP 2024 monitoring acquisitions, select
`/job/plp_greece_2024_monitoring_job.yaml` in the command below instead of the
global job. Both CSVs must be installed first; the focused YAML references
their mounted `/data/raw/` paths.

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
