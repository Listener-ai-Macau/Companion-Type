"""Archive only the six public, pinned, currently selected ASR assets."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=R/'docs/handoffs/20261109-core-acceptance';D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109')
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=128*1024**2)
source=Path(os.environ['APPDATA'])/'Companion Type/models/local-asr'
expected={'onnxruntime.dll':'8b695444d1a35ed0c8338b8c14438b3be5e0a3b222b88b1e7b4ce8753f135b50','onnxruntime_providers_shared.dll':'ebc55b0f28e8a79cbf78e810a7f510ba70e75a2dfbcfcc6aca31ab2b8710a59a','sherpa-onnx-c-api.dll':'94f23cb935c57fb2581c66d65f6602ab5b509d6fc269404296af0336871daba5','funasr-paraformer-large-zh-2024/model.int8.onnx':'8234905d74db17f7466a1cd110ce20f57c1ff9c1fc95db0615d8931955da5c54','funasr-paraformer-large-zh-2024/tokens.txt':'59aba8873a2ed1e122c25fee421e25f283b63290efbde85c1f01a853d83cb6e6'}
def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
for name,digest in expected.items():assert sha(source/name)==digest,name
marker=source/'funasr-paraformer-large-zh-2024/ready';assert marker.read_text(encoding='ascii').strip()==expected['funasr-paraformer-large-zh-2024/model.int8.onnx']
bundle=D/'fixed-product-local-asr079.zip'
if not bundle.exists():
 with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_STORED) as archive:
  for name in [*expected,'funasr-paraformer-large-zh-2024/ready']:archive.write(source/name,name)
with zipfile.ZipFile(bundle) as archive:
 assert set(archive.namelist())==set(expected)|{'funasr-paraformer-large-zh-2024/ready'}
 for name,digest in expected.items():
  with archive.open(name) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==digest,name
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'EXACT_CURRENT_PUBLIC_PRODUCT_ASR_COMPONENTS_PREPARED','provider':'local-paraformer-official','modelSelectionChanged':False,'modelTrainingOrResearchRun':False,'privateAudioOrSettingsIncluded':False,'bundleBytes':bundle.stat().st_size,'bundleSha256':sha(bundle),'files':expected,'readyValue':marker.read_text(encoding='ascii').strip(),'cpuAndMemoryLimits':limits.query()}
for name,digest in expected.items():assert sha(source/name)==digest
gh='C:/Program Files/GitHub CLI/gh.exe';repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
info=json.loads(subprocess.check_output([gh,'release','view',tag,'--repo',repo,'--json','isDraft,assets'],text=True,encoding='utf8'));assert info['isDraft']
if not any(a['name']==bundle.name for a in info['assets']):subprocess.run([gh,'release','upload',tag,str(bundle),'--repo',repo],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
release=json.loads(subprocess.check_output([gh,'api','repos/'+repo+'/releases/438762888'],text=True,encoding='utf8'));assert release['draft'];asset=next(a for a in release['assets'] if a['name']==bundle.name);assert asset['size']==record['bundleBytes'] and asset.get('digest')=='sha256:'+record['bundleSha256']
record.update(privateDraftAsset=asset['id'],draft=True,sourceAssetsUnchanged=True)
(C/'fixed-product-asr-input.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in record.items() if k not in ['files','cpuAndMemoryLimits']},ensure_ascii=False))
