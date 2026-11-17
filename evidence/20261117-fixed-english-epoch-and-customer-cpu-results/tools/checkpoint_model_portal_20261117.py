"""Local-only source checkpoint, staging only this batch's portal edits."""
from pathlib import Path
import argparse,hashlib,json,subprocess

P=Path('C:/Users/Billy/Documents/Codex/2026-11-14/ni/work/companion-project-portal')
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
def git(*args,**kw):return subprocess.check_output(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(P),*args],**kw)
assert not git('diff','--cached','--name-only').strip()
parent=git('rev-parse','HEAD').decode().strip()
ap=argparse.ArgumentParser();ap.add_argument('--training-progress',action='store_true');ap.add_argument('--final-results',action='store_true');args=ap.parse_args()
if args.final_results:
    names=['src/app.js','src/style.css','src/handbook.json','tools/model_progress.py']
    changed=set(git('diff','--name-only','--',*names).decode().splitlines())
    assert changed and changed.issubset(names)
    target=C/'portal-final-source-checkpoint.json';assert not target.exists()
    git('add','--',*names)
    assert set(git('diff','--cached','--name-only').decode().splitlines())==changed
    git('commit','--quiet','-m','Report final fixed English adaptation and measured CPU bilingual model limits')
    result=dict(state='LOCAL_FIXED_EPOCH_AND_CUSTOMER_CPU_PAGE_SOURCE_CHECKPOINT',parent=parent,
      commit=git('rev-parse','HEAD').decode().strip(),files=sorted(changed),hostingOrRemotePush=False,
      generatedDistStaged=False,qa=str(C/'portal-final-epoch-cpu-r1/result.json'),
      sourceSha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in changed})
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));raise SystemExit(0)
if args.training_progress:
    names=['src/app.js','src/style.css','src/handbook.json','tools/model_progress.py']
    git('add','--',*names)
    assert set(git('diff','--cached','--name-only').decode().splitlines())==set(names)
    git('commit','--quiet','-m','Show actual English adaptation updates alongside unchanged speech quality gates')
    result=dict(state='LOCAL_TRAINING_PROGRESS_PAGE_SOURCE_CHECKPOINT',parent=parent,
      commit=git('rev-parse','HEAD').decode().strip(),files=names,hostingOrRemotePush=False,
      generatedDistStaged=False,qa=str(C/'portal-training-r1/result.json'),
      sourceSha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in names})
    target=C/'portal-training-source-checkpoint.json';assert not target.exists()
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));raise SystemExit(0)
name='tools/build_portal.py'
base=git('show','HEAD:'+name).decode()
edits=[
('from resource_accounting import build_resource_manager','from resource_accounting import build_resource_manager\nfrom model_progress import build_model_progress'),
("    handbook = load(SITE / 'src/handbook.json')","    handbook = load(SITE / 'src/handbook.json')\n    model_progress = build_model_progress(root, backlog)"),
('sources=source_hashes, handbook=handbook, resources=resources)','sources=source_hashes, handbook=handbook, resources=resources, modelProgress=model_progress)'),
("    emit('resource-manager.json', js(resources['manager']))","    emit('model-progress.json', js(model_progress))\n    emit('resource-manager.json', js(resources['manager']))"),
('groups=groups, tasks=tasks, resources=resources, handbook=handbook','groups=groups, tasks=tasks, resources=resources, modelProgress=model_progress, handbook=handbook'),
('audience=\'local\', current=current, resources=dict(','audience=\'local\', current=current, modelProgress=model_progress, resources=dict(')]
for old,new in edits:
    assert base.count(old)==1,old
    base=base.replace(old,new)
blob=git('hash-object','-w','--stdin',input=base.encode()).decode().strip()
git('update-index','--add','--cacheinfo','100644,'+blob+','+name)
names=['src/app.js','src/index.html','src/style.css','src/handbook.json','tools/model_progress.py']
git('add','--',*names)
staged=git('diff','--cached','--name-only').decode().splitlines()
assert set(staged)==set(names+[name]),staged
git('commit','--quiet','-m','Show measured speech quality, failed routes and current English reference in Companion handbook')
head=git('rev-parse','HEAD').decode().strip()
assert 'docstore.read_text' in (P/name).read_text(encoding='utf-8')
result=dict(state='LOCAL_MODEL_PAGE_SOURCE_CHECKPOINT',parent=parent,commit=head,files=staged,
    hostingOrRemotePush=False,generatedDistStaged=False,
    concurrentDocstoreBuilderEditsPreservedUnstaged=True,
    workingSourceSha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in staged},
    stagedBuilderBlob=blob,qa=str(C/'portal-browser-r5/result.json'))
(C/'portal-source-checkpoint.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
