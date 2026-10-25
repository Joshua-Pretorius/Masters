# Obtain Sentinel-1 instrument noise metadata

Use the exact product list in metadata_requests.csv. These source ZIP paths come from the existing processing manifests; /data/... paths refer to the processing container and have not been checked on the server.

The original SAFE product contains the needed small files:

- manifest.safe
- annotation/*.xml (geolocation, geometry, processing flags)
- annotation/calibration/noise-*.xml
- annotation/calibration/calibration-*.xml

Run collect_noise_metadata.py wherever the original ZIPs or SAFE directories already exist. Keep metadata_requests.csv beside the script, or pass --requests explicitly. Example:

    python collect_noise_metadata.py --product-root PATH_TO_EXISTING_PRODUCTS --output sentinel1_noise_metadata

This command only reads existing products and writes small metadata files. It skips the large measurement TIFFs and creates collection_inventory.json recording missing/collected products. The collector was tested with a small fixture to confirm this behaviour. It does not connect to any remote computer.

If the original products are unavailable, obtain the same annotation/calibration members from the matching Sentinel-1 product at Copernicus Data Space or ASF, using the provider's authenticated download method as required. The complete imagery does not need to be transferred if product-member access is available.

To create calibrated noise-equivalent sigma-zero (NESZ), combine the noise power LUT with the corresponding sigma-zero calibration LUT, interpolate in the original product coordinates, and propagate through the same split/deburst/geocoding workflow. Product specification: https://sentinels.copernicus.eu/documents/247904/1877131/Sentinel-1-Product-Specification-18052021.pdf

Check thermalNoiseCorrectionPerformed and actual processing history first. Do not subtract the noise again from already corrected imagery. The currently checked-in SNAP graphs have no explicit ThermalNoiseRemoval node; that alone does not verify the history of every exported raster.

The legacy Manila raster's exact original processing product must be confirmed before applying SLC calibration vectors to it. Matching acquisition time is sufficient for exploratory observation alignment, but does not make SLC and legacy calibration/noise LUTs interchangeable.

A real retained Durban SNAP noise/calibration example is saved in retained_Durban_SNAP_metadata.xml. It is SNAP metadata, not a NESZ raster; that IW1 intermediate does not cover the digitised Durban plastic footprints.

Current instrument-noise maps: not generated. Current roughness maps estimate environmental sea clutter from labelled water.
