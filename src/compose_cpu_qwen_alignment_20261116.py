"""Join immutable CPU ASR/alignment to continuous CPU voices using inherited policy."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_transcript_20261107 import normalized_journal,onset_attribution
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args();limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2)
 B=read(a.control/'binding.json');policy=read(a.control/'composition-binding.json');state=read(a.run/'worker-state.json')
 assert sha(__file__)==policy['composerSha256']
 for file,digest in policy['files'].items():assert sha(file)==digest
 assert state['state']=='COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED' and len(state['completed'])==len(B['cases'])
 done={x['id']:x for x in state['completed']};out=a.run/'composed';assert not out.exists();out.mkdir();results=[]
 for meeting,source in policy['speakerSources'].items():
  assert sha(source['sourceJournal'])==source['sourceJournalSha256'] and sha(source['producer'])==source['producerSha256']
  producer=read(source['producer']);assert not producer['gpuUsed'] and producer['oneContinuousSpeakerState'] and producer['allOriginalAudioSamplesSubmitted']
  raw_journal=read(source['sourceJournal']);journal,mapping=normalized_journal(raw_journal);tokens=[];utterances=[];texts=[];cursor=0;offset=0;alignment_seconds=0.
  for case in [x for x in B['cases'] if x['meeting']==meeting]:
   assert case['sourceStartFrame']==cursor;cursor=case['sourceEndFrame'];saved=done[case['id']];assert sha(saved['file'])==saved['sha256'];packet=read(saved['file']);assert packet['case']==case
   payload=packet['payload'];assert payload['originalText']==case['text']==''.join(x['text'] for x in payload['units']);assert payload['allOriginalCharactersPreserved'];texts.append(case['text']);alignment_seconds+=payload['seconds']
   low_ms=round(case['sourceStartFrame']/16);high_ms=round(case['sourceEndFrame']/16)
   for unit in payload['units']:
    valid=unit['positiveAndInOriginalLeafBounds'];start,end=unit['absoluteStartSeconds'],unit['absoluteEndSeconds']
    if valid:
     assert 0<=start<end<=source['audioSeconds'];identity=onset_attribution((start+end)/2,journal['segments'],duration=source['audioSeconds'],margin=(end-start)/2+.06)
     display_start=max(low_ms,min(high_ms-1,round(start*1000)));display_end=max(display_start+1,min(high_ms,round(end*1000)))
    else:
     assert start is None and end is None;identity={'speaker':None,'candidateSpeakers':[],'attribution':'invalid_predicted_time_original_word_preserved_unknown','overlapDetectedNearOnset':False}
     display_start,display_end=low_ms,high_ms
    tokens.append({**unit,**identity,'sourceChunk':case['id'],'textStart':offset+unit['textStartCodepoint'],'textEnd':offset+unit['textEndCodepoint'],
     'start':start if valid else None,'end':end if valid else None,'intervalPlusInheritedUncertaintyMarginUsed':True,'fixedUncertaintyMarginSeconds':.06})
    utterances.append({'text':unit['text'],'startMs':display_start,'endMs':display_end,'speaker':identity['speaker'],'approximateTiming':True})
   offset+=len(case['text'])+1
  assert cursor==round(source['audioSeconds']*16000)
  text='\n'.join(texts);doc={'isFinal':True,'text':text,'utterances':utterances};target=out/(meeting+'-model-output.json');atomic_json(target,doc)
  review={'meeting':meeting,'audioSha256':source['audioSha256'],'audioSeconds':source['audioSeconds'],'rawWindowText':text,'tokenEstimates':tokens,
   'rawSpeakerJournal':source,'nativeToConsecutiveDisplaySpeakerIds':mapping,'inputFramesCoveredExactlyOnce':cursor,'everyRecognizedCharacterPreserved':True,
   'rawCpuContinuousJournalUsedWithOverlap':True,'sourceAsrAndSpeakerInferenceRerun':False,'wordTimeAccuracyQualified':False,'bothOverlappingVoicesRecovered':False,'qualityQualified':False,
   'alignmentInferenceSeconds':alignment_seconds,'attributionPolicy':'Inherited full predicted word interval plus fixed60ms margin; boundary, gap, overlap and invalid time remain unknown.'}
  review_file=out/(meeting+'-attribution-review.json');atomic_json(review_file,review)
  results.append({'meeting':meeting,'document':str(target),'documentSha256':sha(target),'review':str(review_file),'reviewSha256':sha(review_file),'alignmentUnits':len(tokens),
   'invalidTimeUnits':sum(not x['positiveAndInOriginalLeafBounds'] for x in tokens),'unknownSpeakerUnits':sum(x['speaker'] is None for x in tokens),'alignmentInferenceSeconds':alignment_seconds})
 result={'state':'COMPLETE_CPU_ALIGNMENT_CONTINUOUS_VOICES_ON_RETAINED_ASR_COMPOSITION_NOT_QUALIFIED','at':datetime.now().astimezone().isoformat(),'meetings':results,
  'sourceAsrInferenceBackend':policy['sourceAsrInferenceBackend'],'wholeAsrAlignmentSpeakerCpuRerun':False,
  'newAsrNeuralCalls':0,'newSpeakerNeuralCalls':0,'noReferencesRead':True,'originalAttributionMarginUnchanged':True,'qualityQualified':False,'productDefaultChanged':False,'limits':limits.query()}
 atomic_json(a.run/'composition-state.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
