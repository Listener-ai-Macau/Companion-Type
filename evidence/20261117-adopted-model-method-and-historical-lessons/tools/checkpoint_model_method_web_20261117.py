"""Local portal source checkpoint and scoped research-evidence protection config."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
P=Path('C:/Users/Billy/Documents/Codex/2026-11-14/ni/work/companion-project-portal')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):return subprocess.check_output(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(P),*args],text=True).strip()
assert read(C/'portal-method-lessons-r1/result.json')['javascriptErrors']==[]
assert not git('diff','--cached','--name-only')
names=['src/app.js','src/style.css','tools/model_progress.py']
assert set(git('diff','--name-only','--',*names).splitlines())==set(names)
receipt=C/'portal-method-source-checkpoint.json';assert not receipt.exists()
parent=git('rev-parse','HEAD');git('add','--',*names)
assert set(git('diff','--cached','--name-only').splitlines())==set(names)
git('commit','--quiet','-m','Adopt diagnostic-first speech workflow and preserve actionable lessons in Companion page')
record=dict(state='LOCAL_MODEL_METHOD_AND_LESSONS_PAGE_SOURCE_CHECKPOINT',at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
 commit=git('rev-parse','HEAD'),parent=parent,files=names,hostingOrRemotePush=False,
 originalBacklogIsExecutionSource=True,lessonSource=str(J/'week-direction-review-20261117.json'),
 qa=str(C/'portal-method-lessons-r1/result.json'),sourceSha256={n:sha(P/n) for n in names},localHtmlSha256=sha(R/'Companion.html'))
receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
sys.path.insert(0,str(R.parent/'ai-collaboration-workflow/tools/handbook'));import docstore
key='Companion/docs/development_log.md';timeline=docstore.read_bytes(key)
canonical=C/'method-web-canonical-receipt.json'
canonical.write_text(json.dumps(dict(backlogSha256=sha(R/'docs/product_backlog.json'),timelineSha256=docstore.sha(timeline),
 timelineQueryKey=key,timelineUrl=docstore.url(key),physicalMarkdownRestored=False),indent=2)+'\n',encoding='utf-8')
files=[]
def add(p,name):
 p=Path(p);assert p.is_file() and p.stat().st_size<32*1024**2
 files.append(dict(source=str(p.resolve()),name=name))
add(J/'week-direction-review-20261117.json','week-review-and-lessons.json')
add('work/bilingual_progress.json','workpoint-snapshot.json')
for name in ['same-input-comparability-audit-r1.json','portal-method-source-checkpoint.json','method-web-canonical-receipt.json']:
 add(C/name,name)
for name in ['audit_model_comparability_20261117.py','adopt_model_method_web_20261117.py','check_model_portal_20261117.py','checkpoint_model_method_web_20261117.py']:
 add(Path('work')/name,'tools/'+name)
for p in (C/'portal-method-lessons-r1').iterdir():
 if p.is_file():add(p,'portal-qa/'+p.name)
config=dict(revision=77,evidenceDirectory='evidence/20261117-adopted-model-method-and-historical-lessons',sources=[],closedDirectories=[],files=files,
 commitMessage='Adopt owner-approved speech work method and preserve lessons with same-input audit',
 claims=dict(state='OWNER_ADOPTED_DIAGNOSE_FIRST_METHOD_AND_LESSONS_WEB_DELIVERED',newNeuralCalls=0,newTrainingUpdates=0,
  originalTwelveEnglishInputHashesAndFramesVerified=True,englishCasesWithChangedCpuSegmentation=7,
  modelQualityImprovementClaimed=False,productDefaultChanged=False,qualityQualified=False,saleQualified=False,
  lessonCount=8,portalLocalSourceCommit=record['commit'],portalHostingOrSourcePush=False,
  rawAudioModelWeightsOrCredentialsIncluded=False,oldFailuresAndHistoricalStatementsRetained=True))
target=Path('work/checkpoint_model_method_r77.json');assert not target.exists()
target.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(localPortalCommit=record['commit'],configuration=str(target),evidenceFiles=len(files),bytes=sum(Path(f['source']).stat().st_size for f in files)),ensure_ascii=False))
