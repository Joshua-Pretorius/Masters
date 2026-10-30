# Annotation classes

Digitising prepare exposes these `Class` values for task and scene annotation
polygons: `plastic`, `ship`, `wake`, `slick`, `calm_water`, `open_ocean`, `other`,
`uncertain`, `reef`, and `rain`. Import validation uses the same list.

`reef` denotes an annotation interpreted as a reef-related feature; `rain`
denotes an annotation interpreted as a rain-related SAR signature. These are
reviewer-assigned classes, not automatic detections. Existing confidence and
training-status fields still apply.

Existing local projects can be updated with QGIS Python using
`tools/add_local_annotation_classes.py --root D:\Joshua --report <report.json>`.
This adds the two choices and renderer categories without changing annotation
features, existing class values, or other form settings. Original projects are
backed up before replacement. Reopen projects after migration. Future server
preparation uses the additions after the updated code is deployed there.
