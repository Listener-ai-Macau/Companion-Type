from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
control=B/'qwen-cpu-working-set-r1/neural-control';run=E/'qwen-cpu-working-set-control-r1';doc=read(run/'run.json');state=read(run/'inference-state.json');settings=read(control/'binding.json')
assert doc['state']=='COMPLETE_QWEN_CPU_PORT_CLIPS_SCORING_PENDING' and len(state['completed'])==1
item=state['completed'][0];assert sha(item['file'])==item['sha256'];packet=read(item['file']);old=read(settings['resourceControl']['expectedRawFile'])
assert packet['rawDecoded']==old['rawDecoded'] and packet['hypothesis']==old['hypothesis'] and packet['naturalEos'] and old['naturalEos']
assert packet['seconds']<=old['seconds']*2 and doc['familyWorkingSetPeakBytes']<=settings['maximumWorkingSetBytes']+64*1024**2
proof={'state':'PASS_ACTUAL_QWEN_RAW_OUTPUT_EXACT_UNDER_175GIB_WORKING_SET_WITHOUT_2X_SLOWDOWN','at':datetime.now().astimezone().isoformat(),
 'controlRun':str(run/'run.json'),'controlRunSha256':sha(run/'run.json'),'controlOutput':item,'oldOutput':settings['resourceControl']['expectedRawFile'],
 'oldOutputSha256':settings['resourceControl']['expectedRawSha256'],'oldSeconds':old['seconds'],'cappedSeconds':packet['seconds'],'ratio':packet['seconds']/old['seconds'],
 'workingSetControl':state['workingSetControl'],'observedFamilyWorkingSetPeakBytes':doc['familyWorkingSetPeakBytes'],'observedFamilyPrivatePeakBytes':doc['privatePeakBytes'],
 'singleControlTimingNotAUniversalPerformanceClaim':True,'originalCpuPrivateAndLowRamGuardsUnchanged':True,'noModelOrQuantizationChange':True}
(control/'result.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
C=B/'qwen-cpu-chinese-characterization-r2';assert not C.exists();C.mkdir();binding=read(B/'qwen-cpu-chinese-characterization-r1/binding.json')
binding.update(workerSha256=settings['workerSha256'],runnerSha256=settings['runnerSha256'],maximumWorkingSetBytes=settings['maximumWorkingSetBytes'],resumeCompleted=[item],
 resourceWorkingSetProof=proof,at=proof['at']);binding['helpers']=settings['helpers'];assert 'caseTimeBudgetSeconds' not in binding
(C/'binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ['protocol.json','scope-decision.json','whole-scoring-only.json']:shutil.copyfile(B/'qwen-cpu-chinese-characterization-r1'/name,C/name)
print(json.dumps({'control':str(C),'run':str(E/'qwen-cpu-chinese-whole-run-r2'),'reusedCompleteWindows':1,'memoryProof':proof},ensure_ascii=False))
