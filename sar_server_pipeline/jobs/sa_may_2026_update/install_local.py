"""Install the verified update locally; never connects to Skua."""
import argparse,hashlib,json,shutil,datetime
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,default=Path('D:/Masters'))
args=parser.parse_args()
root=args.root.resolve()
bundle=Path(__file__).resolve().parent
assert root.is_dir(),f'Masters folder is unavailable: {root}'
hashes=json.loads((bundle/'original_hashes.json').read_text())
changes={}
for relative,expected in hashes.items():
    dst=root/relative
    src=bundle/Path(relative).name
    current=hashlib.sha256(dst.read_bytes()).hexdigest()
    replacement=hashlib.sha256(src.read_bytes()).hexdigest()
    assert current in {expected,replacement},f'{dst} has changed since preparation; merge required, no files changed.'
    if current!=replacement: changes[dst]=src.read_bytes()
registry=root/'sar_server_pipeline/digitising/meria_batches.py'
content=registry.read_text(encoding='utf-8')
anchor='    MeriaBatch("sa_gqeberha_2026_may05_10", "sa", "Gqeberha", ("20260505T170121", "20260510T170927")),\n'
addition='    MeriaBatch("sa_gqeberha_2026_may22_29", "sa", "Gqeberha", ("20260522T170927", "20260529T170120")),\n    MeriaBatch("sa_ku_gompo_2026_may07_12", "sa", "Ku Gompo", ("20260507T164513", "20260512T165318")),\n'
if 'sa_ku_gompo_2026_may07_12' not in content:
    assert content.count(anchor)==1,'Batch registry differs; manual merge required. No files changed.'
    changes[registry]=content.replace(anchor,anchor+addition).encode('utf-8')
tests=root/'sar_server_pipeline/tests/test_meria_batches.py'
if tests.exists() and registry in changes:
    text=tests.read_text(encoding='utf-8')
    for old,new in [('len(MERIA_BATCHES), 17','len(MERIA_BATCHES), 19'),('len(acquisitions), 28','len(acquisitions), 32'),('len(set(acquisitions)), 28','len(set(acquisitions)), 32'),('len(names), 28','len(names), 32'),('sum(len(ids) for ids in selections.values()), 28','sum(len(ids) for ids in selections.values()), 32')]:
        assert old in text, f'Test inventory differs: {old}. No files changed.'
        text=text.replace(old,new)
    changes[tests]=text.encode('utf-8')
backup=root/'outputs'/('sa_may_2026_backup_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True,exist_ok=False)
for dst,data in changes.items():
    saved=backup/dst.relative_to(root)
    saved.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(dst,saved)
    dst.write_bytes(data)
job=root/'sar_server_pipeline/jobs/sa_may_2026_update'
if job.exists():
    shutil.copytree(job,backup/'previous_job')
shutil.copytree(bundle,job,dirs_exist_ok=True)
print(f'Installed {len(changes)} local file updates. Backups: {backup}')
print(f'Job bundle: {job}')
print('No Skua connection made. Run the local batch tests before transfer.')
