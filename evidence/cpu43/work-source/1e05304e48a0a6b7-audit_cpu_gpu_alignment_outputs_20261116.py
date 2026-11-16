from pathlib import Path
from datetime import datetime
import hashlib,json,statistics
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
plan=read(B/'cpu-retained-baseline-alignment-r2/binding.json');done={r['id']:r for r in read(E/'cpu-retained-baseline-alignment-full-r2/worker-state.json')['completed']};old=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/normal-turn-r6-alignment-r1/aligned/S_R004S03C01'
raw_deltas=[];time_deltas=[];old_invalid=new_invalid=units=0;files=[]
for case in plan['cases']:
 p=old/(case['id']+'.json');entry=done[case['id']];assert sha(entry['file'])==entry['sha256'];a=read(p)['payload'];b=read(entry['file'])['payload']
 assert a['originalText']==b['originalText']==case['text'];assert len(a['units'])==len(b['units'])
 assert [x['text'] for x in a['units']]==[x['text'] for x in b['units']]
 left=a.get('rawTimestampClassIds',[]);right=b.get('rawTimestampClassIds',[]);assert len(left)==len(right)
 raw_deltas.extend(abs(x-y) for x,y in zip(left,right))
 for x,y in zip(a['units'],b['units']):
  assert x['alignmentUnit']==y['alignmentUnit'];units+=1
  old_invalid+=not x['positiveAndInOriginalLeafBounds'];new_invalid+=not y['positiveAndInOriginalLeafBounds']
  time_deltas.extend(abs(x[k]-y[k]) for k in ['predictedStartSeconds','predictedEndSeconds'])
 files.append({'leaf':case['id'],'oldGpu':str(p),'oldGpuSha256':sha(p),'cpu':entry['file'],'cpuSha256':entry['sha256']})
q=lambda xs,p:sorted(xs)[min(len(xs)-1,int(len(xs)*p))]
result={'state':'CPU_GPU_SAME_RETAINED_ASR_ALIGNMENT_DIAGNOSTIC_NOT_TRUE_WORD_TIME_ACCEPTANCE','at':datetime.now().astimezone().isoformat(),'leaves':len(plan['cases']),'alignmentUnits':units,
 'rawTimestampClassCount':len(raw_deltas),'identicalRawTimestampClasses':sum(x==0 for x in raw_deltas),'rawClassDeltaMedian':statistics.median(raw_deltas),'rawClassDeltaP95':q(raw_deltas,.95),
 'decodedTimestampDeltaMedianSeconds':statistics.median(time_deltas),'decodedTimestampDeltaP95Seconds':q(time_deltas,.95),'decodedTimestampDeltaMaxSeconds':max(time_deltas),
 'oldGpuInvalidOrZeroDurationWordIntervals':old_invalid,'cpuInvalidOrZeroDurationWordIntervals':new_invalid,'inputAndCharactersExactlyEqual':True,
 'newNeuralCalls':0,'bitwiseCpuGpuParityClaimed':False,'trueWordTimeAccuracyMeasured':False,'currentProductUsesOnsetsOnlyWithFixed60msNotWordDuration':True,
 'wholeAsrWasPreviousProtectedGpuResult':True,'files':files,'qualityQualified':False}
target=B/'cpu-retained-baseline-join-r4/cpu-gpu-output-diagnostic.json';assert not target.exists();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='files'}))
