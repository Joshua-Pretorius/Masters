import {FileBlob,SpreadsheetFile} from 'file:///C:/Users/Joshua%20Pretorius/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
import fs from 'node:fs/promises';
const dir='D:/Masters/outputs/marida_16pec_20190116_followup';
const job='D:/Masters/sar_server_pipeline/jobs/marida_16pec_20190116';
const source='D:/Masters/MERIA_scene_batch_tracker.xlsx';
await fs.copyFile(source,job+'/backup/MERIA_scene_batch_tracker.xlsx');
const w=await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const data=JSON.parse(await fs.readFile(job+'/batch.json','utf8'));
const s=w.worksheets.getItem('Batch summary'),sc=w.worksheets.getItem('Scenes');
s.getRange('A97:M97').copyFrom(s.getRange('A96:M96'),'all');
s.getRange('A97:M97').values=[['MARIDA',data.batch,'16PEC',2,91.345278,27/86400,null,null,null,null,null,null,'Local job started 2026-10-30. Follow-up to marida_16pec_20190111_03; both slices. Historical optical reference 2019-01-12; January 16 labels require review.']];
for(const [c,sceneCol] of [['I','L'],['J','M'],['K','N'],['L','O']])s.getRange(c+'97').formulas=[[`=COUNTIFS(Scenes!$B$7:$B$156,$B97,Scenes!$${sceneCol}$7:$${sceneCol}$156,"Done")`]];
for(let i=0;i<2;i++){
 const row=155+i, r=data.scenes[i];sc.getRange(`A${row}:O${row}`).copyFrom(sc.getRange('A154:O154'),'all');
 sc.getRange(`A${row}:O${row}`).values=[['MARIDA',data.batch,'16PEC',r.acquisition_start.replace('T',' ').replace('Z',''),Number(r.delta_h),Number(r.delta_h),'MARIDA','marida_16PEC_2019-01-12',r.download_group_key,'MARIDA',`Local processing job started 2026-10-30. Descending track 55. Footprint covers ${(Number(r.scene_coverage_ratio)*100).toFixed(1)}% of buffered AOI; pair covers 100%. Historical optical context only.`,null,null,null,null]];
}
w.recalculate();
console.log((await w.inspect({kind:'table',range:"'Batch summary'!A97:M97",include:'values,formulas',tableMaxCols:13,tableMaxRows:1})).ndjson);
for(const [name,range,file] of [['Batch summary','A95:F97','tracker_after_summary.png'],['Scenes','A154:F156','tracker_after_scenes.png']]){
 const b=await w.render({sheetName:name,range,scale:1.5}); await fs.writeFile(dir+'/'+file,new Uint8Array(await b.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(w)).save(dir+'/tracker_updated.xlsx');
