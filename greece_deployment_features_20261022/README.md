# Greece controlled-deployment feature analysis

The supplied deployment footprints can be made more distinct from the labelled water using scene-specific combinations of SAR features. Separation is strongest on 29 June 2024. A single transferable signature has not been established: leaving each acquisition out gives inconsistent results, and adding the coarse environmental interactions did not improve the average held-out ranking.

Open REPORT.html for the full illustrated report, then Greece_2021_feature_analysis.qgz or Greece_2024_feature_analysis.qgz in QGIS. Toggle one map at a time. Scene-fitted maps are exploratory; held-out maps show transfer to an acquisition not used to fit that model.

- Extracted 10 SAR layers for 58 core deployment pixels and 4,487 water pixels across four acquisitions. Boundary pixels and coverage fractions are retained separately.
- Added 8 SAR feature transforms/interactions, PCA, regularized logistic hyperplanes, shrinkage LDA, seven SAR-environment interaction indices and held-out environmental scores.
- Retrieved environmental layers only: wind, waves, currents, near-surface temperature and chlorophyll. Native marine grids are about 4 km and the nearest valid ocean cell is 8.4 km away. These fields describe regional context.
- Original data and batch projects were not edited. Outputs retain exact native SAR grids.

## Main results

       Acquisition UTC  Deployment pixels  Water pixels  Scene-fit AUC  Scene-fit AUC vs nearer water  Held-out AUC
26 Jun 2021, 16:15 UTC                 19          1129          0.920                          0.708         0.746
02 Jul 2021, 16:15 UTC                 21          1123          0.925                          0.817         0.543
29 Jun 2024, 04:15 UTC                  8          1125          0.987                          1.000         0.531
05 Jul 2024, 16:07 UTC                 10          1110          0.873                          0.871         0.524

Scene-fit AUC describes the same labels used to fit the model and is not independent accuracy. Nearer-water AUC uses water polygons 2 and 4. Cross-scene tests are inconsistent; environmental interactions and independent-water calibration do not establish a stable transferable plastic signature.

## Reproduce

Run the Python scripts with .venv/Scripts/python.exe in this order: extract_sar.py, fetch_wind.py, describe_environment.py, fetch_marine.py, assemble_environment.py, analyse_features.py, water_calibrated_analysis.py, make_figures.py, verify_outputs.py. Then run build_qgis_projects.py using the installed QGIS Python batch launcher. Paths are configured in the scripts. Source downloads reuse the user's existing Copernicus credentials and do not store them in this output folder.
