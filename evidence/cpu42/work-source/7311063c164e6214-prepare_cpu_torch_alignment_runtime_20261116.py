"""Isolated official CPU Torch overlay, matching the existing2.11 base version."""
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
import argparse,ctypes,hashlib,json,subprocess,sys,urllib.parse,urllib.request
args_parser=argparse.ArgumentParser();args_parser.add_argument('--revision',type=int,default=1);args=args_parser.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/('joint-architecture-r1/cpu-forced-alignment-r'+str(args.revision));E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')/C.name
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
assert not C.exists() and not E.exists();C.mkdir();E.mkdir();index='https://download.pytorch.org/whl/cpu/torch/'
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':
   value=dict(attrs).get('href')
   if value:self.links.append(urllib.parse.urljoin(index,value))
with urllib.request.urlopen(index,timeout=30) as response:body=response.read(4*1024**2);assert response.read(1)==b''
parser=Links();parser.feed(body.decode());abi=subprocess.check_output([PY,'-c','import sys;print(str(sys.version_info.major)+str(sys.version_info.minor))'],text=True).strip();filename='torch-2.11.0+cpu-cp'+abi+'-cp'+abi+'-win_amd64.whl'
matches=[u for u in parser.links if urllib.parse.unquote(Path(urllib.parse.urlparse(u).path).name)==filename];assert len(matches)==1,'Exact existing Torch base CPU wheel unavailable; no runtime version grid'
url=matches[0];digest=urllib.parse.parse_qs(urllib.parse.urlparse(url).fragment)['sha256'][0];assert len(digest)==64
source={'state':'PINNED_OFFICIAL_TORCH_CPU_OVERLAY_BEFORE_INSTALL','at':datetime.now().astimezone().isoformat(),'url':url,'filename':filename,'sha256':digest,'version':'2.11.0+cpu',
 'index':index,'indexSha256':hashlib.sha256(body).hexdigest(),'sitePackages':str(E/'torch-cpu-site'),'basePython':PY,
 'otherDependencies':'Reuse the existing pinned native Transformers5.22.1 and pure Python processor dependencies. This target shadows only Torch; no existing environment or system packages are modified.',
 'newNeuralCalls':0,'modelWeightsChanged':False,'qualityQualified':False}
atomic_json(C/'runtime-source.json',source);(C/'official-cpu-index.html').write_bytes(body)
state={'state':'INSTALLING_ISOLATED_CPU_TORCH_NO_NEURAL_CALLS','startedAt':source['at'],'source':source,'newNeuralCalls':0}
try:
 with (C/'installation.log').open('xb') as log:
  result=subprocess.run([PY,'-m','pip','install','--no-deps','--no-compile','--only-binary=:all:','--no-cache-dir','--no-input',
   '--target',str(E/'torch-cpu-site'),'--report',str(C/'pip-install-report.json'),url],stdout=log,stderr=subprocess.STDOUT,timeout=900,
   creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 assert result.returncode==0,result.returncode
 report=json.loads((C/'pip-install-report.json').read_text());assert len(report['install'])==1
 installed=report['install'][0];assert installed['metadata']['version']=='2.11.0+cpu' and installed['download_info']['archive_info']['hashes']['sha256']==digest
 state.update(state='COMPLETE_ISOLATED_OFFICIAL_CPU_TORCH_OVERLAY_INSTALLED_MODEL_NOT_LOADED',cpuOverlay=str(E/'torch-cpu-site'))
except BaseException as error:state.update(state='INCOMPLETE_CPU_RUNTIME_PREPARATION_NO_NEURAL_CALLS',error=repr(error));raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),limits=limits.query());atomic_json(C/'runtime-installation.json',state)
print(json.dumps({k:v for k,v in state.items() if k not in ['source','limits']}))
