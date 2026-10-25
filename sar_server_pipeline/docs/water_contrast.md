# Four signed water-relative SAR views

`digitising prepare` adds four initially unchecked layers directly inside each
physical acquisition's **SAR rasters** group:

1. Refined Lee VV | signed contrast (dB)
2. VV 30 m patch | signed contrast (dB)
3. VH 30 m patch | signed contrast (dB)
4. VV 60 m patch | signed contrast (dB)

Original SAR, optical evidence and editable annotations remain available. These
are continuous visual aids, not debris labels, CFAR detections or probabilities.
Instrument noise/NESZ reliability, particularly for VH, remains unassessed.

## Coverage

For each acquisition, collect its linked optical reference points (including AOI
context points for coverage only) and available predicted points. Keep points
whose locations have positive, valid VV samples on that acquisition. Connect
them with a convex hull in a local azimuthal equidistant metric CRS; buffer the
hull by **100,000 metres**; intersect with the existing raster bounds. One point
produces a buffered point; two produce a buffered line. Clip output cell centres
to that polygon and retain source NoData inside it. No SAR is downloaded.

This is an approximate local metric buffer, not 100 km added to latitude/longitude
coordinates. The calculation retains the native raster grid and uses a halo
outside the coverage polygon, so background statistics are not artificially cut
off at the coverage boundary. Source extent and source validity remain limits.
Desktop migration additionally includes vertices of explicitly named controlled
deployment polygons. These define coverage only, never contrast values or tuning.

## Fixed calculations

Filtered VV contrast = existing Refined Lee VV pixel in dB minus arithmetic mean
filtered VV dB in a rectangular surrounding ring (outer nominal half-width 150 m,
excluded central half-width 50 m). No additional Refined Lee filtering is run.

Patch contrast = `10*log10(mean(linear intensity in patch) /
mean(linear intensity in surrounding water ring))`. Use original calibrated VV
or VH intensity. Nominal patch full-widths are 30 and 60 m; the common background
ring has outer half-width 300 m and excluded central half-width 100 m. Averaging
linear intensity before conversion to dB differs from averaging dB values.

Metre sizes are rounded to odd pixel dimensions using native spacing at the
coverage-window midpoint: `2*max(1, round(half_width / pixel_spacing)) + 1`.
The resulting actual footprints are recorded, not assumed equal to their labels.
For the MARIDA 18QYG grid, patches are 3x3 and 5x5 pixels, approximately 40x42 m
and 66x70 m. Geographic-grid metre widths vary across large scenes; nominal metre
windows are fixed in pixels within each output, not dynamically resampled.

Water eligibility is ESA WorldCover 2021 v200 class 80, nearest-neighbour aligned
to the SAR grid, more than 30 m from nonwater/unknown. This static map is not an
acquisition-specific clean-water classifier. It can include slicks, ships, wakes
or fronts. WorldCover COG windows are retrieved over HTTPS; no Skua connection
is part of this code. Confirmed missing WorldCover tiles remain unknown; other
network failures fail the run rather than silently inventing water.

Rings need at least 70% eligible valid cells and at least 30 cells. Central
patches need at least 90% and four cells. The central cell must itself be eligible
and valid. Unsupported results are NaN/NoData. Both signs are retained. Display
is fixed blue/white/red at -6/0/+6 dB; stored values are not clipped. Continuous
overviews use averaging; inspect the native grid for annotation boundaries.

## Reproducibility and transfer

Outputs live in `<scene directory>/water_contrast_v1/`:

- `water_contrast.tif`: four Float32 bands, native grid, compressed and tiled.
- `water_contrast.json`: method, input file identities, points, grid/window sizes,
  valid counts and WorldCover source provenance.
- `coverage.geojson`: actual buffered, source-clipped processing polygon.

The transfer manifest includes all three. QGIS uses the multiband GeoTIFF directly
with portable relative paths, avoiding absolute-path VRT dependencies. Fingerprints
include source sizes/mtimes, paths, point coordinates and method settings. Matching
completed results are reused; partial files are not. Writes use a temporary raster
and completion sidecar. Missing SAR inputs or no on-image points are logged as
unavailable, never substituted with another acquisition or polarization.

After pulling this code on the server, rebuild the existing image before the next
normal preparation command (the Dockerfile copies the Python package):

```sh
cd sar_server_pipeline
docker compose build digitising
# Then run your usual docker compose run --rm digitising prepare ... command.
```

The local implementation was not deployed or run on Skua. Preparation may take
substantially longer because a 100 km buffer can cover most of an acquisition.
Allow storage for up to four Float32 bands plus overviews over the clipped extent.

For existing desktop projects, `tools/install_water_contrast.py` installs completed
outputs from an inventory/results JSON pair, removes the superseded `Area | filtered,
patch and VV-VH views v1` and `Signed water-relative SAR | fixed v1` groups, and
creates timestamped project backups. It leaves old derived files in place so the
backups remain usable. It refuses to overwrite a concurrently changed project
and checks original sources/visibility plus new-layer validity after saving.

WorldCover: ESA WorldCover 2021 v200, DOI 10.5281/zenodo.7254221, CC BY 4.0.
