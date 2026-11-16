"""Complete original recordings, fixed CPU windows, prediction-only stable identities."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,math,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.optimize import linear_sum_assignment
from companion_exclusive_journal_20261114 import exclusive_journal
from score_sequential_speakers_20261115 import overlap_seconds,union
from score_joint_whole_meetings_20261115 import parse_native,units
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
 frozen=read(a.control/'composition-source-binding.json');assert sha(__file__)==frozen['composerSha256']
 for path,digest in frozen['helperSha256'].items():assert sha(path)==digest
 assert sha(a.control/'predicted-speaker-bindings.json')==frozen['predictedBindingsSha256']
 B=read(a.control/'binding.json');sources=read(a.control/'predicted-speaker-bindings.json')['sources'];inference=read(a.run/'inference-state.json')
 assert inference['state']=='COMPLETE_CPU_FIXED_CHUNKS_COMPOSITION_AND_SCORING_PENDING' and len(inference['completed'])==len(B['cases'])
 completed={r['id']:r for r in inference['completed']};out=a.run/'composed';assert not out.exists();out.mkdir();results=[]
 for case in B['meetings']:
  source=sources[case['meeting']]
  assert sha(source['probabilities'])==source['probabilitiesSha256'] and sha(source['sourceJournal'])==source['sourceJournalSha256']
  data=np.load(source['probabilities'],mmap_mode='r',allow_pickle=False)
  journal,receipt=exclusive_journal(data,frames=source['frames'],seconds_per_frame=source['cadence'],source_journal=read(source['sourceJournal']))
  global_ids=sorted({r['speaker'] for r in journal['segments']});trace=[];all_rows=[];raw_parts=[];source_units=[];cursor=0;incomplete=[];invalid=[];seconds=0.
  for chunk in [r for r in B['cases'] if r['meeting']==case['meeting']]:
   item=completed[chunk['id']];assert sha(item['file'])==item['sha256'];packet=read(item['file']);assert packet['case']==chunk and packet['originalChunkInputComplete']
   assert cursor==chunk['sourceStartFrame'];cursor=chunk['sourceEndFrame'];offset=chunk['sourceStartFrame']/16000
   parsed,rows,residual=parse_native(packet['rawDecoded']);source_units.extend(v for r in rows for v in units(r['text'],case['language']))
   valid=lambda r: r['speaker'] is not None and math.isfinite(r['start']) and 0<=r['start']<r['end']<=chunk['audioSeconds']
   local=sorted({r['speaker'] for r in rows if valid(r)});matrix=np.zeros((len(local),len(global_ids)))
   for i,s in enumerate(local):
    selected=union([dict(r,start=offset+r['start'],end=offset+r['end']) for r in rows if valid(r) and r['speaker']==s])
    for j,g in enumerate(global_ids):matrix[i,j]=overlap_seconds(selected,[r for r in journal['segments'] if r['speaker']==g])
   rr,cc=linear_sum_assignment(-matrix);mapping={local[i]:global_ids[j] for i,j in zip(rr,cc) if matrix[i,j]>0}
   for i,r in enumerate(rows):
    native=mapping.get(r['speaker']) if valid(r) else None
    good=valid(r) and offset+r['end']<=case['audioSeconds']
    if r['speaker'] is not None and not good:invalid.append({'chunk':chunk['id'],'row':i,'start':r['start'],'end':r['end']})
    if native is not None and good:
     start,end=offset+r['start'],offset+r['end'];raw_parts.append('['+repr(start)+'][S'+str(native).zfill(2)+']'+r['text']+'['+repr(end)+']')
    else:
     native=None;start=end=None;raw_parts.append(r['text'])
    all_rows.append({'chunk':chunk['id'],'localIndex':i,'text':r['text'],'nativeGlobalSpeaker':native,'start':start,'end':end,'localSpeaker':r['speaker']})
   trace.append({'chunk':chunk['id'],'rawFile':item['file'],'rawSha256':item['sha256'],'localToNativeGlobal':mapping,'matrixLocalOrder':local,'matrixGlobalOrder':global_ids,'overlapSecondsMatrix':matrix.tolist()})
   if not packet['naturalEos']:incomplete.append(chunk['id'])
   seconds+=packet['seconds']
  assert cursor==case['frames']
  raw='\n'.join(raw_parts);parsed,assembled,residual=parse_native(raw)
  assert [v for r in assembled for v in units(r['text'],case['language'])]==source_units,'Composition changed or dropped original lexical units'
  packet={'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'rawDecoded':raw,
   'naturalEos':not incomplete,'completeOriginalRecordingInput':True,'inputFramesCoveredExactlyOnce':cursor,'chunkCount':len(trace),'incompleteOutputChunks':incomplete,
   'invalidOriginalTimeSegments':invalid,'allOriginalLexicalUnitsPreserved':True,'cpuAsrInferenceSeconds':seconds,'backend':'CPU',
   'speakerJournalBackend':'REUSED_ORIGINAL_VULKAN_PREDICTIONS_CPU_JOURNAL_RUNTIME_NOT_YET_MEASURED','referenceRead':False,
   'qualityQualified':False,'wholeMeetingAcceptance':False,'productDefaultChanged':False,'newTraining':False}
  target=out/(case['meeting']+'-raw.json');atomic_json(target,packet)
  atomic_json(out/(case['meeting']+'-composition.json'),{'case':case,'rows':all_rows,'trace':trace,'source':source,'sourceJournalReceipt':receipt,'referencesRead':False})
  atomic_json(out/(case['meeting']+'-primary-speaker-journal.json'),journal)
  results.append({'meeting':case['meeting'],'file':str(target),'sha256':sha(target),'frames':cursor,'audioSeconds':case['audioSeconds'],'cpuAsrInferenceSeconds':seconds,'chunks':len(trace),'incompleteOutputChunks':incomplete,'invalidTimeCount':len(invalid)})
 result={'at':datetime.now().astimezone().isoformat(),'state':'COMPLETE_CPU_FIXED_FULL4_COMPOSITION_NOT_QUALIFIED','meetings':results,
  'composerSha256':sha(__file__),'referenceRead':False,'wholeMeetingAcceptance':False,'qualityQualified':False,'newTraining':False,'limits':limits.query()}
 atomic_json(a.run/'composition-state.json',result);print(json.dumps({k:v for k,v in result.items() if k!='limits'},ensure_ascii=False))
if __name__=='__main__':main()
