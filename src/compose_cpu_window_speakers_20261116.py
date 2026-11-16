"""Link predicted local speakers to a predicted whole-source journal, without gold."""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,math,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.optimize import linear_sum_assignment
from companion_exclusive_journal_20261114 import exclusive_journal
from score_sequential_speakers_20261115 import intervals,overlap_seconds,union
from score_joint_whole_meetings_20261115 import parse_native
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
 B=read(a.control/'composition-input.json');assert sha(__file__)==B['composerSha256']
 for file,digest in B['helperSha256'].items():assert sha(file)==digest
 state=read(a.run/'inference-state.json');assert state['state']=='COMPLETE_CPU_WINDOW_COHORT_COMPOSITION_AND_SCORING_PENDING'
 assert len(state['completed'])==32 and len(B['cases'])==32
 journals={};receipts=[]
 for meeting,source in B['sources'].items():
  bound=source['probabilities'];assert sha(bound['file'])==bound['sha256']
  data=np.load(bound['file'],allow_pickle=False);frames=len(data);assert data.shape[1]==8
  active=np.zeros(data.shape,dtype=bool)
  for k in range(8):
   v=data[:,k];last=np.maximum.accumulate(np.where(v!=.5,np.arange(frames),-1));active[:,k]=(last>=0)&(v[np.maximum(last,0)]>.5)
  source_journal={'segments':intervals(active,source['audioSeconds']),'audioSeconds':source['audioSeconds'],'audioSha256':source['audioSha256']}
  journal,receipt=exclusive_journal(data,frames=frames,seconds_per_frame=.01,source_journal=source_journal)
  journals[meeting]=journal['segments'];receipts.append({'meeting':meeting,'probabilities':bound,'receipt':receipt})
 out=a.run/'composition';assert not out.exists();out.mkdir();completed=[]
 meta={r['id']:r for r in B['cases']}
 for item in state['completed']:
  assert sha(item['file'])==item['sha256'];packet=read(item['file']);case=packet['case'];m=meta[case['id']]
  assert packet['naturalEos'] and not packet['wasTruncated'] and case['wavSha256']==m['wavSha256']
  parsed,rows,residual=parse_native(packet['rawDecoded']);seconds=case['audioSeconds'];offset=m['sourceStartFrame']/16000
  valid=lambda r: r['speaker'] is not None and math.isfinite(r['start']) and 0<=r['start']<r['end']<=seconds+.1
  local=sorted({r['speaker'] for r in rows if valid(r)})
  global_ids=sorted({r['speaker'] for r in journals[case['meeting']]})
  matrix=np.zeros((len(local),len(global_ids)))
  for i,s in enumerate(local):
   selected=union([dict(r,start=offset+r['start'],end=offset+r['end']) for r in rows if valid(r) and r['speaker']==s])
   for j,g in enumerate(global_ids):matrix[i,j]=overlap_seconds(selected,[r for r in journals[case['meeting']] if r['speaker']==g])
  rr,cc=linear_sum_assignment(-matrix);mapping={local[i]:global_ids[j] for i,j in zip(rr,cc) if matrix[i,j]>0}
  composed=[]
  for i,r in enumerate(rows):
   native=mapping.get(r['speaker']) if valid(r) else None
   composed.append({'index':i,'text':r['text'],'localSpeaker':r['speaker'],'nativeWholeMeetingSpeaker':native,
    'start':r['start'] if math.isfinite(r['start']) else None,'end':r['end'] if math.isfinite(r['end']) else None,
    'attribution':'predicted_identity_overlap_assignment' if native is not None else 'UNKNOWN'})
  payload={'id':case['id'],'meeting':case['meeting'],'rawFile':item['file'],'rawSha256':item['sha256'],
   'rows':composed,'localToNativeGlobal':mapping,'overlapSecondsMatrix':matrix.tolist(),'matrixLocalOrder':local,'matrixGlobalOrder':global_ids,
   'sourceStartFrame':m['sourceStartFrame'],'residual':residual,'referenceRead':False,'trueSpeakerCountRead':False,
   'mappingUsesPredictionsOnly':True,'unknownRetained':True,'wordsRewritten':False,'wholeMeetingAcceptance':False}
  target=out/(case['id']+'.json');atomic_json(target,payload);completed.append({'id':case['id'],'file':str(target),'sha256':sha(target)})
 result={'state':'COMPLETE_CPU_WINDOW_COMPOSITION_NOT_QUALIFIED','completed':completed,'sourceJournalReceipts':receipts,
  'composerSha256':sha(__file__),'bindingSha256':sha(a.control/'composition-input.json'),'referenceRead':False,
  'wholeMeetingIdentityJournalReusedUnchanged':True,'newSpeakerRuntimeOnCpuMeasured':False,'qualityQualified':False,'wholeMeetingAcceptance':False,'limits':limits.query()}
 atomic_json(a.run/'composition-state.json',result);print(json.dumps({'state':result['state'],'cases':len(completed)}))
if __name__=='__main__':main()
