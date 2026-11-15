"""Invoke the unchanged original scorer after validating exact case bindings."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,runpy,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True)
p.add_argument('--phase',choices=['baseline','candidate'],required=True);p.add_argument('--run',type=Path);a=p.parse_args()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
protocol=read(a.control/'protocol.json');assert sha(protocol['scorer'])==protocol['scorerSha256']
baseline=read(a.control/'baseline-binding.json')
if a.phase=='baseline':
 rttm=Path(baseline['rttm']);assert sha(rttm)==baseline['rttmSha256']
 output=a.control/'baseline-reproduced-score.json'
else:
 assert a.run is not None
 state=read(a.run/'state.json');assert state['state']=='COMPLETE_WHOLE_COMMUNITY1_ORIGINAL_SCORE_PENDING'
 receipt=read(a.run/'output/output-receipt.json');rttm=a.run/'output/predicted.rttm'
 assert sha(rttm)==receipt['regularRttmSha256'] and receipt['exclusiveOutputUsedForQualification'] is False
 raw=a.run/'output/raw-output.json';assert sha(raw)==receipt['rawOutputSha256']
 actual=read(raw);expected=read(a.control/'scoring-case.json')
 assert actual['audioSha256']==expected['audioSha256']==state['pcm']['sourceWavSha256']
 assert actual['audioSeconds']==expected['audioSeconds']
 assert actual['binding']['protocolSha256']==state['protocolSha256']==sha(a.control/'protocol.json')
 output=a.run/'original-reference-score.json'
assert not output.exists()
sys.argv=[protocol['scorer'],'--case',str(a.control/'scoring-case.json'),'--rttm',str(rttm),'--out',str(output)]
runpy.run_path(protocol['scorer'],run_name='__main__')
score=read(output)
if a.phase=='baseline':
 for key,value in baseline['originalComponents'].items():assert abs(score['components'][key]-value)<1e-9,(key,score['components'][key],value)
 result={'state':'PASS_ORIGINAL_FULL_DER_COMPONENTS_REPRODUCED_BEFORE_CANDIDATE_OUTPUT',
  'components':score['components'],'originalScoreSha256':baseline['originalScoreSha256'],'newNeuralCalls':0}
else:
 result={'state':'COMPLETE_FIXED_COMMUNITY1_ORIGINAL_REFERENCE_SCORE',
  'baseline':baseline['originalComponents'],'candidate':score['components'],
  'strictSpeakerDerPass':score['components']['diarization error rate']<=.10,
  'perPersonDetail':score['perReferenceSpeakerForEvaluationOnly'],'automaticProductAdoption':False}
result.update(at=datetime.now().astimezone().isoformat(),qualityQualified=False,fullMeetingGatesChanged=False,limits=limits.query())
target=output.with_name(output.stem+'-receipt.json');assert not target.exists()
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
