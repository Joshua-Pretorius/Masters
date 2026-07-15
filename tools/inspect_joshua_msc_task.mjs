import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = String.raw`C:\Users\Joshua Pretorius\Downloads\Joshua_Msc_Task.xlsx`;
const outputDir = String.raw`D:\Masters\outputs\joshua_msc_task_inspect`;

await fs.mkdir(outputDir, { recursive: true });

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const summary = await workbook.inspect({
  kind: "workbook,sheet,table,region",
  maxChars: 12000,
  tableMaxRows: 12,
  tableMaxCols: 10,
  tableMaxCellChars: 120,
});

await fs.writeFile(path.join(outputDir, "summary.ndjson"), summary.ndjson, "utf8");

const sheets = workbook.worksheets.items.map((sheet) => sheet.name);
for (const sheetName of sheets) {
  const safeName = sheetName.replace(/[<>:"/\\|?*]+/g, "_");
  const preview = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(outputDir, `${safeName}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

console.log(
  JSON.stringify({
    sheets,
    summaryPath: path.join(outputDir, "summary.ndjson"),
    outputDir,
  }),
);
