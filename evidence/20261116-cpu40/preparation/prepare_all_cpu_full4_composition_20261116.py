"""Reuse all completed ASR outputs; new full-source CPU speaker predictions only."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
native=E/'cpu-native8-r2';closed=read(native/'run.json');assert closed['state']=='COMPLETE_CPU_ONLY_NATIVE8_FULL4_NOT_QUALIFIED' and closed['cpu61ControlPassed'] and len(closed['results'])==4
old=B/'cpu-fixed-whole-r2';asr=E/old.name;C=B/'all-cpu-full4-composition-r1';out=E/C.name
assert not C.exists() and not out.exists();C.mkdir();out.mkdir()
original_sources=read(old/'predicted-speaker-bindings.json')['sources'];sources={}
for case in read(native/'audio-only.json')[1:]:
 meeting=case['meeting'];directory=native/'results'/meeting;cache=native/'probabilities'/meeting
 producer=read(directory/'completed-state.json');prob=read(cache/'probabilities.json')
 assert producer['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' and producer['gpuUsed'] is False
 assert producer['allOriginalAudioSamplesSubmitted'] and producer['oneContinuousSpeakerState'] and producer['audioSha256']==case['audioSha256']
 assert producer['completedNeuralFrames']==prob['committedFrames'] and producer['probabilityManifestSha256']==sha(cache/'probabilities.json')
 assert producer['rttmSha256']==sha(directory/'predicted.rttm') and prob['nativeLibrarySha256']==read(native/'protocol.json')['nativeLibrarySha256']
 sources[meeting]={'probabilities':str(cache/'probabilities.npy'),'probabilitiesSha256':sha(cache/'probabilities.npy'),
  'frames':prob['committedFrames'],'cadence':producer['nativeSecondsPerFrame'],'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],
  'sourceJournal':str(directory/'speaker-journal.json'),'sourceJournalSha256':sha(directory/'speaker-journal.json'),
  'producer':str(directory/'completed-state.json'),'producerSha256':sha(directory/'completed-state.json'),
  'protocol':str(native/'protocol.json'),'protocolSha256':sha(native/'protocol.json'),'modelSha256':prob['modelSha256'],
  'backendOriginallyVulkan':False,'executionDevice':'cpu','probabilityManifest':str(cache/'probabilities.json'),'probabilityManifestSha256':sha(cache/'probabilities.json'),
  'comparisonOriginalGpuSource':original_sources[meeting]}
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
write(C/'predicted-speaker-bindings.json',{'at':datetime.now().astimezone().isoformat(),'sources':sources,'referenceInputToModels':False})
for name in ['binding.json','whole-scoring-only.json']:shutil.copyfile(old/name,C/name)
shutil.copyfile(asr/'inference-state.json',out/'inference-state.json')
combined={'state':'COMPLETE_REUSED_CPU_ASR_AND_NEW_CPU_SPEAKER_NOT_QUALIFIED','at':datetime.now().astimezone().isoformat(),
 'asrRun':str(asr/'run.json'),'asrRunSha256':sha(asr/'run.json'),'speakerRun':str(native/'run.json'),'speakerRunSha256':sha(native/'run.json'),
 'asrOutputsRerun':0,'originalAsrInputCount':290,'newNeuralCallsByComposition':0,'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False}
write(out/'run.json',combined)
# A separate derived scorer changes only CPU provenance/baseline comparison;
# original reference aliases, raw text scoring and quality gates stay intact.
summary=S/'score_cpu_fixed_whole_summary_20261116.py';text=summary.read_text(encoding='utf-8')
before="raw_der=activity_score(activity,original_rows,case['audioSeconds']);assert abs(raw_der['DER']-case['baselineDER'])<1e-8,(meeting,raw_der['DER'],case['baselineDER'])"
after="""raw_der=activity_score(activity,original_rows,case['audioSeconds'])
  previous_source=source['comparisonOriginalGpuSource'];assert sha(previous_source['producer'])==previous_source['producerSha256']
  previous_rttm=Path(previous_source['sourceJournal']).with_name('predicted.rttm')
  assert sha(previous_rttm)==read(previous_source['producer'])['rttmSha256']
  original_gpu_der=activity_score(activity,rttm(previous_rttm),case['audioSeconds'])
  assert abs(original_gpu_der['DER']-case['baselineDER'])<1e-8,(meeting,original_gpu_der['DER'],case['baselineDER'])"""
assert text.count(before)==1;text=text.replace(before,after)
text=text.replace("'originalNemotronRawDERReproduced':raw_der","'originalNemotronRawDERReproduced':original_gpu_der")
text=text.replace("'fullCpuSpeakerModelRuntimeMeasured':False","'fullCpuSpeakerModelRuntimeMeasured':True")
text=text.replace("FULL4_FIXED_CPU_COMPOSITION_SCORED_NOT_PRODUCT_QUALIFIED","FULL4_ALL_CPU_COMPOSITION_SCORED_NOT_PRODUCT_QUALIFIED")
text=text.replace('The authoritative raw multi-voice Nemotron journal reuses original GPU predictions; its original DER remains unchanged. CPU speaker execution remains a separate required check.',
 'The authoritative raw multi-voice Nemotron journal is from actual CPU-only continuous full-source inference. Original GPU baseline DER is independently reproduced; no cross-backend bitwise parity is assumed.')
variant=S/'score_all_cpu_full4_summary_20261116.py';assert not variant.exists();variant.write_text(text,encoding='utf-8');compile(text,str(variant),'exec')
frozen=read(old/'composition-source-binding.json');frozen.update(summaryScorerSha256=sha(variant),predictedBindingsSha256=sha(C/'predicted-speaker-bindings.json'),
 cpuMetadataAdapterSha256=sha(S/'compose_cpu_native8_full4_20261116.py'),originalSummarySourceSha256=sha(summary),originalSummarySource=str(summary))
write(C/'composition-source-binding.json',frozen)
print(json.dumps({'control':str(C),'run':str(out),'newAsrCalls':0,'cpuSpeakerFull4':True}))
