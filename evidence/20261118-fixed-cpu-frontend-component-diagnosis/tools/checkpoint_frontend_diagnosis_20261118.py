"""Select closed frontend evidence for the existing private research checkpoint."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import subprocess

project = Path('C:/Users/Billy/Desktop/Denzic/Companion')
portal = Path('C:/Users/Billy/Documents/Codex/2026-11-14/ni/work/companion-project-portal')
root = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117/preprocessing-contract-20261118')

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

score = read(root / 'cpu-contract-r3/score.json')
assert score['originalSherpaExactOutputMatches'] == 0
before = score['summaryByMode']['installed_frontend']
after = score['summaryByMode']['published_hf_frontend']
assert before['referenceWords'] == after['referenceWords'] == 709
assert read(root / 'portal-qa-final/result.json')['javascriptErrors'] == []

commit = subprocess.check_output(['git','-C',str(portal),'rev-parse','HEAD'], text=True).strip()
delivery = root / 'local-portal-source-receipt.json'
delivery.write_text(json.dumps({
    'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
    'localPortalCommit':commit,'localHtml':str(project/'Companion.html'),
    'localHtmlSha256':sha(project/'Companion.html'),'portalRemotePush':False,
    'qa':str(root/'portal-qa-final/result.json')
},indent=2),encoding='utf-8')

files = []
def add(path, name):
    path = Path(path)
    assert path.is_file() and path.stat().st_size < 32 * 1024**2
    files.append({'source':str(path.resolve()),'name':name})

for name in ['numerical-frontend-audit.json','portable-frontend-parity-r1.json','preparation.json',
             'protocol-r1.json','protocol-r2.json','protocol-r3.json','local-portal-source-receipt.json']:
    add(root/name,name)
for folder in ['feature-inputs-r1','feature-inputs-r2','cpu-contract-r1','cpu-contract-r2-admission-failed',
               'cpu-contract-r2','cpu-contract-r3']:
    for p in (root/folder).iterdir():
        if p.is_file() and p.suffix in ('.json','.previous','.py'):
            add(p,folder+'/'+p.name)
add(root/'portal-qa-final/result.json','portal-qa.json')
for name in ['prepare_frontend_contract_20261118.py','prepare_frontend_features_20261118.py',
             'probe_frontend_contract_20261118.py','score_frontend_contract_20261118.py',
             'audit_frontend_contract_20261118.py','reference_parakeet_cpu_frontend_20261118.py',
             'verify_reference_frontend_cpu_parity_20261118.py','record_frontend_diagnosis_20261118.py',
             'checkpoint_frontend_diagnosis_20261118.py','check_model_portal_20261117.py']:
    add(Path('work')/name,'tools/'+name)
add(Path('work/bilingual_progress.json'),'original-workpoint-snapshot.json')
config = dict(revision=79, evidenceDirectory='evidence/20261118-fixed-cpu-frontend-component-diagnosis',
              sources=[], closedDirectories=[], files=files,
              commitMessage='Preserve fixed-weight CPU frontend comparison and rejected deployment configuration',
              claims=dict(state='FRONTEND_EFFECT_CONFIRMED_FIXED_INT8_CPU_DEPLOYMENT_REJECTED',
                          oldReconstructedErrors=before['errors'], referenceFrontendErrors=after['errors'],
                          words=709, oldEmptyOutputs=before['emptyOutputs'], newEmptyOutputs=after['emptyOutputs'],
                          actualSherpaOutputsReproduced=False, sameDirectExecutorWeightsAndRuntime=True,
                          productDefaultChanged=False, trainingUpdates=0, qualityQualified=False,
                          saleQualified=False, noAudioWeightsFeatureArraysWheelsOrCredentials=True,
                          localPortalCommit=commit))
with Path('work/checkpoint_frontend_diagnosis_r79.json').open('x',encoding='utf-8') as f:
    json.dump(config,f,indent=2)
print(json.dumps(dict(entries=len(files),localPortalCommit=commit)))
