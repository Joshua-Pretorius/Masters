# Plastic Event Entry Web App Design

## Goal

Build a small local Python web app that runs on `localhost` and lets a single user enter new plastic-observation events, then regenerate the existing nearest-S1 inventory outputs for the matching scope.

The app must:

- collect event metadata and geometry through one browser form
- accept either pasted coordinates or uploaded point geometry files
- persist the entered event as canonical source data owned by the app
- rerun the existing South Africa or global nearest-S1 generator after save
- show the regenerated result, including before and after S1 matches and coverage information

## Scope

This is a local single-user tool, not a shared service.

V1 will support:

- `sensor_observed`: `S1`, `S2`, `Planet`
- `scope`: `SA`, `Global`
- one-page event entry and result display
- pasted coordinate input
- uploaded `shp`, zipped shapefile, or `gpkg` point input
- regeneration of the existing generated nearest-S1 CSV and docx files
- showing alternate S1 candidate scenes when the chosen match is not full coverage

V1 will not support:

- authentication or multiple users
- polygon or line event geometry
- editing or deleting previously saved events through the UI
- direct editing of generated inventory CSV or docx outputs
- background job queues or remote deployment

## Existing Pipeline Constraints

The current nearest-S1 outputs are generated artifacts, not source records.

Current generated outputs include:

- `D:\Masters\Data_Creation\meria_sa_plastic_s1_slc\MERIA_SA_plastic_nearest_S1_SLC_before_after.csv`
- `D:\Masters\Data_Creation\meria_sa_plastic_s1_slc\MERIA_SA_plastic_nearest_S1_SLC_before_after.docx`
- `D:\Masters\Data_Creation\meria_global_s1_slc\MERIA_global_plastic_nearest_S1_SLC_before_after.csv`
- `D:\Masters\Data_Creation\meria_global_s1_slc\MERIA_global_plastic_nearest_S1_SLC_before_after.docx`

The South Africa generator currently uses hard-coded observations in `D:\Masters\Data_Creation\build_meria_sa_s1_slc_matches.py`.

The global generator currently combines hard-coded observations with Ghana shapefile-derived observations in `D:\Masters\Data_Creation\build_meria_global_s1_slc_matches.py`.

The new app must not mutate generated files directly. Instead, it will introduce a new app-owned source dataset and either:

- extend the existing generators to read those app-owned source records, or
- invoke a thin adapter layer that merges app-owned source records into the generator input model before rebuild

## Recommended Architecture

Use a single Python process with three concerns:

1. A local HTTP server that renders the form and result page.
2. A persistence layer that stores canonical event records and normalized geometry.
3. An orchestration layer that updates generator inputs, reruns the relevant generator, and reads back the newly generated row.

The app should live under a new directory such as:

- `D:\Masters\Data_Creation\event_entry_app`

Suggested internal layout:

- `app.py` or equivalent server entrypoint
- `templates/` for HTML
- `static/` for CSS and light client-side JS
- `data/events.csv` for event metadata
- `data/geometries/<event_id>.geojson` for normalized point storage
- `data/uploads/` for original uploaded files
- `services/` for parsing, validation, generator orchestration, and result extraction

## Canonical Data Model

Each saved event becomes one canonical record in the app-owned source dataset.

Event metadata fields:

- `event_id`
- `created_at_utc`
- `sensor_observed`
- `observed_date`
- `scope`
- `area_name`
- `notes`
- `geometry_source_type` as `manual` or `upload`
- `upload_original_name`
- `point_count`
- `processing_status`
- `processing_message`

Normalized geometry storage:

- store one GeoJSON-style point collection per event under `data/geometries/<event_id>.geojson`
- always store coordinates as WGS84 longitude and latitude
- preserve stable point identifiers inside the stored geometry

The app should keep both:

- raw user metadata for traceability
- normalized point geometry for deterministic downstream processing

## Input Rules

The single-page form will collect:

- observed sensor
- observed date
- scope
- area name
- notes
- geometry input

Geometry input options:

- pasted coordinates
- uploaded point file

Supported upload formats in V1:

- `.gpkg`
- `.shp`
- zipped shapefile containing the required sidecar files

Coordinate paste rules:

- support one point per line
- each line may contain latitude and longitude in decimal degrees
- the parser may later be extended for cardinal notation, but V1 should prioritize reliable decimal-degree input

Input exclusivity rule:

- allow either pasted coordinates or an uploaded file for V1
- if both are supplied in the same submission, reject the submission and ask the user to choose one source

This keeps validation simple and avoids silent disagreements between two geometry inputs.

## Validation

Validate before any permanent write.

Required fields:

- `sensor_observed`
- `observed_date`
- `scope`
- `area_name`
- at least one point

Geometry validation rules:

- uploaded geometry must resolve to point features only
- all normalized coordinates must be convertible to WGS84 longitude and latitude
- empty files or empty pasted input must be rejected

Submission validation outcomes:

- invalid form data: reject with field-level messages and no writes
- valid form data: persist event first, then run downstream regeneration

## Processing Rules

After a valid submit:

1. Normalize and validate geometry.
2. Allocate a stable `event_id`.
3. Save metadata to `events.csv`.
4. Save normalized geometry to `data/geometries/<event_id>.geojson`.
5. Copy the original upload into `data/uploads/` if an upload was used.
6. Update the relevant generator input source for `SA` or `Global`.
7. If `sensor_observed` is `S2` or `Planet`, rerun nearest-S1 matching for the chosen scope.
8. If `sensor_observed` is `S1`, mark the event saved and skip nearest-S1 matching.
9. Read back the regenerated output row for the saved event and show it in the UI.

Sensor-specific behavior:

- `S1` observations are saved only and do not trigger nearest-S1 lookup
- `S2` and `Planet` observations trigger nearest-S1 lookup

Scope-specific behavior:

- `SA` submissions only rerun the South Africa generator
- `Global` submissions only rerun the global generator

## Generator Integration

The cleanest generator boundary is to stop treating the observation lists as fully hard-coded.

Recommended change:

- move observation loading behind explicit loader functions in both generator scripts
- merge existing built-in observations with app-owned saved events for the relevant scope

For South Africa:

- replace the fully hard-coded `OBSERVATIONS` list with `BASE_OBSERVATIONS + load_saved_app_observations("SA")`

For global:

- keep the existing Ghana shapefile loader
- replace the current final observation assembly with `BASE_OBSERVATIONS + load_ghana_drift_observations() + load_saved_app_observations("Global")`

The app should invoke the generators as scripts, not reimplement their matching logic inside the web layer.

## Result Display

After processing, the result page should show:

- save status
- `event_id`
- whether nearest-S1 matching ran or was skipped
- generated output file paths

For `S2` and `Planet` submissions, also show:

- before scene name
- before scene timestamp
- before coverage ratio
- after scene name
- after scene timestamp
- after coverage ratio
- candidate counts
- rejection reasons if no valid match was selected

For `S1` submissions:

- show that the event was saved
- show that nearest-S1 matching was intentionally skipped

## Alternate Scene Coverage

The user wants to see which extra S1 scenes would make up the remainder when the selected scene does not cover the full event geometry.

V1 should support this by extending the generator result payload or app-side readback to include alternate candidates for the saved event:

- scene name
- scene timestamp
- coverage ratio
- whether the scene was selected or only suggested as supplemental coverage

This should be shown separately for before and after candidates.

If the current generator output CSV does not contain enough detail, the generator should be extended to emit additional candidate information in a machine-readable form, preferably:

- extra CSV columns containing serialized candidate summaries, or
- a sidecar JSON file keyed by `event_id`

A sidecar JSON file is preferable because candidate lists are variable-length and fit poorly into flat CSV.

## Error Handling

Saving the canonical event record and downstream regeneration are separate outcomes.

Rules:

- if validation fails, save nothing
- if save succeeds but regeneration fails, keep the saved event and report the regeneration error
- if save and regeneration both succeed, show the generated result

The UI must distinguish:

- `saved`
- `saved_but_match_skipped`
- `saved_but_regeneration_failed`
- `saved_and_regenerated`

Regeneration errors should surface:

- the failing scope
- the script invoked
- the captured stderr or error message

The user should be able to retry later without re-entering the event, even if V1 exposes retry only through a local command rather than a UI button.

## UI Design

Use a single simple page with two sections:

- the entry form
- the latest processing result

The page should favor clarity over framework complexity.

Suggested form layout:

- top row: scope, sensor, observed date
- second row: area name
- notes field
- geometry input mode selector
- geometry input area
- submit button

Geometry area behavior:

- if manual mode is selected, show a multiline text box with decimal-degree examples
- if upload mode is selected, show a file input with accepted formats listed

The result section should appear below the form after submit and remain readable even when regeneration fails.

## Implementation Direction

Use a minimal Python web framework with simple templating.

Recommended stack:

- Flask for routing and form handling
- Jinja templates for HTML rendering
- light CSS with no frontend build step

This is preferred over a separate SPA because:

- it keeps the stack aligned with the existing Python pipeline
- it avoids introducing Node tooling into a workspace that does not already have a frontend app
- it is sufficient for a single local form workflow

## Testing

Testing should focus on deterministic seams.

Unit tests:

- coordinate parsing and normalization
- uploaded geometry parsing
- validation outcomes
- event ID generation
- generator input assembly from saved events
- result extraction from regenerated outputs

Integration tests:

- `S1` submission saves and skips matching
- `S2` or `Planet` submission saves and triggers the correct scope generator
- failed generator run leaves saved event intact
- regenerated row for the saved event can be read back and displayed

Test fixtures should avoid live network access by mocking generator execution or mocking the generator internals at the orchestration layer.

## Rollout Sequence

Implement in this order:

1. Create app-owned event storage and geometry normalization.
2. Add single-page local web form and validation.
3. Refactor both generator scripts to load app-owned saved events.
4. Add orchestration to run only the relevant scope generator.
5. Read back and display regenerated results.
6. Extend generator output for alternate candidate scene reporting.

## Success Criteria

The design is successful when:

- a local user can open the app in a browser on `localhost`
- the user can submit either manual points or a point upload
- the app saves the event as canonical source data
- `S2` and `Planet` events regenerate the correct nearest-S1 outputs for the chosen scope
- `S1` events save cleanly without running nearest-S1 matching
- the result page shows the regenerated row and coverage information
- regeneration failures do not lose the saved event
