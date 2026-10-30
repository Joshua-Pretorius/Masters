from pathlib import Path
import win32com.client,openpyxl,json
job=Path('D:/Masters/sar_server_pipeline/jobs/marida_16pec_20190116')
x=win32com.client.GetActiveObject('Excel.Application'); w=next(w for w in x.Workbooks if w.FullName.lower()==r'd:\masters\meria_scene_batch_tracker.xlsx')
source=openpyxl.load_workbook('D:/Masters/outputs/marida_16pec_20190116_followup/tracker_preserved.xlsx')
backup=str(job/'backup/MERIA_scene_batch_tracker_excel_unsaved.xlsx');w.SaveCopyAs(backup)
checks=[]
for name,first,last,template,cols in [('Batch summary',97,97,96,13),('Scenes',155,156,154,15)]:
 s=w.Worksheets(name)
 assert all(v is None for row in s.Range(s.Cells(first,1),s.Cells(last,cols)).Value for v in row),'Destination rows are not empty'
 before=s.Range(s.Cells(1,1),s.Cells(template,cols)).Formula
 for r in range(first,last+1):
  s.Range(s.Cells(template,1),s.Cells(template,cols)).Copy(Destination=s.Range(s.Cells(r,1),s.Cells(r,cols)))
  for c in range(1,cols+1):
   value=source[name].cell(r,c).value
   if isinstance(value,str) and value.startswith('='):s.Cells(r,c).Formula=value
   else:s.Cells(r,c).Value=value
 assert before==s.Range(s.Cells(1,1),s.Cells(template,cols)).Formula
 checks.append(name)
x.CutCopyMode=False
w.Save()
assert w.Saved
print('Saved new rows through Excel; existing cell values/formulas and unsaved edits preserved:',checks)
