import json,csv,shutil
from pathlib import Path
root=Path('D:/Masters'); job=root/'sar_server_pipeline/jobs/marida_16pec_20190116'; inv=root/'Data_Creation/global_s1_slc_inventory'; data=json.loads((job/'batch.json').read_text());
overrides={'reason':'User-requested January 16 follow-up to both January 11 slices; outside default 72-hour window. Original January 12 optical time retained; not contemporary ground truth.','associations':data['scenes']}
(inv/'manual_followup_associations.json').write_text(json.dumps(overrides,indent=2))
p=root/'Data_Creation/build_global_s1_slc_inventory.py'; txt=p.read_text();shutil.copy2(p,job/'backup'/p.name)
needle='    if query_catalogue:\n        write_csv(OUT_DIR / "global_s1_slc_associations.csv", target_rows)'
replacement='''    if query_catalogue:
        # Explicit user-requested temporal follow-ups remain distinct from the
        # automatic +/-72-hour selection and survive inventory regeneration.
        override_path = OUT_DIR / "manual_followup_associations.json"
        if override_path.exists():
            overrides = json.loads(override_path.read_text(encoding="utf-8"))
            seen = {row["target_id"] for row in target_rows}
            followups = overrides["associations"]
            for raw in followups:
                row = dict(raw)
                if row["obs_id"] not in buffered_by_obs:
                    raise ValueError(f"Unknown follow-up optical reference: {row['obs_id']}")
                row["coverage_complete"] = str(row["coverage_complete"]).lower() == "true"
                if row["target_id"] not in seen:
                    target_rows.append(row)
                    seen.add(row["target_id"])
            for obs_id in sorted({row["obs_id"] for row in followups}):
                selected = [row for row in followups if row["obs_id"] == obs_id]
                first = selected[0]
                selection_rows.append({
                    "obs_id": obs_id, "source_dataset": first["source_dataset"],
                    "source_group_id": first["source_group_id"], "role": "followup",
                    "candidate_count": len(selected), "selected_count": len(selected),
                    "coverage_set_ratio": float(first["coverage_set_ratio"]),
                    "coverage_complete": str(first["coverage_complete"]).lower() == "true",
                    "reason": overrides["reason"],
                })
        write_csv(OUT_DIR / "global_s1_slc_associations.csv", target_rows)'''
assert needle in txt;p.write_text(txt.replace(needle,replacement,1))
p=inv/'global_s1_slc_selection_summary.csv';shutil.copy2(p,job/'backup'/p.name)
with p.open(newline='') as f:rows=list(csv.DictReader(f))
if not any(r['obs_id']=='marida_16PEC_2019-01-12' and r['role']=='followup' for r in rows):
 r=dict(rows[0],obs_id='marida_16PEC_2019-01-12',source_dataset='MARIDA',source_group_id='16PEC/2019-01-12',role='followup',candidate_count=2,selected_count=2,coverage_set_ratio=1.0,coverage_complete=True,reason=overrides['reason'])
 with p.open('a',newline='') as f:csv.DictWriter(f,fieldnames=rows[0]).writerow(r)
readme='''# MARIDA 16PEC January 16 local follow-up

Batch: `marida_16pec_20190116_followup`.
Parent: `marida_16pec_20190111_03` (both 23:57:57 / 7CEB and 23:58:22 / 4D98).

Two Sentinel-1A IW SLC VV/VH scenes, descending relative orbit 55:
- 2019-01-16 11:37:14 UTC, FC33; 87.04% of buffered AOI.
- 2019-01-16 11:37:41 UTC, B06D; 26.29% of buffered AOI.
Their catalogue footprints jointly cover 100% of the original 30 km buffered processing rectangle. Actual valid-pixel coverage requires output verification.

User requested this follow-up on 2026-10-30 after reporting thick debris in the area. The existing January 12 16:16:31 UTC optical reference is historical context (91.35 hours earlier), not a January 16 label. Both slices require review. No new optical observation date or confirmed plastic label is asserted.

## Local execution
`local_job.yaml` uses the existing pipeline with SNAP native resolution, full-swath IW1/IW2/IW3, one worker and 8 GB cache. Patch extraction and stacking are disabled pending annotation.
Data: `D:/Masters/outputs/marida_16pec_20190116_followup`.
Preflight passed for two targets. Background local download/processing started 2026-10-30. See `run.stderr.log` (INFO lines), `process.pid`, and the stage marker under `manifests/marida_16pec_20190116_followup-local-v1/stages/slc_process.json`.
A success marker plus processed scene manifests and valid rasters are required before calling this complete. No Skua connection is required.

Resume from `D:/Masters/sar_server_pipeline` with the opendrift conda Python:
`python -m pipeline slc_process --manifest jobs/marida_16pec_20190116/local_job.yaml`
Do not start a duplicate while the process in process.pid is running.

## Registration
Updated global associations, processing targets, processing points, selection summary, global job, named batch registry and MERIA scene/batch workbook. `manual_followup_associations.json` preserves the explicit exception during inventory rebuilds. Catalogue provenance is in `asf_catalogue.json`; backups precede each original file change.
'''
(job/'README.md').write_text(readme)
p=inv/'README.md';shutil.copy2(p,job/'backup'/p.name);p.write_text(p.read_text()+ '\n## January 16, 2019 16PEC follow-up\n\nTwo user-requested follow-up SLC scenes (FC33 and B06D) were added on 2026-10-30 as `marida_16pec_20190116_followup`. They jointly cover the buffered AOI and are linked to both January 11 parent slices. This explicit exception is outside the default 72-hour window; `manual_followup_associations.json` preserves it on rebuild. January 12 optical references remain historical context, not January 16 ground truth. Local job, catalogue evidence and current status: `../../sar_server_pipeline/jobs/marida_16pec_20190116/README.md`. The physical target inventory now contains 126 scenes.\n')
compile(txt.replace(needle,replacement,1),str(p),'exec')
print('Inventory regeneration, selection audit and job documentation updated.')
