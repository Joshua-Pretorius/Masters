import fs from 'node:fs/promises';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const outDir = 'D:/Masters/outputs/01a1358f-1333-7933-bfeb-f740f1ce185a';
const wb = Workbook.create();
const ws = wb.worksheets.add('Research timeline');
ws.showGridLines = false;
ws.tabColor = '#254A70';

const navy = '#254A70';
const blue = '#4D88B9';
const pale = '#EAF2F8';
const amber = '#FFF1C7';
const muted = '#5A6C7C';
const dark = '#183047';
const white = '#FFFFFF';
const font = 'Arial';
const date = (y,m,d) => new Date(Date.UTC(y,m-1,d));

ws.getRange('A1:P28').format.font = { name: font, size: 10, color: dark };
ws.getRange('A1:P28').format.verticalAlignment = 'center';
ws.getRange('A1:P28').format.rowHeight = 24;
ws.getRange('A:A').format.columnWidth = 22;
ws.getRange('B:B').format.columnWidth = 38;
ws.getRange('C:D').format.columnWidth = 13;
ws.getRange('E:P').format.columnWidth = 10;
ws.getRange('A1:P1').format.rowHeight = 12;
ws.getRange('A2').values = [['Research completion timeline']];
ws.getRange('A2:P2').format.rowHeight = 34;
ws.getRange('A2:P2').format.font = { name: font, size: 15, bold: true, color: navy };
ws.getRange('A2:P2').format.borders = { bottom: { style: 'thin', color: '#AFC5D7' } };
ws.getRange('A3').values = [['Extension application plan']];
ws.getRange('A3').format.font = { name: font, size: 10, italic: true, color: muted };
ws.getRange('C3').values = [['Target date']];
ws.getRange('D3').values = [[date(2027,3,31)]];
ws.getRange('D3').setNumberFormat('dd mmm yyyy');
ws.getRange('C3:D3').format.font = { name: font, size: 10, bold: true, color: navy };
ws.getRange('A4:P4').format.rowHeight = 13;

const monthGroups = [
  ['E5:F5','Oct 2026'], ['G5:H5','Nov 2026'], ['I5:J5','Dec 2026'],
  ['K5:L5','Jan 2027'], ['M5:N5','Feb 2027'], ['O5:P5','Mar 2027'],
];
for (const [range,label] of monthGroups) {
  ws.mergeCells(range);
  const c = range.split(':')[0];
  ws.getRange(c).values = [[label]];
  ws.getRange(range).format = { fill: navy, font: { name: font, size: 10, bold: true, color: white }, horizontalAlignment: 'center', verticalAlignment: 'center' };
}
ws.getRange('A5:D5').format.fill = navy;
ws.getRange('A5:P5').format.rowHeight = 27;
ws.getRange('A6:D6').values = [['Research section', 'Main stage', 'Start', 'Finish']];
const periods = [];
for (const [y,m] of [[2026,10],[2026,11],[2026,12],[2027,1],[2027,2],[2027,3]]) {
  periods.push(date(y,m,1),date(y,m,16));
}
ws.getRange('E6:P6').values = [periods];
ws.getRange('E6:P6').setNumberFormat('d mmm');
ws.getRange('A6:P6').format = { fill: blue, font: { name: font, size: 10, bold: true, color: white }, horizontalAlignment: 'center', verticalAlignment: 'center' };
ws.getRange('A6:P6').format.rowHeight = 28;

const tasks = [
  ['Introduction', 'Refine aims and study framing', 2027,2,16, 2027,3,10],
  ['Literature review', 'Integrate review and verify references', 2027,2,1, 2027,2,20],
  ['Methods', 'Complete data labelling', 2026,10,15, 2026,11,30],
  ['Methods', 'Preprocess scenes and assemble samples', 2026,10,15, 2026,11,30],
  ['Methods', 'Train and refine the model', 2026,12,1, 2026,12,31],
  ['Methods', 'Evaluate and map detections', 2027,1,1, 2027,1,31],
  ['Methods', 'Write and refine methods chapter', 2027,2,1, 2027,2,25],
  ['Results', 'Analyse results and write chapter', 2027,2,1, 2027,3,5],
  ['Discussion', 'Interpret findings and limitations', 2027,2,16, 2027,3,10],
  ['Conclusion', 'Complete conclusions and abstract', 2027,3,1, 2027,3,15],
  ['Journal article', 'Prepare article for journal submission', 2027,2,16, 2027,3,24],
  ['Full thesis', 'Complete draft for supervisor', 2027,3,11, 2027,3,15],
  ['Review', 'Supervisor feedback and revisions', 2027,3,16, 2027,3,24],
  ['Submission', 'Final checks and submit thesis', 2027,3,25, 2027,3,31],
];
const startRow = 7;
for (let i=0; i<tasks.length; i++) {
  const [section,stage,sy,sm,sd,ey,em,ed] = tasks[i];
  const r = startRow+i;
  ws.getRange(`A${r}:D${r}`).values = [[section,stage,date(sy,sm,sd),date(ey,em,ed)]];
  ws.getRange(`C${r}:D${r}`).setNumberFormat('dd mmm yy');
  ws.getRange(`C${r}:D${r}`).format.fill = amber;
  ws.getRange(`A${r}`).format.font = { name: font, size: 10, bold: true, color: navy };
  ws.getRange(`A${r}:P${r}`).format.rowHeight = 27;
  if (i%2===1) ws.getRange(`A${r}:B${r}`).format.fill = '#F6F9FC';
  if (section==='Submission') {
    ws.getRange(`A${r}:B${r}`).format.fill = pale;
    ws.getRange(`A${r}:B${r}`).format.font = { name: font, size: 10, bold: true, color: navy };
  }
  for (let col=4; col<16; col++) {
    const letter = String.fromCharCode(65+col);
    const c = ws.getRange(`${letter}${r}`);
    c.formulas = [[`=IF(AND($C${r}<=IF(DAY(${letter}$6)=1,${letter}$6+14,EOMONTH(${letter}$6,0)),$D${r}>=${letter}$6),"██████","")`]];
    c.format.font = { name: font, size: 10, bold: true, color: section==='Submission' ? '#D97732' : blue };
    c.format.horizontalAlignment = 'center';
  }
}
ws.getRange(`A${startRow}:P${startRow+tasks.length-1}`).format.borders = { insideHorizontal: { style: 'thin', color: '#E1E9F0' }, bottom: { style: 'thin', color: '#AFC5D7' } };
ws.getRange('A22').values = [['Edit the amber start and finish dates to update the timeline.']];
ws.getRange('A22:P22').format.font = { name: font, size: 10, italic: true, color: muted };
ws.getRange('A24').values = [['Article preparation runs alongside the final thesis writing.']];
ws.getRange('A24:P24').format.font = { name: font, size: 10, italic: true, color: muted };
ws.freezePanes.freezeRows(6);

wb.recalculate();
const inspect = await wb.inspect({kind:'table',range:'Research timeline!A5:P20',include:'values,formulas',tableMaxRows:16,tableMaxCols:16,maxChars:6500});
console.log(inspect.ndjson);
const errors = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'formula error scan',maxChars:2000});
console.log(errors.ndjson);
const preview = await wb.render({sheetName:'Research timeline',range:'A1:P24',scale:1.5,format:'png'});
await fs.writeFile(`${outDir}/gantt_preview.png`,new Uint8Array(await preview.arrayBuffer()));
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(`${outDir}/MSc_Extension_Gantt_to_31_March_2027.xlsx`);
