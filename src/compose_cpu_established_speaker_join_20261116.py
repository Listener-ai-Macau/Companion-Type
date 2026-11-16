"""Use the existing product's exact onset join, not a newly invented word policy."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from companion_local_speaker_document_20261114 import join_aligned_recording
from companion_exclusive_journal_20261114 import exclusive_journal
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args();limits=WorkerLimits(cpu_percent=1,memory_bytes=512*1024**2)
 B=read(a.control/'binding.json');policy=read(a.control/'composition-binding.json');assert sha(__file__)==policy['composerSha256']
 for file,digest in policy['files'].items():assert sha(file)==digest
 state=read(a.run/'worker-state.json');assert state['state']=='COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED';done={r['id']:r for r in state['completed']}
 assert len(done)==len(B['cases']);out=a.run/'composed';assert not out.exists();out.mkdir();results=[]
 for meeting,source in policy['speakerSources'].items():
  for key in ['probabilities','sourceJournal','producer']:assert sha(source[key])==source[key+'Sha256']
  producer=read(source['producer']);assert not producer['gpuUsed'] and producer['oneContinuousSpeakerState']
  raw_journal=read(source['sourceJournal']);array=np.load(source['probabilities'],mmap_mode='r',allow_pickle=False)
  view,derivation=exclusive_journal(array,frames=source['frames'],seconds_per_frame=source['cadence'],source_journal=raw_journal)
  leaves=[];payloads=[];seconds=0.
  for case in [r for r in B['cases'] if r['meeting']==meeting]:
   item=done[case['id']];assert sha(item['file'])==item['sha256'];packet=read(item['file']);assert packet['case']==case;payload=packet['payload']
   assert payload['originalText']==case['text']==''.join(u['text'] for u in payload['units'])
   leaves.append({'id':case['id'],'text':case['text'],'startSample':case['sourceStartFrame'],'endSample':case['sourceEndFrame']})
   payloads.append(dict(payload,originalStartSample=case['sourceStartFrame'],originalEndSample=case['sourceEndFrame']));seconds+=payload['seconds']
  original=read(policy['sourceDocument']);assert sha(policy['sourceDocument'])==policy['sourceDocumentSha256']
  document,trace=join_aligned_recording(original,leaves,payloads,raw_journal,audio_seconds=source['audioSeconds'],audio_sha256=source['audioSha256'],attribution_journal=view)
  assert document['text']==original['text']==''.join(x['text'] for x in document['utterances'])
  tokens=[dict(x,start=x['estimatedOnsetSeconds'],end=min(source['audioSeconds'],x['estimatedOnsetSeconds']+.06) if x['estimatedOnsetSeconds'] is not None else None) for x in trace['tokenEstimates']]
  target=out/(meeting+'-model-output.json');atomic_json(target,document)
  review=dict(trace,meeting=meeting,audioSha256=source['audioSha256'],audioSeconds=source['audioSeconds'],rawWindowText=document['text'],tokenEstimates=tokens,
   rawSpeakerJournal=source,sourceAsrInferenceBackend=policy['sourceAsrInferenceBackend'],fixedUncertaintyMarginSeconds=.06,onsetOnlyNotWordDuration=True,
   everyRecognizedCharacterPreserved=True,wordTimeAccuracyQualified=False,bothOverlappingVoicesRecovered=False,qualityQualified=False,alignmentInferenceSeconds=seconds)
  review_file=out/(meeting+'-attribution-review.json');atomic_json(review_file,review);atomic_json(out/(meeting+'-exclusive-view.json'),{'view':view,'derivation':derivation,'primaryRawMultiVoiceDERUnchanged':True})
  results.append({'meeting':meeting,'document':str(target),'documentSha256':sha(target),'review':str(review_file),'reviewSha256':sha(review_file),'alignmentUnits':len(tokens),
   'invalidTimeUnits':sum(not x['positiveAndInOriginalLeafBounds'] for x in tokens),'invalidOnsetUnits':sum(x['estimatedOnsetSeconds'] is None for x in tokens),
   'unknownSpeakerUnits':sum(x['speaker'] is None for x in tokens),'alignmentInferenceSeconds':seconds,'utterances':len(document['utterances'])})
 result={'state':'COMPLETE_CPU_ALIGNMENT_CONTINUOUS_VOICES_ON_RETAINED_ASR_COMPOSITION_NOT_QUALIFIED','at':datetime.now().astimezone().isoformat(),'meetings':results,
  'sourceAsrInferenceBackend':policy['sourceAsrInferenceBackend'],'wholeAsrAlignmentSpeakerCpuRerun':False,'newAsrNeuralCalls':0,'newSpeakerNeuralCalls':0,
  'noReferencesRead':True,'existingProductJoinReusedExactly':True,'originalAttributionMarginUnchanged':True,'qualityQualified':False,'productDefaultChanged':False,'limits':limits.query()}
 atomic_json(a.run/'composition-state.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
