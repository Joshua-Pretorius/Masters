# MIREIA - Marine litter signatures in SAR Images patch report

- Generated: `2026-04-12T19:52:12Z`
- Input JSON: `/mnt/d/Masters/ocean-scan-mireia-- marine litter signatures in sar images-e71e8ee6-e41d-4889-bb08-a821fb5e8bbd.json`
- GeoJSON: `/mnt/d/Masters/Scripts/ocean_scan_mireia_patches.geojson`
- CSV: `/mnt/d/Masters/Scripts/ocean_scan_mireia_planet_requests.csv`
- Total observations in source JSON: `42`
- Polygon patches exported: `41`
- Non-patch / skipped observations: `1`
- Planet nearest acquisitions resolved live: `0`

## Notes

- Patch export includes only polygon observations with `class=PATCH` and `isAbsence=false`.
- Planet matching is defined here as the `PSScene` acquisition with the smallest absolute time delta to each patch timestamp, constrained to scenes intersecting the patch polygon.
- Progressive search windows used by the resolver: `12`, `24`, `72`, `168`, `720` hours.
- No Planet API key was available while generating this report, so item IDs remain unresolved and the API calls below are ready-to-run templates once `PL_API_KEY` is set.
- Planet docs referenced for these calls: Data API item search, items/assets, and Orders API mechanics/reference.

## Summary

| Patch | Obs ID | Timestamp (UTC) | Centroid (lon, lat) | Est. area m2 | Planet status | Planet item | Acquired | Delta h |
| --- | --- | --- | --- | ---: | --- | --- | --- | ---: |
| 001 | 6ec629af-9109-48b3-99f4-9ca1efcc30ab | 2021-10-03T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 002 | 449a475a-64e0-4c90-8aeb-4e6ca82b80f4 | 2021-09-08T04:54:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 003 | 3f6da35f-cc98-4cc4-92bd-3408b9b6b92c | 2021-07-30T16:32:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 004 | 498c8221-d14c-44a8-bdf1-8acbfcf9216a | 2021-07-23T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 005 | 3fe3a9a3-0f18-4430-8e34-0cd262ea6389 | 2021-06-28T04:54:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 006 | 23a2adda-7b5e-4c11-a392-f1757520cd2d | 2021-06-05T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 007 | b1fffddd-b2c2-4e5c-8698-644305b09e38 | 2021-05-24T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 008 | 2dee6f8f-db40-4f97-b257-c4aa9517515b | 2021-05-19T16:32:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 009 | adf9a7c0-542a-40a6-a2ec-4cf93f4215d2 | 2021-05-11T04:54:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 010 | c8263fd7-91b0-4222-be30-11736117f07c | 2021-05-06T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 011 | 286d2418-88c0-464e-802b-d4eb34fd5143 | 2021-04-24T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 012 | c302e883-209b-49ac-b17f-b509c06795a9 | 2021-10-03T04:47:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 013 | 76ec6bf4-6b5f-437a-9d4f-aebec8b2ce73 | 2021-09-26T04:55:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 014 | f53d1aa7-19f3-47e2-8b67-5326a447b879 | 2021-07-28T04:55:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 015 | 6fbcd469-5998-4ef4-b544-6497d27540f9 | 2021-07-23T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 016 | 141ddc5d-7ab9-4a52-8479-fb363dbf2705 | 2021-06-23T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 017 | 2dd31802-297e-445f-bb86-85630d090d18 | 2021-06-05T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 018 | 8e2bbf02-61ec-452c-9fc6-4ce9f4c9491a | 2021-05-29T04:55:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 019 | f521a4f4-dd63-499b-a8e5-cd0db7e57ba4 | 2021-05-24T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 020 | 7179555b-d477-4799-a8d8-4be28c2ff685 | 2021-05-06T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 021 | 05e9c78d-fa17-4609-aa3d-5c9870b5722b | 2021-04-24T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 022 | 47547a65-11f0-4540-93fb-227bad49ae81 | 2021-04-06T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 023 | 8fe3676d-b164-410b-a7d0-a77bc42d63c9 | 2021-04-01T16:32:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 024 | c8e7893a-792a-49ae-920e-d3b64bf802a4 | 2021-03-25T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 025 | 155c2d7d-110e-4041-a86b-8ad8d33aba1c | 2021-03-07T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 026 | da4bfb13-c625-4655-a1ad-101af28758e0 | 2021-02-23T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 027 | 986cb23b-f7b6-49a1-8c5e-f27c4c6657aa | 2021-01-24T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 028 | d39f4713-cafa-43a8-9e58-83627e5fa0f8 | 2021-01-19T16:32:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 029 | 54583c6f-d50f-4fe8-9c17-6c84ffee527b | 2021-04-06T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 030 | a7d17cd3-59d4-45bf-a066-94a4084ca96f | 2021-03-25T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 031 | e584367d-62d7-496b-acd1-75b6df6a00d9 | 2021-03-07T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 032 | a9f8f202-d131-4cde-a088-794725748715 | 2021-02-23T16:41:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 033 | 6e869537-def1-4fae-963a-018a6b2c741f | 2021-01-24T04:46:00.000Z | 19.287395, 43.759150 | 118299.163 | unresolved_no_api_key |  |  |  |
| 034 | 9e17ce98-9eeb-40f6-989e-894dc2be72ea | 2017-10-12T23:57:00.000Z | -86.691666, 16.016666 | 13234762.070 | unresolved_no_api_key |  |  |  |
| 035 | 33a32832-fc41-4fdd-8c91-a41844fc1709 | 2017-10-17T11:37:00.000Z | -86.391666, 16.025000 | 9925607.631 | unresolved_no_api_key |  |  |  |
| 036 | 86a3fb61-9db1-4df5-82ae-a848e0455a2e | 2020-07-04T23:57:00.000Z | 130.558334, 32.608334 | 2899761.360 | unresolved_no_api_key |  |  |  |
| 037 | 91ea9edc-67b4-4211-8532-35deec4a3148 | 2018-10-31T18:17:58.000Z | -0.219745, 5.495525 | 1246225.823 | unresolved_no_api_key |  |  |  |
| 038 | 05e7c3bc-2eac-4c4b-ba8a-6bf8aa4c0789 | 2018-10-12T12:00:00.000Z | 3.468853, 39.607096 | 57694879.709 | unresolved_no_api_key |  |  |  |
| 039 | 3f181238-1180-4e8f-bd9e-90daa87aa6ca | 2018-10-11T12:00:00.000Z | 3.468983, 39.607120 | 57848731.175 | unresolved_no_api_key |  |  |  |
| 040 | 7599355c-419f-4f5b-913b-22b769ee25d2 | 2018-10-11T12:00:00.000Z | 3.468862, 39.607108 | 57848732.523 | unresolved_no_api_key |  |  |  |
| 041 | cabcd011-9d82-4124-9f9c-120bdc406cf3 | 2018-10-12T12:00:00.000Z | 3.468348, 39.602787 | 67944025.663 | unresolved_no_api_key |  |  |  |

## Per-patch Details

### Patch 001

- Observation ID: `6ec629af-9109-48b3-99f4-9ca1efcc30ab`
- Source ID: `S1B_20211003T1641`
- Timestamp (UTC): `2021-10-03T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-09-03T16:41:00Z","lte":"2021-11-02T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_001_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_001_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_001_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_001","source_type":"scenes","products":[{"item_ids":["PATCH_001_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 002

- Observation ID: `449a475a-64e0-4c90-8aeb-4e6ca82b80f4`
- Source ID: `S1B_20210908T0454`
- Timestamp (UTC): `2021-09-08T04:54:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-08-09T04:54:00Z","lte":"2021-10-08T04:54:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_002_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_002_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_002_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_002","source_type":"scenes","products":[{"item_ids":["PATCH_002_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 003

- Observation ID: `3f6da35f-cc98-4cc4-92bd-3408b9b6b92c`
- Source ID: `S1B_20210730T1632`
- Timestamp (UTC): `2021-07-30T16:32:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-06-30T16:32:00Z","lte":"2021-08-29T16:32:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_003_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_003_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_003_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_003","source_type":"scenes","products":[{"item_ids":["PATCH_003_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 004

- Observation ID: `498c8221-d14c-44a8-bdf1-8acbfcf9216a`
- Source ID: `S1B_20210723T1641`
- Timestamp (UTC): `2021-07-23T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-06-23T16:41:00Z","lte":"2021-08-22T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_004_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_004_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_004_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_004","source_type":"scenes","products":[{"item_ids":["PATCH_004_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 005

- Observation ID: `3fe3a9a3-0f18-4430-8e34-0cd262ea6389`
- Source ID: `S1B_20210628T0454`
- Timestamp (UTC): `2021-06-28T04:54:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-05-29T04:54:00Z","lte":"2021-07-28T04:54:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_005_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_005_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_005_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_005","source_type":"scenes","products":[{"item_ids":["PATCH_005_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 006

- Observation ID: `23a2adda-7b5e-4c11-a392-f1757520cd2d`
- Source ID: `S1B_20210605T1641`
- Timestamp (UTC): `2021-06-05T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-05-06T16:41:00Z","lte":"2021-07-05T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_006_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_006_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_006_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_006","source_type":"scenes","products":[{"item_ids":["PATCH_006_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 007

- Observation ID: `b1fffddd-b2c2-4e5c-8698-644305b09e38`
- Source ID: `S1B_20210524T1641`
- Timestamp (UTC): `2021-05-24T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-04-24T16:41:00Z","lte":"2021-06-23T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_007_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_007_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_007_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_007","source_type":"scenes","products":[{"item_ids":["PATCH_007_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 008

- Observation ID: `2dee6f8f-db40-4f97-b257-c4aa9517515b`
- Source ID: `S1B_20210519T1632`
- Timestamp (UTC): `2021-05-19T16:32:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-04-19T16:32:00Z","lte":"2021-06-18T16:32:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_008_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_008_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_008_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_008","source_type":"scenes","products":[{"item_ids":["PATCH_008_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 009

- Observation ID: `adf9a7c0-542a-40a6-a2ec-4cf93f4215d2`
- Source ID: `S1B_20210511T0454`
- Timestamp (UTC): `2021-05-11T04:54:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-04-11T04:54:00Z","lte":"2021-06-10T04:54:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_009_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_009_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_009_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_009","source_type":"scenes","products":[{"item_ids":["PATCH_009_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 010

- Observation ID: `c8263fd7-91b0-4222-be30-11736117f07c`
- Source ID: `S1B_20210506T0446`
- Timestamp (UTC): `2021-05-06T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-04-06T04:46:00Z","lte":"2021-06-05T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_010_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_010_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_010_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_010","source_type":"scenes","products":[{"item_ids":["PATCH_010_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 011

- Observation ID: `286d2418-88c0-464e-802b-d4eb34fd5143`
- Source ID: `S1B_20210424T0446`
- Timestamp (UTC): `2021-04-24T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-03-25T04:46:00Z","lte":"2021-05-24T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_011_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_011_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_011_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_011","source_type":"scenes","products":[{"item_ids":["PATCH_011_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 012

- Observation ID: `c302e883-209b-49ac-b17f-b509c06795a9`
- Source ID: `S1A_20211003T0447`
- Timestamp (UTC): `2021-10-03T04:47:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-09-03T04:47:00Z","lte":"2021-11-02T04:47:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_012_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_012_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_012_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_012","source_type":"scenes","products":[{"item_ids":["PATCH_012_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 013

- Observation ID: `76ec6bf4-6b5f-437a-9d4f-aebec8b2ce73`
- Source ID: `S1A_20210926T0455`
- Timestamp (UTC): `2021-09-26T04:55:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-08-27T04:55:00Z","lte":"2021-10-26T04:55:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_013_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_013_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_013_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_013","source_type":"scenes","products":[{"item_ids":["PATCH_013_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 014

- Observation ID: `f53d1aa7-19f3-47e2-8b67-5326a447b879`
- Source ID: `S1A_20210728T0455`
- Timestamp (UTC): `2021-07-28T04:55:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-06-28T04:55:00Z","lte":"2021-08-27T04:55:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_014_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_014_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_014_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_014","source_type":"scenes","products":[{"item_ids":["PATCH_014_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 015

- Observation ID: `6fbcd469-5998-4ef4-b544-6497d27540f9`
- Source ID: `S1A_20210723T0446`
- Timestamp (UTC): `2021-07-23T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-06-23T04:46:00Z","lte":"2021-08-22T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_015_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_015_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_015_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_015","source_type":"scenes","products":[{"item_ids":["PATCH_015_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 016

- Observation ID: `141ddc5d-7ab9-4a52-8479-fb363dbf2705`
- Source ID: `S1A_20210623T1641`
- Timestamp (UTC): `2021-06-23T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-05-24T16:41:00Z","lte":"2021-07-23T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_016_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_016_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_016_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_016","source_type":"scenes","products":[{"item_ids":["PATCH_016_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 017

- Observation ID: `2dd31802-297e-445f-bb86-85630d090d18`
- Source ID: `S1A_20210605T0446`
- Timestamp (UTC): `2021-06-05T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-05-06T04:46:00Z","lte":"2021-07-05T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_017_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_017_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_017_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_017","source_type":"scenes","products":[{"item_ids":["PATCH_017_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 018

- Observation ID: `8e2bbf02-61ec-452c-9fc6-4ce9f4c9491a`
- Source ID: `S1A_20210529T0455`
- Timestamp (UTC): `2021-05-29T04:55:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-04-29T04:55:00Z","lte":"2021-06-28T04:55:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_018_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_018_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_018_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_018","source_type":"scenes","products":[{"item_ids":["PATCH_018_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 019

- Observation ID: `f521a4f4-dd63-499b-a8e5-cd0db7e57ba4`
- Source ID: `S1A_20210524T0446`
- Timestamp (UTC): `2021-05-24T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-04-24T04:46:00Z","lte":"2021-06-23T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_019_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_019_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_019_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_019","source_type":"scenes","products":[{"item_ids":["PATCH_019_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 020

- Observation ID: `7179555b-d477-4799-a8d8-4be28c2ff685`
- Source ID: `S1A_20210506T1641`
- Timestamp (UTC): `2021-05-06T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-04-06T16:41:00Z","lte":"2021-06-05T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_020_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_020_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_020_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_020","source_type":"scenes","products":[{"item_ids":["PATCH_020_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 021

- Observation ID: `05e9c78d-fa17-4609-aa3d-5c9870b5722b`
- Source ID: `S1A_20210424T1641`
- Timestamp (UTC): `2021-04-24T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-03-25T16:41:00Z","lte":"2021-05-24T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_021_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_021_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_021_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_021","source_type":"scenes","products":[{"item_ids":["PATCH_021_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 022

- Observation ID: `47547a65-11f0-4540-93fb-227bad49ae81`
- Source ID: `S1B_20210406T1641`
- Timestamp (UTC): `2021-04-06T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-03-07T16:41:00Z","lte":"2021-05-06T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_022_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_022_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_022_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_022","source_type":"scenes","products":[{"item_ids":["PATCH_022_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 023

- Observation ID: `8fe3676d-b164-410b-a7d0-a77bc42d63c9`
- Source ID: `S1B_20210401T1632`
- Timestamp (UTC): `2021-04-01T16:32:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-03-02T16:32:00Z","lte":"2021-05-01T16:32:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_023_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_023_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_023_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_023","source_type":"scenes","products":[{"item_ids":["PATCH_023_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 024

- Observation ID: `c8e7893a-792a-49ae-920e-d3b64bf802a4`
- Source ID: `S1B_20210325T1641`
- Timestamp (UTC): `2021-03-25T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-02-23T16:41:00Z","lte":"2021-04-24T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_024_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_024_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_024_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_024","source_type":"scenes","products":[{"item_ids":["PATCH_024_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 025

- Observation ID: `155c2d7d-110e-4041-a86b-8ad8d33aba1c`
- Source ID: `S1B_20210307T0446`
- Timestamp (UTC): `2021-03-07T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-02-05T04:46:00Z","lte":"2021-04-06T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_025_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_025_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_025_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_025","source_type":"scenes","products":[{"item_ids":["PATCH_025_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 026

- Observation ID: `da4bfb13-c625-4655-a1ad-101af28758e0`
- Source ID: `S1B_20210223T0446`
- Timestamp (UTC): `2021-02-23T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-01-24T04:46:00Z","lte":"2021-03-25T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_026_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_026_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_026_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_026","source_type":"scenes","products":[{"item_ids":["PATCH_026_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 027

- Observation ID: `986cb23b-f7b6-49a1-8c5e-f27c4c6657aa`
- Source ID: `S1B_20210124T1641`
- Timestamp (UTC): `2021-01-24T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2020-12-25T16:41:00Z","lte":"2021-02-23T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_027_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_027_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_027_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_027","source_type":"scenes","products":[{"item_ids":["PATCH_027_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 028

- Observation ID: `d39f4713-cafa-43a8-9e58-83627e5fa0f8`
- Source ID: `S1B_20210119T1632`
- Timestamp (UTC): `2021-01-19T16:32:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2020-12-20T16:32:00Z","lte":"2021-02-18T16:32:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_028_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_028_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_028_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_028","source_type":"scenes","products":[{"item_ids":["PATCH_028_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 029

- Observation ID: `54583c6f-d50f-4fe8-9c17-6c84ffee527b`
- Source ID: `S1A_20210406T0446`
- Timestamp (UTC): `2021-04-06T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-03-07T04:46:00Z","lte":"2021-05-06T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_029_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_029_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_029_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_029","source_type":"scenes","products":[{"item_ids":["PATCH_029_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 030

- Observation ID: `a7d17cd3-59d4-45bf-a066-94a4084ca96f`
- Source ID: `S1A_20210325T0446`
- Timestamp (UTC): `2021-03-25T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-02-23T04:46:00Z","lte":"2021-04-24T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_030_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_030_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_030_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_030","source_type":"scenes","products":[{"item_ids":["PATCH_030_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 031

- Observation ID: `e584367d-62d7-496b-acd1-75b6df6a00d9`
- Source ID: `S1A_20210307T1641`
- Timestamp (UTC): `2021-03-07T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-02-05T16:41:00Z","lte":"2021-04-06T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_031_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_031_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_031_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_031","source_type":"scenes","products":[{"item_ids":["PATCH_031_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 032

- Observation ID: `a9f8f202-d131-4cde-a088-794725748715`
- Source ID: `S1A_20210223T1641`
- Timestamp (UTC): `2021-02-23T16:41:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2021-01-24T16:41:00Z","lte":"2021-03-25T16:41:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_032_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_032_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_032_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_032","source_type":"scenes","products":[{"item_ids":["PATCH_032_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 033

- Observation ID: `6e869537-def1-4fae-963a-018a6b2c741f`
- Source ID: `S1A_20210124T0446`
- Timestamp (UTC): `2021-01-24T04:46:00.000Z`
- Centroid (lon, lat): `19.287395, 43.759150`
- Estimated patch area m2: `118299.163`
- Validation type: `IN_SITU`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2020-12-25T04:46:00Z","lte":"2021-02-23T04:46:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_033_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_033_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_033_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_033","source_type":"scenes","products":[{"item_ids":["PATCH_033_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[19.284825,43.757864],[19.289964,43.757864],[19.289964,43.760436],[19.284825,43.760436],[19.284825,43.757864]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 034

- Observation ID: `9e17ce98-9eeb-40f6-989e-894dc2be72ea`
- Source ID: `missing`
- Timestamp (UTC): `2017-10-12T23:57:00.000Z`
- Centroid (lon, lat): `-86.691666, 16.016666`
- Estimated patch area m2: `13234762.070`
- Validation type: `None`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[-86.7,15.983333],[-86.683333,15.983333],[-86.683333,16.05],[-86.7,16.05],[-86.7,15.983333]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2017-09-12T23:57:00Z","lte":"2017-11-11T23:57:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_034_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_034_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_034_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_034","source_type":"scenes","products":[{"item_ids":["PATCH_034_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[-86.7,15.983333],[-86.683333,15.983333],[-86.683333,16.05],[-86.7,16.05],[-86.7,15.983333]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 035

- Observation ID: `33a32832-fc41-4fdd-8c91-a41844fc1709`
- Source ID: `missing`
- Timestamp (UTC): `2017-10-17T11:37:00.000Z`
- Centroid (lon, lat): `-86.391666, 16.025000`
- Estimated patch area m2: `9925607.631`
- Validation type: `None`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[-86.4,16.0],[-86.383333,16.0],[-86.383333,16.05],[-86.4,16.05],[-86.4,16.0]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2017-09-17T11:37:00Z","lte":"2017-11-16T11:37:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_035_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_035_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_035_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_035","source_type":"scenes","products":[{"item_ids":["PATCH_035_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[-86.4,16.0],[-86.383333,16.0],[-86.383333,16.05],[-86.4,16.05],[-86.4,16.0]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 036

- Observation ID: `86a3fb61-9db1-4df5-82ae-a848e0455a2e`
- Source ID: `missing`
- Timestamp (UTC): `2020-07-04T23:57:00.000Z`
- Centroid (lon, lat): `130.558334, 32.608334`
- Estimated patch area m2: `2899761.360`
- Validation type: `None`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[130.55,32.6],[130.566667,32.6],[130.566667,32.616667],[130.55,32.616667],[130.55,32.6]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2020-06-04T23:57:00Z","lte":"2020-08-03T23:57:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_036_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_036_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_036_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_036","source_type":"scenes","products":[{"item_ids":["PATCH_036_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[130.55,32.6],[130.566667,32.6],[130.566667,32.616667],[130.55,32.616667],[130.55,32.6]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 037

- Observation ID: `91ea9edc-67b4-4211-8532-35deec4a3148`
- Source ID: `missing`
- Timestamp (UTC): `2018-10-31T18:17:58.000Z`
- Centroid (lon, lat): `-0.219745, 5.495525`
- Estimated patch area m2: `1246225.823`
- Validation type: `None`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[-0.22628,5.49166],[-0.21321,5.49166],[-0.21321,5.49939],[-0.22628,5.49939],[-0.22628,5.49166]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2018-10-01T18:17:58Z","lte":"2018-11-30T18:17:58Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_037_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_037_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_037_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_037","source_type":"scenes","products":[{"item_ids":["PATCH_037_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[-0.22628,5.49166],[-0.21321,5.49166],[-0.21321,5.49939],[-0.22628,5.49939],[-0.22628,5.49166]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 038

- Observation ID: `05e7c3bc-2eac-4c4b-ba8a-6bf8aa4c0789`
- Source ID: `05`
- Timestamp (UTC): `2018-10-12T12:00:00.000Z`
- Centroid (lon, lat): `3.468853, 39.607096`
- Estimated patch area m2: `57694879.709`
- Validation type: `CONCLUSIVE_HIRES_SATELLITE_IMAGE`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[3.4046126087374335,39.583784356213854],[3.5327762266342604,39.5832674191317],[3.5331375811102395,39.630401110063666],[3.4048870431824088,39.63091890806143],[3.4046126087374335,39.583784356213854]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2018-09-12T12:00:00Z","lte":"2018-11-11T12:00:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_038_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_038_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_038_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_038","source_type":"scenes","products":[{"item_ids":["PATCH_038_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[3.4046126087374335,39.583784356213854],[3.5327762266342604,39.5832674191317],[3.5331375811102395,39.630401110063666],[3.4048870431824088,39.63091890806143],[3.4046126087374335,39.583784356213854]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 039

- Observation ID: `3f181238-1180-4e8f-bd9e-90daa87aa6ca`
- Source ID: `04`
- Timestamp (UTC): `2018-10-11T12:00:00.000Z`
- Centroid (lon, lat): `3.468983, 39.607120`
- Estimated patch area m2: `57848731.175`
- Validation type: `CONCLUSIVE_HIRES_SATELLITE_IMAGE`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[3.4047423567176045,39.58374553917426],[3.532905900600688,39.58322845945417],[3.5332683075067615,39.63048783903226],[3.405017611708197,39.63100578220366],[3.4047423567176045,39.58374553917426]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2018-09-11T12:00:00Z","lte":"2018-11-10T12:00:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_039_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_039_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_039_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_039","source_type":"scenes","products":[{"item_ids":["PATCH_039_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[3.4047423567176045,39.58374553917426],[3.532905900600688,39.58322845945417],[3.5332683075067615,39.63048783903226],[3.405017611708197,39.63100578220366],[3.4047423567176045,39.58374553917426]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 040

- Observation ID: `7599355c-419f-4f5b-913b-22b769ee25d2`
- Source ID: `03`
- Timestamp (UTC): `2018-10-11T12:00:00.000Z`
- Centroid (lon, lat): `3.468862, 39.607108`
- Estimated patch area m2: `57848732.523`
- Validation type: `CONCLUSIVE_HIRES_SATELLITE_IMAGE`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[3.4046209823610982,39.58373396389194],[3.5327845072721638,39.583217018171204],[3.533146831478981,39.63047639877668],[3.404896154696399,39.63099420772507],[3.4046209823610982,39.58373396389194]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2018-09-11T12:00:00Z","lte":"2018-11-10T12:00:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_040_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_040_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_040_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_040","source_type":"scenes","products":[{"item_ids":["PATCH_040_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[3.4046209823610982,39.58373396389194],[3.5327845072721638,39.583217018171204],[3.533146831478981,39.63047639877668],[3.404896154696399,39.63099420772507],[3.4046209823610982,39.58373396389194]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```

### Patch 041

- Observation ID: `cabcd011-9d82-4124-9f9c-120bdc406cf3`
- Source ID: `02`
- Timestamp (UTC): `2018-10-12T12:00:00.000Z`
- Centroid (lon, lat): `3.468348, 39.602787`
- Estimated patch area m2: `67944025.663`
- Validation type: `CONCLUSIVE_HIRES_SATELLITE_IMAGE`
- Source type: `SATELLITE,LEO,OPTICAL,SAR,SENTINEL1,SENTINEL2`
- Planet status: `unresolved_no_api_key`
- Closest Planet item: unresolved
- Planet acquired (UTC): unresolved
- Time delta hours: unresolved
- Available assets: unresolved
- Preferred asset type: template uses `ortho_analytic_4b`
- Product bundle for clip order: `analytic_udm2,analytic_8b_udm2`

Quick search for candidate Planet acquisitions:

```bash
curl -X POST "https://api.planet.com/data/v1/quick-search?_sort=acquired%20asc&_page_size=250" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"item_types":["PSScene"],"geometry":{"type":"Polygon","coordinates":[[[3.4045729050919595,39.575073069202034],[3.5317459876053223,39.57456074218084],[3.5321739274227295,39.630492772740126],[3.4048985061325245,39.63100611245799],[3.4045729050919595,39.575073069202034]]]},"filter":{"type":"DateRangeFilter","field_name":"acquired","config":{"gte":"2018-09-12T12:00:00Z","lte":"2018-11-11T12:00:00Z"}}}'
```

Item metadata lookup:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_041_ITEM_ID"
```

Available assets for the item:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_041_ITEM_ID/assets"
```

Activate the preferred single-scene asset:

```bash
curl -X POST -u "$PL_API_KEY:" "https://api.planet.com/data/v1/item-types/PSScene/items/PATCH_041_ITEM_ID/assets/ortho_analytic_4b/activate"
```

Create a clipped Orders API download for the patch polygon:

```bash
curl -X POST "https://api.planet.com/compute/ops/orders/v2" -u "$PL_API_KEY:" -H "Content-Type: application/json" -d '{"name":"mireia_patch_041","source_type":"scenes","products":[{"item_ids":["PATCH_041_ITEM_ID"],"item_type":"PSScene","product_bundle":"analytic_udm2,analytic_8b_udm2"}],"tools":[{"clip":{"aoi":{"type":"Polygon","coordinates":[[[3.4045729050919595,39.575073069202034],[3.5317459876053223,39.57456074218084],[3.5321739274227295,39.630492772740126],[3.4048985061325245,39.63100611245799],[3.4045729050919595,39.575073069202034]]]}}}]}'
```

Check order status and read result download links:

```bash
curl -u "$PL_API_KEY:" "https://api.planet.com/compute/ops/orders/v2/YOUR_ORDER_ID"
```
