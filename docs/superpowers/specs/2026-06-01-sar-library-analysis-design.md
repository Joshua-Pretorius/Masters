# SAR Library Analysis Design

## Goal

Build a first-pass analysis pack for the SAR patch library that:

- creates descriptive graphics for all valid `plastic` samples
- creates Ghana-only class-separation graphics across `plastic`, `ship`, `wake`, `slick`, and `calm_water`
- ranks which summary SAR features separate Ghana `plastic` from non-plastic classes best
- writes figures, tables, and a short run note under:
  - `D:\Masters\Data_Creation\Library\Analysis`

## Scope

This stage consumes the existing library outputs already created under:

- `D:\Masters\Data_Creation\Library\sar_patch_inventory.csv`
- `D:\Masters\Data_Creation\Library\sar_patch_library.csv`
- `D:\Masters\Data_Creation\Patches\...`

It does not create new SAR patches. It only analyzes the current extracted patch library.

## Current Data Reality

The current library contains a mix of usable and unusable rows for numeric analysis.

### Valid current use cases

- Ghana contains usable multi-class samples with valid summary features
- plastic samples exist across Palma and Ghana

### Known limitation

Some Palma plastic rows currently have `NaN` summary statistics, so the analysis stage must filter to rows with valid numeric feature values before plotting or ranking.

This means:

- descriptive plastic graphics use all valid plastic rows from every scene
- Ghana class-separation and feature-importance analysis use Ghana rows with valid features only

## Output Folder

All outputs go to:

- `D:\Masters\Data_Creation\Library\Analysis`

The stage will create the folder if it does not exist.

## Plastic Descriptive Graphics

These graphics are descriptive only. They must not make class-separation claims.

### Figures

- `plastic_feature_distributions.png`
  - small-multiple histograms for selected SAR summary features
- `plastic_feature_boxplots.png`
  - boxplots for the same selected features
- `plastic_patch_montage.png`
  - a montage of representative plastic patch thumbnails

### Sidecar table

- `plastic_patch_montage_examples.csv`
  - one row per thumbnail used in the montage
  - includes sample id, image path, scene id, class label, and any sampling note if needed

## Ghana Class-Separation Graphics

These graphics use Ghana rows only and are intended to inspect separability between plastic and the other manually labeled classes.

### Ghana classes

- `plastic`
- `ship`
- `wake`
- `slick`
- `calm_water`

### Figures

- `ghana_class_counts.png`
  - class count bar chart
- `ghana_feature_boxplots_by_class.png`
  - feature-by-class boxplots for a focused subset of useful features
- `ghana_feature_pairplot_subset.png`
  - pairwise scatter or density views for a small subset of high-signal features
- `ghana_plastic_vs_other_violinplots.png`
  - one-vs-rest comparisons for plastic against all non-plastic Ghana classes

## Feature-Importance Analysis

Feature-importance analysis is Ghana-only and uses the summary-feature library, not raw pixels.

### Primary task

Rank which SAR summary features best separate:

- `plastic`
- `other` where `other = ship + wake + slick + calm_water`

### Methods

Use two complementary rankings.

#### 1. Random forest importance

- train a simple `plastic` vs `other` random forest on Ghana rows with valid features
- use class labels from `normalized_class_label`
- save ranked importances

#### 2. Univariate separability score

- compute an interpretable per-feature separation score
- use absolute standardized mean difference or an equivalent simple effect-size metric

These two rankings will be saved side by side so model-based and univariate signals can be compared.

### Outputs

- `ghana_plastic_vs_other_feature_importance.csv`
- `ghana_plastic_vs_other_feature_importance.png`

## Feature Set For Analysis

The analysis stage must work from the existing summary-feature columns in `sar_patch_library.csv`.

Candidate feature families:

- `vv_db_*`
- `vh_db_*`
- `vv_vh_ratio_db_*`
- `vv_minus_vh_db_*`
- `vv_glcm_mean_*`
- `vv_glcm_std_*`
- `vv_glcm_entropy_*`
- `decomp_entropy_*`
- `decomp_anisotropy_*`
- `decomp_alpha_*`

The stage will not use every statistic blindly for every graphic. It will select a compact numeric subset for readable figures while still ranking the full valid feature set for importance.

## Data Filtering Rules

### General validity

- only use rows where `extraction_status == ok`
- only use rows with non-null numeric values for the required analysis features

### Plastic descriptive graphics

- filter to `normalized_class_label == plastic`
- include all scenes
- drop rows with invalid numeric features from the distribution plots
- allow montage sampling from available patch image paths

### Ghana class-separation analysis

- filter to rows where `scene_id == before_20181030T181758`
- keep the five Ghana classes listed above
- exclude rows missing required feature values

## Thumbnail Montage Rules

The montage will be easy to inspect rather than exhaustive.

- select a limited number of representative plastic patches
- read the generated patch images from `D:\Masters\Data_Creation\Patches`
- render a simple visualization from a chosen subset of bands suitable for human viewing

For V1, the montage can use a single grayscale display band such as `vv_db`, or a simple RGB-style composite if that is straightforward and stable.

## Run Note

Write a short markdown summary file:

- `analysis_run_note.md`

It will include:

- date of run
- source CSV paths
- row counts used for plastic descriptive graphics
- row counts used for Ghana class-separation analysis
- classes included
- features analyzed
- any dropped-row counts due to invalid numeric values

## Error Handling

The analysis stage must be resilient to sparse data.

### Required behavior

- skip plots that cannot be generated due to insufficient valid rows
- record the skip reason in `analysis_run_note.md`
- continue generating the rest of the pack

### Examples

- if pairplots are too sparse, skip the pairplot and keep the other graphics
- if a feature is entirely null after filtering, exclude it from plotting and ranking

## Testing Strategy

Tests must cover the analysis logic with small synthetic CSV fixtures.

Core tests:

- load the library CSV and filter to valid rows correctly
- select all valid plastic rows across scenes
- select Ghana-only rows and class labels correctly
- compute one-vs-rest labels for Ghana plastic vs other
- generate feature-importance tables in the expected shape
- write outputs into `Library\Analysis`
- handle insufficient-data conditions without crashing

Tests do not need to validate visual aesthetics. They must validate that the expected files and tables are produced, and that filtering and ranking logic are correct.

## Implementation Shape

Add a new script under `D:\Masters\Data_Creation` for analysis generation, with focused helpers for:

- CSV loading
- row filtering
- feature selection
- plastic montage sampling
- descriptive plotting
- Ghana class-separation plotting
- feature-importance computation
- run-note writing

This keeps the analysis stage separate from patch extraction while still building directly on the current library outputs.

## Frozen V1 Decisions

- plastic graphics are descriptive only
- class-separation analysis is Ghana-only
- feature importance is Ghana `plastic` vs `other`
- use summary-feature columns, not raw-pixel modeling
- write all outputs to `Library\Analysis`

## Out Of Scope For V1

- interactive dashboards
- notebook-first workflow
- cross-scene domain generalization claims
- training a production classifier from this analysis stage
- deep model explainability on ResNet or U-Net outputs
