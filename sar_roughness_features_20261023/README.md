# Roughness-controlled plastic reference analysis

Open REPORT.html for the full results and limitations. Start in All_locations_roughness_analysis.qgz, or the Greece_2021 / Greece_2024 projects.

The second pass uses a water-only environmental backscatter baseline, a 1.5x controlled-deployment multiplier, and all locally matched digitised plastic observations. There are 9 acquisitions, 98 scene/polygon records and 43,937 sampled pixels.

Main result: common-feature event-held-out object-balanced AUC increases modestly from 0.537 to 0.567. New-location transfer remains weak. Local fitted maps are useful exploratory views, not independent evidence of a transferable detector.

Instrument noise has not been estimated: see instrument_noise/README.md and metadata_requests.csv for the required SAFE files and the tested metadata-only collector.

Source data and original batch projects were not edited.

Reproduction order: inventory_sources.py, describe_global_environment.py, fetch_environment.py, fetch_wind_grids.py, expand_scotland_environment.py, extract_features.py, environment_lookup.py, model_roughness.py, model_rich_SLC.py, export_figures.py, verify_outputs.py, build_qgis_projects.py. Most scripts use the Python environment from the previous Greece analysis; QGIS packaging uses installed QGIS Python. ROOT and source paths are configured in the scripts.
