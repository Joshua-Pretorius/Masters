# SA May 2026 processing update

Prepared locally on 26 October 2026. Skua has not been contacted.

SAR cutoffs: Gqeberha 5 May 2026 inclusive; Ku Gompo 7 May 2026 inclusive.
Optical dates remain 8, 9 and 25 May for Gqeberha and 9 May for Ku Gompo.
Times of optical observations were not supplied; dates use the existing full UTC-day convention. Optical candidates are search aids, not SAR ground truth.

183 unique points: MERIA_SA_010 (28), MERIA_SA_011 (105), MERIA_SA_012 (33), MERIA_SA_013 (17).
The repeated 25 May line and two repeated 9 May points are retained in the raw source/GeoJSON but deduplicated in the processing CSV. The incomplete 34.08830 S coordinate has no longitude and is excluded.

The nearest partial-coverage scenes are retained alongside the nearest full-coverage scenes. Gqeberha: 5/10 May and 22/29 May. Ku Gompo: 7/12 May. Coverage refers to the existing 15 km buffered-point AOI, not a measured debris extent. See selections.json and the saved Copernicus catalogue responses.

## Transfer
Copy this entire folder via your usual laptop/Drive route to:
~/students/Joshua/src/Masters/sar_server_pipeline/jobs/sa_may_2026_update

## Run on Skua
From the sar_server_pipeline checkout, run:

```bash
bash jobs/sa_may_2026_update/run_on_skua.sh
```

The script validates every requested scene against the cutoff, then starts the existing full-swath IW1/IW2/IW3 processing job. It uses the job-local CSVs, one worker and 32 GB SNAP cache. Patch extraction and stacking remain disabled until annotation review. Existing completed outputs can be reused by the processor; the two 5/10 May targets retain their existing MERIA_SA_009 identifiers. This does not establish that these outputs currently exist on Skua.

After installing locally, for later digitising also synchronise the updated repository Data_Creation/meria_sa_plastic_s1_slc CSVs and sar_server_pipeline/digitising/meria_batches.py. The processing job itself needs no code changes or image rebuild. Never replace a newer server catalogue blindly; these are complete local catalogue snapshots.

## Local installation completed
Installed into D:/Masters on 26 October 2026. Original workbook, CSVs, batch registry and affected inventory-count tests are backed up in D:/Masters/outputs/sa_may_2026_backup_20261026_100106.

All four local test_meria_batches.py tests passed. Installed input validation passed for six unique SAR scenes, the event cutoffs and 183 new points. Skua processing has not been run or remotely inspected.

The normal processing job is self-contained in this folder. For later digitising, repository_updates contains the updated CSVs and batch registry, arranged relative to the Masters repository root. Review and merge these on the server before digitising if the server copies have independent changes.

## Broader temporal search
The public Copernicus query was broadened from IW dual-polarisation SLC to all SLC modes. Additional Gqeberha entries include WV single-VV products on 8 and 27 May. These are not compatible with the normal IW1/IW2/IW3 VV/VH pipeline; point-level vignette coverage has not been established. Ku Gompo returned no additional SLC products. The selected dates are the closest before/after acquisitions among the returned compatible products, subject to the event cutoffs. No claim is made about other sensors or GRD-only alternatives.
