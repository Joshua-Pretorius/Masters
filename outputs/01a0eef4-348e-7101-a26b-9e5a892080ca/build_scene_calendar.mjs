import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const outDir = "D:/Masters/outputs/01a0eef4-348e-7101-a26b-9e5a892080ca";
const data = JSON.parse(await fs.readFile(path.join(outDir, "scene_calendar_data.json"), "utf8"));
const workbook = Workbook.create();
const calendar = workbook.worksheets.add("Calendar");
const handoff = workbook.worksheets.add("Server handoff");
const register = workbook.worksheets.add("Scene register");
const sceneByAlias = new Map(data.scenes.map((scene) => [scene.alias, scene]));
const font = "Arial";
const navy = "#18324B";
const blue = "#1F5F86";
const paleBlue = "#EAF3F8";
const paleAmber = "#FFF2D6";
const paleGray = "#F0F2F4";
const body = "#1F2937";

const dateValue = (iso) => {
  if (!iso || iso === "Already local") return null;
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
};
const acq = (granule) => granule.match(/_(\d{8}T\d{6})_/ )?.[1] ?? "";
const sceneLabel = (alias) => {
  const scene = sceneByAlias.get(alias);
  const area = (scene.areas[0] ?? scene.sources[0] ?? "Scene").slice(0, 16);
  const shortDate = acq(scene.granule).slice(0, 8);
  const taskNote = scene.local_tasks.length > 1 ? ` (${scene.local_tasks.length} tasks)` : "";
  return `${alias}  ${area}  ${shortDate}${taskNote}`;
};
const aliasLines = (aliases, perLine = 5) => {
  const lines = [];
  for (let i = 0; i < aliases.length; i += perLine) lines.push(aliases.slice(i, i + perLine).join("  "));
  return lines.join("\n");
};
const setTitle = (sheet, title, subtitle, note, lastColumn) => {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastColumn}5`).format.font = { name: font, size: 10, color: body };
  sheet.getRange("A2").values = [[title]];
  sheet.getRange("A2").format.font = { name: font, size: 15, color: navy, bold: true };
  sheet.getRange("A3").values = [[subtitle]];
  sheet.getRange("A3").format.font = { name: font, size: 10, color: body, italic: true };
  sheet.getRange("A4").values = [[note]];
  sheet.getRange("A4").format.font = { name: font, size: 10, color: body };
  sheet.getRange(`A5:${lastColumn}5`).format.borders = { bottom: { style: "thin", color: "#A9BBC8" } };
};
const headerStyle = (range) => {
  range.format.fill = navy;
  range.format.font = { name: font, size: 10, bold: true, color: "#FFFFFF" };
  range.format.rowHeight = 28;
  range.format.verticalAlignment = "center";
  range.format.horizontalAlignment = "center";
};

// The calendar is the primary reader-facing view. Every alias has exactly one review block.
setTitle(
  calendar,
  "SAR digitising calendar",
  "30 September – 20 October 2026  |  Africa/Johannesburg",
  "19 local tasks / 17 physical scenes by Friday; then 112 scenes over 12 Masters days. Server processing and transfer require a daily ready check.",
  "G",
);
calendar.getRange("A5").values = [["Required pace after Friday: 11 scenes on full days and 7 on meeting days, about 50 minutes per scene before server handling. Replan if actual review time is longer."]];
calendar.getRange("A5").format.font = { name: font, size: 10, color: "#8A4B08", italic: true };
calendar.getRange("A6:G6").values = [[
  "Date", "Day", "09:00–13:00", "14:00–17:00", "19:00–21:00", "21:00–23:00", "09:00 server queue for next workday",
]];
headerStyle(calendar.getRange("A6:G6"));
calendar.getRange("A:A").format.columnWidth = 15;
calendar.getRange("B:B").format.columnWidth = 9;
calendar.getRange("C:C").format.columnWidth = 45;
calendar.getRange("D:D").format.columnWidth = 45;
calendar.getRange("E:E").format.columnWidth = 43;
calendar.getRange("F:F").format.columnWidth = 21;
calendar.getRange("G:G").format.columnWidth = 36;
const dayRows = data.calendar_days.map((day) => {
  const isWorkday = day.masters_day;
  const morning = day.blocks["09:00–13:00"].map(sceneLabel).join("\n");
  const afternoon = day.meeting_day
    ? "14:30–15:00  Meeting"
    : day.blocks["14:00–17:00"].map(sceneLabel).join("\n");
  const evening = day.blocks["19:00–21:00"].map(sceneLabel).join("\n");
  const next = day.prep_aliases.length
    ? `Start ${day.next_workday} batch\n${aliasLines(day.prep_aliases, 5)}`
    : "";
  return [dateValue(day.date), day.weekday, morning, afternoon, evening, isWorkday ? "Catch-up only" : "", next];
});
calendar.getRange(`A7:G${6 + dayRows.length}`).values = dayRows;
calendar.getRange(`A7:A${6 + dayRows.length}`).setNumberFormat("ddd dd mmm");
calendar.getRange(`A7:G${6 + dayRows.length}`).format.font = { name: font, size: 10, color: body };
calendar.getRange(`A7:G${6 + dayRows.length}`).format.verticalAlignment = "center";
calendar.getRange(`C7:G${6 + dayRows.length}`).format.wrapText = true;
calendar.getRange(`A7:G${6 + dayRows.length}`).format.rowHeight = 101;
for (let index = 0; index < data.calendar_days.length; index++) {
  const row = index + 7;
  const day = data.calendar_days[index];
  if (!day.masters_day) {
    calendar.getRange(`A${row}:G${row}`).format.fill = paleGray;
    calendar.getRange(`A${row}:G${row}`).format.rowHeight = 27;
  } else {
    if (index % 2 === 0) calendar.getRange(`A${row}:G${row}`).format.fill = "#F8FAFC";
    if (day.meeting_day) calendar.getRange(`D${row}`).format.fill = paleAmber;
    if (day.prep_aliases.length) calendar.getRange(`G${row}`).format.fill = paleBlue;
  }
  if (day.date === "2026-10-02" || day.date === "2026-10-09" || day.date === "2026-10-16") {
    calendar.getRange(`A${row}:G${row}`).format.borders = { bottom: { style: "medium", color: "#708A9D" } };
  }
}
calendar.freezePanes.freezeRows(6);
calendar.tabColor = navy;

// Server handoff specifies the prior-workday action and exact scene IDs in each package.
setTitle(
  handoff,
  "Daily server handoff",
  "At 09:00 on the prep date, check processed manifests, run missing SLC processing, then prepare the QGIS batch.",
  "Move the batch QGZ, task GeoPackages, task manifests and selected SAR TIFFs listed in transfer_files.txt. Verify QGIS opens before the review day.",
  "G",
);
handoff.getRange("A6:G6").values = [[
  "Prep date", "Review date", "Scenes for review", "Count", "09:00 server action", "Move across by end of prep day", "Ready check",
]];
headerStyle(handoff.getRange("A6:G6"));
handoff.getRange("A:A").format.columnWidth = 16;
handoff.getRange("B:B").format.columnWidth = 16;
handoff.getRange("C:C").format.columnWidth = 42;
handoff.getRange("D:D").format.columnWidth = 9;
handoff.getRange("E:E").format.columnWidth = 48;
handoff.getRange("F:F").format.columnWidth = 51;
handoff.getRange("G:G").format.columnWidth = 18;
const handoffDays = data.calendar_days.filter((day) => day.prep_aliases.length);
const handoffRows = handoffDays.map((day) => [
  dateValue(day.date),
  dateValue(day.next_workday),
  aliasLines(day.prep_aliases, 5),
  day.prep_aliases.length,
  "Check scene manifests; process missing SLC scenes; run digitising prepare for this batch.",
  "Use generated transfer_files.txt: batch.qgz, task.gpkg, task manifests, selected SAR TIFFs; open locally.",
  "Not checked",
]);
handoff.getRange(`A7:G${6 + handoffRows.length}`).values = handoffRows;
handoff.getRange(`A7:B${6 + handoffRows.length}`).setNumberFormat("ddd dd mmm");
handoff.getRange(`A7:G${6 + handoffRows.length}`).format.font = { name: font, size: 10, color: body };
handoff.getRange(`A7:G${6 + handoffRows.length}`).format.verticalAlignment = "center";
handoff.getRange(`C7:F${6 + handoffRows.length}`).format.wrapText = true;
handoff.getRange(`A7:G${6 + handoffRows.length}`).format.rowHeight = 76;
handoff.getRange(`G7:G${6 + handoffRows.length}`).format.fill = paleAmber;
handoff.getRange(`G7:G${6 + handoffRows.length}`).dataValidation = {
  rule: { type: "list", values: ["Not checked", "Processing", "Prepared", "Transferred", "Blocked"] },
};
handoff.freezePanes.freezeRows(6);
handoff.tabColor = blue;

// One row per physical Sentinel-1 acquisition; local multi-task scenes remain one physical row.
setTitle(
  register,
  "Scene register",
  "129 distinct physical acquisitions: 116 global targets plus 14 South African targets, with one acquisition shared by both lists.",
  "The first 17 rows are local QGIS acquisitions covering 19 tasks. Later server state is unverified; update the status fields as batches arrive.",
  "N",
);
register.getRange("A6:N6").values = [[
  "Scene ID", "Acquisition", "Full Sentinel-1 granule", "Source dataset(s)", "Area(s)", "Optical observation(s)",
  "Local task ID(s)", "Review date", "Review block", "Server prep date", "Local QGIS", "Server stage", "Transfer status", "Review outcome",
]];
headerStyle(register.getRange("A6:N6"));
const widths = [11, 21, 76, 27, 28, 40, 80, 16, 18, 18, 14, 18, 18, 23];
for (let c = 0; c < widths.length; c++) register.getRangeByIndexes(0, c, 1, 1).format.columnWidth = widths[c];
const registerRows = data.scenes.map((scene) => [
  scene.alias,
  acq(scene.granule),
  scene.granule,
  scene.sources.join(", "),
  scene.areas.join(", "),
  scene.observations.join(", "),
  scene.local_tasks.join("\n"),
  dateValue(scene.scheduled_date),
  scene.scheduled_block,
  dateValue(scene.prep_date),
  scene.local_tasks.length ? "Yes" : "No",
  "Not live checked",
  scene.local_tasks.length ? "Local package" : "Pending",
  "",
]);
register.getRange(`A7:N${6 + registerRows.length}`).values = registerRows;
register.getRange(`H7:H${6 + registerRows.length}`).setNumberFormat("ddd dd mmm");
register.getRange(`J7:J${6 + registerRows.length}`).setNumberFormat("ddd dd mmm");
register.getRange(`A7:N${6 + registerRows.length}`).format.font = { name: font, size: 10, color: body };
register.getRange(`A7:N${6 + registerRows.length}`).format.verticalAlignment = "center";
register.getRange(`G7:G${6 + registerRows.length}`).format.wrapText = true;
register.getRange(`A7:N${6 + registerRows.length}`).format.rowHeight = 26;
register.getRange("A7:N23").format.fill = paleBlue;
register.getRange("L7:N135").format.fill = paleAmber;
register.freezePanes.freezeRows(6);
register.freezePanes.freezeColumns(3);
register.tabColor = "#698398";
register.getRange("A138").values = [[
  "Sources: global_s1_slc_processing_targets.csv; global_s1_slc_associations.csv; MERIA_SA_plastic_nearest_S1_SLC_before_after.csv; local task_manifest.json files."
]];
register.getRange("A138").format.font = { name: font, size: 9, italic: true, color: "#475569" };

workbook.recalculate();
for (const [sheetName, range, fileName] of [
  ["Calendar", "A1:G13", "calendar_week1.png"],
  ["Calendar", "A14:G20", "calendar_week2.png"],
  ["Calendar", "A21:G27", "calendar_week3.png"],
  ["Server handoff", "A1:G18", "server_handoff.png"],
  ["Scene register", "A1:J19", "scene_register.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.2, format: "png" });
  await fs.writeFile(path.join(outDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const mainCheck = await workbook.inspect({ kind: "table", range: "Calendar!A1:G13", include: "values", tableMaxRows: 13, tableMaxCols: 7, maxChars: 4000 });
const registerCheck = await workbook.inspect({ kind: "table", range: "Scene register!A6:N10", include: "values", tableMaxRows: 5, tableMaxCols: 14, maxChars: 2500 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 30 }, summary: "formula errors" });
console.log("CALENDAR_CHECK", mainCheck.ndjson);
console.log("REGISTER_CHECK", registerCheck.ndjson);
console.log("ERRORS", errors.ndjson);
const output = await SpreadsheetFile.exportXlsx(workbook);
const outputPath = path.join(outDir, "SAR_Digitising_Calendar_2026-09-30_to_2026-10-20.xlsx");
await output.save(outputPath);
console.log("SAVED", outputPath);
