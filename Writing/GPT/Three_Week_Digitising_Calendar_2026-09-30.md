# Three-week Masters digitising calendar

> Superseded by the [full scene-by-scene Excel calendar](../outputs/01a0eef4-348e-7101-a26b-9e5a892080ca/SAR_Digitising_Calendar_2026-09-30_to_2026-10-20.xlsx), which schedules all 19 current tasks by 2 October and all remaining planned acquisitions by 20 October. Use the workbook for the current plan.

**Dates:** Wednesday 30 September to Tuesday 20 October 2026 (Africa/Johannesburg).  
**Masters:** Monday–Friday, except Tuesday and Thursday 14:00–17:00.  
**Last Call:** Tuesday and Thursday 14:00–17:00, plus Sunday 09:00–13:00, 14:00–17:00 and 19:00–21:00.  
**Saturday:** off. **21:00–23:00:** optional catch-up on active days; no new work is assigned there.

The plan starts on the next full workday because the 29 September work blocks have passed. It covers **15 Masters days**, **117 planned Masters hours**, and **45 planned Last Call hours**. The optional catch-up blocks are outside those totals. Treat scene assignments as review targets, not promises that a visible debris counterpart exists.

## Week 1 · 30 September–6 October

| Day | 09:00–13:00 | 14:00–17:00 | 19:00–21:00 | 21:00–23:00 |
| --- | --- | --- | --- | --- |
| Wed 30 Sep | Inventory the 19 local tasks by **physical SAR acquisition**; check project, raster, time, CRS and annotation status. | Set the review rubric and ledger: supported debris proxy, reviewed non-target, unresolved feature, unusable imagery, or no counterpart identified. Record how empty/no-counterpart reviews will be retained. | Open the Durban batch, test the QGIS annotation workflow, and list any blockers. | Catch-up only. |
| Thu 1 Oct | Durban 2019: inspect **21 Apr** acquisition and its `MERIA_SA_001 before` task. Digitise only supported features and record negatives/uncertainty. | **Last Call.** | Compare optical evidence and drift with the SAR review; save notes and the GeoPackage. | Catch-up only. |
| Fri 2 Oct | Durban 2019: inspect shared **25 Apr** acquisition once, completing the separate `MERIA_SA_001 after` and `MERIA_SA_002 before` tasks. | Inspect **27 Apr** `MERIA_SA_002 after`; make a second pass across all four Durban tasks. | Save evidence, confidence, status and a short Durban decision log. | Catch-up only. |
| Sat 3 Oct | Off. | Off. | Off. | Off. |
| Sun 4 Oct | **Last Call.** | **Last Call.** | **Last Call.** | Catch-up only if needed. |
| Mon 5 Oct | Ghana: inspect **18 Oct 2018** acquisition and its task. | Ghana: inspect the first **24 Oct 2018** frame (`R01`). | Record source/scene timing, counterexamples, unresolved regions and task status. | Catch-up only. |
| Tue 6 Oct | Ghana: inspect the second **24 Oct 2018** frame (`R02`); compare overlap with `R01` without double-counting the physical scenes. | **Last Call.** | Prepare the **30 Oct 2018** shared-acquisition review and close notes from the two 24 Oct frames. | Catch-up only. |

**Checkpoint:** four Durban task reviews and the first three Ghana task reviews recorded; blockers and no-counterpart outcomes visible in the ledger.

## Week 2 · 7–13 October

| Day | 09:00–13:00 | 14:00–17:00 | 19:00–21:00 | 21:00–23:00 |
| --- | --- | --- | --- | --- |
| Wed 7 Oct | Ghana: inspect shared **30 Oct 2018** acquisition once and complete its two distinct optical/SAR tasks. | Second-pass Ghana QA: geometry, class, feature confidence, correspondence confidence and training status across five tasks. | Save Ghana outcomes and update the scene/task ledger. | Catch-up only. |
| Thu 8 Oct | MARIDA **16PCC 2018**, frame `R01`: inspect source mask, timing and SAR; digitise supported features and reviewed negatives. | **Last Call.** | MARIDA **16PCC**, frame `R02`; compare adjacent-frame overlap and log both tasks. | Catch-up only. |
| Fri 9 Oct | MARIDA **16PDC 2018**, frame `R01`. | MARIDA **16PDC**, frame `R02`; check shared source evidence and scene coverage. | Save and QA the four 16PCC/16PDC tasks. | Catch-up only. |
| Sat 10 Oct | Off. | Off. | Off. | Off. |
| Sun 11 Oct | **Last Call.** | **Last Call.** | **Last Call.** | Catch-up only if needed. |
| Mon 12 Oct | MARIDA **18QYF 2021** task. | MARIDA **51PTS 2016** task; complete the six-task MARIDA pass. | Review confidence and eligibility; preserve missing or weak source support. | Catch-up only. |
| Tue 13 Oct | Jamila **Kolkata 2020**: use Sentinel-2 evidence and the SAR scene to review the task. | **Last Call.** | Log the optical-to-SAR relationship and what is or is not identifiable in SAR. | Catch-up only. |

**Checkpoint:** five Ghana and six MARIDA tasks reviewed; Kolkata started. Count task reviews separately from physical scenes and accepted labels.

## Week 3 · 14–20 October

| Day | 09:00–13:00 | 14:00–17:00 | 19:00–21:00 | 21:00–23:00 |
| --- | --- | --- | --- | --- |
| Wed 14 Oct | Jamila **London 2018**, frame `R01`. | Jamila **London 2018**, frame `R02`; compare adjacent frames without copying labels blindly. | QA the London tasks and finish Kolkata notes. | Catch-up only. |
| Thu 15 Oct | Jamila **Tung Chung 2019** task; close the four-task Jamila pass. | **Last Call.** | Reconcile all **19 local task packages** against the ledger; flag incomplete, uncertain or no-counterpart reviews. | Catch-up only. |
| Fri 16 Oct | Second-pass review of proposed accepted debris proxies and confidently reviewed non-targets. | Check geometry, IDs, CRS/grid, duplicate/shared-acquisition handling, class balance and train/validation/test grouping by event or physical scene. Keep unresolved patches out of initial supervised labels. | Freeze a versioned annotation decision log and list outstanding repairs. | Catch-up only. |
| Sat 17 Oct | Off. | Off. | Off. | Off. |
| Sun 18 Oct | **Last Call.** | **Last Call.** | **Last Call.** | Catch-up only if needed. |
| Mon 19 Oct | Validate local GeoPackages and produce counts by reviewed, accepted, excluded, unresolved and no counterpart. | If Skua and transfer paths are available, return edited GeoPackages, run import validation and export accepted polygons; otherwise prepare an exact return manifest and blocker list. | Set patch extraction inputs and leakage-safe scene/event split. | Catch-up only. |
| Tue 20 Oct | Run a small patch/mask extraction and visual QA **if accepted exports are ready**. Otherwise finish the local validation package and write the next transfer/extraction steps. | **Last Call.** | Write the methods/results-ready summary: scenes reviewed, tasks reviewed, accepted proxies, reviewed negatives, unresolved/no counterpart, exclusions, gaps and next processing batch. | Catch-up only. |

**Finish line:** a traceable review of the 19 currently local task packages, a cleaned annotation set with uncertainty preserved, validated/exported accepted polygons where the server handoff is available, and a small extraction check if exports are ready. Additional catalogue scenes, including later South African and global targets, enter a follow-on queue only after their processed rasters and QGIS packages are confirmed ready.

## Daily close-out (use the last 15 minutes of the planned block)

1. Save the GeoPackage and project; verify that the edited layer still opens.
2. Record the **physical acquisition**, **task ID**, optical source/date, SAR time, review outcome, feature/correspondence confidence and training status.
3. Distinguish **no counterpart identified** from a weak positive. Keep unknown dark/bright patches unresolved rather than making them supervised negatives.
4. Move unfinished work to the next available catch-up block only if necessary; otherwise place it in the following day's queue.

## Basis and limits

The local `D:\Joshua` workspace contains 19 current task GeoPackages: Durban 4, Ghana 5, MARIDA 6, and Jamila 4. Several tasks share a physical acquisition. The `D:\Masters\Data_Creation\global_s1_slc_inventory` catalogue lists 116 unique global Sentinel-1 targets, but a catalogue target is not proof that its processed raster and digitising package are ready. This calendar does not assume current Skua availability or that every reviewed scene yields an accepted debris proxy.
