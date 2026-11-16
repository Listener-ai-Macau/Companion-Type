from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
old=B/'cpu-retained-baseline-alignment-r2';C=B/'cpu-retained-baseline-join-r4';run=E/'cpu-retained-baseline-join-r4';PY='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not run.exists();C.mkdir();run.mkdir()
for name in ['binding.json','whole-scoring-only.json']:(C/name).write_bytes((old/name).read_bytes())
(run/'worker-state.json').write_bytes((E/'cpu-retained-baseline-alignment-full-r2/worker-state.json').read_bytes())
policy=read(old/'composition-binding.json');policy['composerSha256']=sha(S/'compose_cpu_established_speaker_join_20261116.py')
for n in ['companion_local_speaker_document_20261114.py','companion_exclusive_journal_20261114.py','practical_transcript_20261107.py']:policy['files'][str(S/n)]=sha(S/n)
origin=read(B/'cpu-retained-baseline-alignment-r1/frozen-audio-recognized-text-only.json');policy.update(sourceDocument=origin['sourceDocument'],sourceDocumentSha256=origin['sourceDocumentSha256'])
(C/'composition-binding.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
score=read(old/'scoring-binding.json');score['files']={str(C/Path(k).name) if Path(k).parent==old else k:v for k,v in score['files'].items()};score['files'][str(C/'composition-binding.json')]=sha(C/'composition-binding.json');(C/'scoring-binding.json').write_text(json.dumps(score,indent=2)+'\n',encoding='utf-8')
decision={'state':'RESTORE_EXISTING_PRODUCT_ONSET_JOIN_BEFORE_RESCORE_ZERO_NEW_NEURAL_CALLS','at':datetime.now().astimezone().isoformat(),
 'previousComposition':str(E/'cpu-retained-baseline-alignment-full-r2/composition-state.json'),'previousCompositionSha256':sha(E/'cpu-retained-baseline-alignment-full-r2/composition-state.json'),
 'sourceOfRegression':'The new provisional assembler used the earlier full-word interval policy and omitted leaf separators from utterances. The current established product uses onset plus/minus60ms, keeps all source separators, and carries the original predicted exclusive attribution view with raw multi-voice evidence. Reuse that exact existing helper instead of changing any model result or reference.',
 'establishedProductHelperSha256':sha(S/'companion_local_speaker_document_20261114.py'),'previousR6HelperSha256':'c19b0e012f83d4683b40badb2a1d8b2cc1a23e95f805ae49586043afa0c800bb',
 'modelOutputsReused':79,'newNeuralCalls':0,'qualityGateChanged':False,'referenceEdits':False,'qualityQualified':False}
(C/'composition-root-cause.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert decision['establishedProductHelperSha256']=='77fe80c965ed76ca5e9a32480e9c918c7718fb749276ce481c824689d97ce393'
subprocess.run([PY,str(S/'compose_cpu_established_speaker_join_20261116.py'),'--control',str(C),'--run',str(run)],check=True)
subprocess.run([PY,str(S/'score_cpu_qwen_alignment_20261116.py'),'--control',str(C),'--run',str(run)],check=True)
checker=Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe');doc=run/'composed/S_R004S03C01-model-output.json';checked=subprocess.run([str(checker),str(doc),str(round(2327.119*1000))],capture_output=True,text=True)
(C/'product-contract.json').write_text(json.dumps({'exitCode':checked.returncode,'stdout':checked.stdout,'stderr':checked.stderr,'checkerSha256':sha(checker),'documentSha256':sha(doc),'installedNativeUiTested':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');assert checked.returncode==0,checked.stderr
print(json.dumps({'state':'PASS_EXISTING_PRODUCT_JOIN_CHARACTERS_AND_SHARED_RUST_CONTRACT_ZERO_NEW_NEURAL_CALLS','document':str(doc)}))
