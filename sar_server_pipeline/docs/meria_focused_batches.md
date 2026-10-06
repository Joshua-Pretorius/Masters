# MERIA focused processing and digitising batches

This runbook selects only the 14 MERIA South African acquisitions, the 11
acquisitions in `jobs/global_all_unique_full_scenes.yaml`, and the already
processed Sentinel-1 acquisition at 2018-10-25 00:06 UTC for the 85 manual
16PCC candidate points. It does not prepare the broader MARIDA or Jamila
inventory.

Each batch covers one area and a short acquisition window. It has one to three
**physical SAR acquisitions**, irrespective of how many optical observations
share those acquisitions. The combined QGIS project has a group for each SAR
scene and one editable annotation GeoPackage per scene.

## Batch register

| Batch name | Area | SAR acquisition starts (UTC) |
| --- | --- | --- |
| `sa_durban_2019_apr21_27` | Durban | 2019-04-21 16:37, 2019-04-25 03:10, 2019-04-27 16:36 |
| `sa_durban_2022_apr05` | Durban | 2022-04-05 16:37 |
| `sa_durban_2022_apr17_20` | Durban | 2022-04-17 16:37, 2022-04-20 03:20 |
| `sa_durban_2022_apr27` | Durban | 2022-04-27 03:11 |
| `sa_east_london_2024_jun03` | East London | 2024-06-03 16:53 |
| `sa_east_london_2024_jun10_15` | East London | 2024-06-10 16:45, 2024-06-15 16:53 |
| `sa_gqeberha_2024_jun08` | Gqeberha | 2024-06-08 17:01 |
| `sa_gqeberha_2024_jun20` | Gqeberha | 2024-06-20 17:01 |
| `sa_gqeberha_2026_may05_10` | Gqeberha | 2026-05-05 17:01, 2026-05-10 17:09 |
| `meria_palma_2018_oct12` | Palma de Mallorca | 2018-10-12 05:44, 17:37 |
| `meria_honduras_2017_oct05` | Bay Islands | 2017-10-05 11:37 |
| `meria_honduras_2017_oct17` | Bay Islands | 2017-10-17 11:37 |
| `meria_honduras_2017_oct29` | Bay Islands | 2017-10-29 11:37 |
| `meria_ghana_2018_oct18_24` | Ghana | 2018-10-18 18:17, 2018-10-24 18:17 |
| `meria_ghana_2018_oct25_31` | Ghana | 2018-10-25 18:09, 2018-10-31 18:09 |
| `meria_ghana_2018_oct30_nov05` | Ghana | 2018-10-30 18:17, 2018-11-05 18:17 |
| `meria_16pcc_2018_oct25` | 16PCC | 2018-10-25 00:06 |

The Ghana pairs follow the same MERIA optical observation before and after the
SAR acquisitions: 18/24 October (`57bbff03`), 25/31 October (`cd77705c`), and
30 October/5 November (`91ea9edc`). Other observations may also refer to one of
those acquisitions. This establishes common observation context and matching
AOI coverage in the MERIA table; inspect valid raster pixels in QGIS before
using individual points as SAR evidence.

## Process the remaining MERIA global acquisitions on Skua

The supplied Skua manifest listing from 2026-10-05 showed all 14 SA acquisitions
processed, 4 of the 11 legacy MERIA global acquisitions processed, and the 16PCC
2018-10-25 00:06 acquisition processed. Verify live status again before running.
After this code is pushed, in the server checkout:

```bash
cd ~/students/Joshua/src/Masters
git pull --ff-only
cd sar_server_pipeline

SAR_DATA=$(sudo docker compose config --format json | python3 -c 'import json,sys; print(next(v["source"] for v in json.load(sys.stdin)["services"]["pipeline"]["volumes"] if v["target"] == "/data"))')
SAR_JOBS=$(sudo docker compose config --format json | python3 -c 'import json,sys; print(next(v["source"] for v in json.load(sys.stdin)["services"]["pipeline"]["volumes"] if v["target"] == "/job"))')

sudo install -m 0644 \
  ../Data_Creation/meria_global_s1_slc/MERIA_global_plastic_nearest_S1_SLC_before_after.csv \
  ../Data_Creation/meria_global_s1_slc/MERIA_global_plastic_points.csv \
  "$SAR_DATA/raw/"

sed 's/^run_id:.*/run_id: meria-global-11-20261006/' \
  jobs/global_all_unique_full_scenes.yaml |
  sudo tee "$SAR_JOBS/meria_global_11_20261006.yaml" >/dev/null

sudo docker compose build pipeline digitising
sudo docker compose run --rm pipeline slc_process \
  --manifest /job/meria_global_11_20261006.yaml
```

The new run ID avoids an old successful stage marker skipping the updated
processing pass. The processor's `force` option remains off. Do not use the
116-scene `global_s1_slc_job.yaml` for this focused run.

## Prepare one area/date batch

After the required acquisitions have processed manifests and rasters, prepare
**one named batch at a time**:

```bash
BATCH=sa_durban_2019_apr21_27  # replace with a batch name in the register
sudo docker compose run --rm digitising prepare-meria \
  --batch "$BATCH" --prediction-mode auto --dry-run
sudo docker compose run --rm digitising prepare-meria \
  --batch "$BATCH" --prediction-mode auto
```

`prepare-meria` selects one task for each specified acquisition; scene
preparation includes its other MERIA optical relationships automatically.
It fails if an acquisition is not present in the processed scene catalogue.
The `meria_global` selector reads the focused MERIA global match table and
candidate-point CSV, and includes documented partial-coverage legacy matches.
It excludes MARIDA and Jamila tasks. `--prediction-mode auto` may retrieve
forcing data; use `cached-only` if preparation must stay offline.

To prepare all 17 batches after the processing pass, use this list. Each
iteration writes its own batch directory and project; it never combines areas
or acquisition weeks:

```bash
for BATCH in \
  sa_durban_2019_apr21_27 sa_durban_2022_apr05 \
  sa_durban_2022_apr17_20 sa_durban_2022_apr27 \
  sa_east_london_2024_jun03 sa_east_london_2024_jun10_15 \
  sa_gqeberha_2024_jun08 sa_gqeberha_2024_jun20 \
  sa_gqeberha_2026_may05_10 meria_palma_2018_oct12 \
  meria_honduras_2017_oct05 meria_honduras_2017_oct17 \
  meria_honduras_2017_oct29 meria_ghana_2018_oct18_24 \
  meria_ghana_2018_oct25_31 meria_ghana_2018_oct30_nov05 \
  meria_16pcc_2018_oct25; do
  sudo docker compose run --rm digitising prepare-meria \
    --batch "$BATCH" --prediction-mode auto || break
done
```

The 85 manual Sentinel-2 points are candidate, unverified debris. They are
drift search seeds and QGIS references, not confirmed plastic polygons. The
16PCC batch uses the processed 2018-10-25 00:06 SAR acquisition.

## Transfer that batch from Skua to the Ubuntu staging machine

On Ubuntu, first run the `pull_command` printed by `prepare-meria` with `-nP`
added to preview size, then run the exact printed command. It uses the
generated `transfer_files.txt` and copies only that batch's project, scene
GeoPackages, reference layers, manifests and SAR rasters. Move the complete
batch directory to `D:\Joshua` before opening its `batch.qgz` in QGIS.
