"""Reuse the exact successful CI artifact, bounded buffers and immutable source."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,zipfile
from release_readback import download
C=Path(__file__).parent;W=Path('E:/CodexData/Companion/.build-cache/windows-note-context20261110');code=sys.argv[1];run_id=int(sys.argv[2]);assert re.fullmatch(r'\d{3}',code) and run_id>0;O=C/('windows'+code);freeze=json.loads((O/'source-freeze.json').read_text(encoding='utf8'));source=freeze['sourceCommit'];artifact_source=freeze.get('artifactSourceCommit',source);assert re.fullmatch('[0-9a-f]{40}',source)
def gh(args):
 p=subprocess.run(['gh',*args],capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stderr.decode(errors='replace')[-1200:];return p.stdout
run=json.loads(gh(['run','view',str(run_id),'--repo','Listener-ai-Macau/Companion-Type','--json','status,conclusion,headSha']));assert run=={'conclusion':'success','headSha':artifact_source,'status':'completed'},run
info=json.loads(gh(['api','repos/Listener-ai-Macau/Companion-Type/actions/runs/'+str(run_id)+'/artifacts']));artifact=next(a for a in info['artifacts'] if a['name']=='companion-windows-candidate-'+artifact_source);archive=W/('ci-artifact'+code+'.zip');proof=download('Listener-ai-Macau/Companion-Type',artifact['id'],archive,artifact['size_in_bytes'],artifact['digest'].removeprefix('sha256:'),kind='artifact');dest=W/('ci-artifact'+code)/artifact_source
if not dest.exists():
 dest.mkdir(parents=True)
 with zipfile.ZipFile(archive) as z:
  for item in z.infolist():
   n=item.filename;assert not n.startswith(('/','\\')) and ':' not in n and '..' not in Path(n).parts and (dest/n).resolve().is_relative_to(dest.resolve())
  z.extractall(dest)
result=json.loads((dest/'result.json').read_text(encoding='utf8'));assert result['state']=='CI_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING' and result['sourceCommit']==source and result['version']=='0.1.'+str(int(code))
for row in result['nativeFiles']:
 with (dest/'windows-bin'/row['path']).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']
with (dest/result['msi']).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==result['msiSha256']
(O/'artifact-readback.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8');(O/'build-artifacts.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8');print(json.dumps({k:result[k] for k in ['state','sourceCommit','version','msiSha256','affectedTestBinary']}))
for file in dest.glob('*context-regression.log'):print(file.name,[line for line in file.read_text(encoding='utf8',errors='replace').splitlines() if 'test result:' in line])
