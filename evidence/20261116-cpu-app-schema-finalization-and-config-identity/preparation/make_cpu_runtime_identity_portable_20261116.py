from pathlib import Path
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/cpu-pcm-candidate-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-pcm-candidate-r1')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
B=read(C/'binding.json');old=read(C/'runtime-contract.json');assert B['runtimeContractSha256']==sha(C/'runtime-contract-before-portable-identity.json')
folder=Path(B['library']).parent
new={'schema':'companion.native-cpu-content-contract.v1','baseArchiveSha256':old['baseArchiveSha256'],'nativeVersion':old['nativeVersion'],'nativeCommit':old['nativeCommit'],
 'files':[{'relativeFile':Path(r['file']).relative_to(folder).as_posix(),'bytes':r['bytes'],'sha256':r['sha256']} for r in old['files']],
 'cpuOnly':True,'change':'Optional Vulkan plugin omitted, all retained CPU and license bytes exactly match the original pinned archive. Content identity is independent of the installation directory.'}
for r in B['runtimeFiles']:assert sha(r['file'])==r['sha256']
for p in [C/'runtime-contract.json',E/'runtime-contract.json']:p.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
B['runtimeContractSha256']=sha(C/'runtime-contract.json');B['runtimeIdentityPreparationCorrection']='Use names, sizes, hashes and pinned release for the inference contract rather than absolute installation paths. All numerical/runtime bytes unchanged; before actual CPU PCM inference. Previous absolute-path contract preserved.'
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'runtimeContractSha256':B['runtimeContractSha256'],'runtimeBytesChanged':False,'neuralCalls':0}))
