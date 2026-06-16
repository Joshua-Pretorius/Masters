# Weekly Plan: Manual SAR Dataset V1 and Drift Follow-up

**Summary**
- Goal: produce a clean, repeatable `v1` manual dataset pipeline that starts from optical-linked SLC scenes and ends with a small patch dataset, extracted feature/dictionary tables, and two model smoke tests: classification and segmentation.
- Plan document target: `Writing/codexnotes/2026-05-23-sar-dataset-week-plan.md`
- This week prioritizes manual label creation and dataset specification first; drift is evaluated only after the first dataset dry run is complete.

## Implementation Changes

### 1. Freeze the scene set and annotation standard
- Use the currently processed MERIA SLC scenes as the week-1 corpus; exclude scenes that are only `prepared`.
- Annotate three classes: `plastic_patch`, `ship_false_positive`, and `open_ocean`.
- Store annotations as `polygon + confidence + notes` in one master geospatial file with stable IDs.
- Confidence levels are `high`, `medium`, and `low`; only `high` and `medium` feed the first dry runs by default.

### 2. Build the repeatable extraction pipeline
- For each polygon, extract scene metadata, class label, confidence, scene time, optical-to-SAR time gap, and local environmental values sampled per patch.
- Extract geometry metrics: area, perimeter, major/minor axis, aspect ratio, orientation, compactness, and bounding-box size in meters and pixels.
- Extract SAR summaries from the existing stack: `vv`, `vh`, `vv_refined_lee`, `vv_glcm_mean`, `vv_glcm_std`, `vv_glcm_entropy`, `decomp_entropy`, `decomp_anisotropy`, and `decomp_alpha`.
- Keep raw physical values in the master dictionary.
- Add derived columns separately for analysis: `vv_db`, `vh_db`, `vv_minus_vh_db`, `vv_div_vh`, and one or more experimental SAR debris-index candidates.
- Save outputs as a patch dictionary table, a feature table, and a linked patch manifest.

### 3. Let the dictionary determine patch policy
- Do not hard-code the final patch size before digitizing.
- Compute object-size statistics from the manual polygons first, then evaluate fixed patch candidates of `128`, `256`, and `512` pixels.
- Choose the smallest fixed patch size that covers at least `95%` of annotated polygons when each polygon bounding box is expanded by a `2x` context margin.
- Save the acceptance and failure counts so the patch-size choice is reproducible.
- After the fixed size is chosen, generate model patches from the stacked SAR data and attach local environmental channels or tabular context.

### 4. Run the two dry runs in sequence
- First dry run: patch classification on `plastic_patch` vs `ship_false_positive` vs `open_ocean` to validate dataset cleanliness and separability.
- Second dry run: lightweight segmentation smoke test using polygon-derived masks on the same fixed patch size.
- For both runs, compute normalization from the training split only.
- Image normalization uses per-channel mean/std from the training split.
- Tabular feature normalization uses training-split scaling only.
- Treat the SAR debris index as experimental: use it as a feature and as a digitizing aid, not as the only detector.

### 5. Evaluate drift after the manual dataset pass
- Run the drift submodule on the same annotated cases only after `v1` dataset assembly and the dry runs are complete.
- Compare drifted candidate regions against the manual SAR polygons to measure whether drift narrows the search space usefully.
- Tune windage, landmask, and forcing choices only after that comparison.
- Judge drift on annotation utility: overlap, search-area reduction, and missed-target risk.

## Interfaces and Data Contracts
- Annotation master file: one polygon per labeled region with `annotation_id`, `scene_id`, `obs_id`, `class_name`, `confidence`, `source_type`, `notes`, and geometry.
- Patch dictionary: one record per extracted patch with `patch_id`, `annotation_id`, chosen patch size, center coordinates, pixel window, split assignment, and linked raster paths.
- Feature table: one record per patch/object with raw SAR stats, derived SAR features, environmental patch stats, geometry stats, and nullable drift metadata for the later phase.
- Classification labels are 3-class IDs.
- Segmentation labels are masks rasterized from the same polygon source.

## Test Plan
- Annotation QA: verify class balance, unique IDs, valid CRS, non-empty geometries, and no orphan records.
- Extraction QA: verify every dictionary row links to an annotation and every feature row links to a patch.
- Patch-sizing QA: verify the selected fixed size satisfies the `95%` coverage rule and record failures explicitly.
- Normalization QA: confirm no train/val/test leakage in image stats or feature scalers.
- Classification smoke test: full training loop runs, loss decreases, and performance is better than chance on held-out data.
- Segmentation smoke test: masks rasterize correctly, full training loop runs, and at least some plastic polygons achieve non-zero IoU.
- Drift evaluation: measure polygon overlap or centroid distance between manual SAR polygons and drifted outputs on the same scenes.


