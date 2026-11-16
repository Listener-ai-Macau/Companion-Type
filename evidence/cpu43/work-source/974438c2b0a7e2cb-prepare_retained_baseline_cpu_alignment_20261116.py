from pathlib import Path
from datetime import datetime
import hashlib,json,os,py_compile,subprocess,sys,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from practical_io_20261107 import atomic_json
from score_joint_whole_meetings_20261115 import lexical_references,units,measure
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=1,memory_bytes=512*1024**2)
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
C=B/'cpu-retained-baseline-alignment-r1';data=E/'cpu-retained-baseline-alignment-input-r1';assert not (C/'preparation.json').exists();C.mkdir(exist_ok=True);data.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
prior=read(E/'cpu-forced-alignment-control-r2/worker-state.json');assert prior['state']=='COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED' and prior['tinyControlPassed']
old=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/normal-turn-r6-alignment-r1';origin=read(old/'audio-text-only.json')[0];assert origin['meeting']=='S_R004S03C01' and sha(origin['sourceDocument'])==origin['sourceDocumentSha256']
assert sha(origin['audio'])==origin['audioSha256'];source_document=read(origin['sourceDocument']);assert source_document['text']=='\n'.join(x['text'] for x in origin['leaves'])
cases=[];cursor=0
with wave.open(origin['audio'],'rb') as original:
 for leaf in origin['leaves']:
  assert leaf['startSample']==cursor and sha(leaf['nodeFile'])==leaf['nodeSha256'];cursor=leaf['endSample'];node=read(leaf['nodeFile']);assert node['raw']['text']==leaf['text']
  original.setpos(leaf['startSample']);pcm=original.readframes(leaf['endSample']-leaf['startSample']);dest=data/(leaf['id']+'.wav')
  if node['raw'].get('exactDigitalSilence'):
   assert not any(pcm) and not node['raw']['neuralInferencePerformed'] and leaf['text']==''
  else:assert node['raw']['naturalEos'] and node['raw']['inputNotTruncated']
  if dest.exists():
   with wave.open(str(dest),'rb') as f:assert (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes())==(1,2,16000,len(pcm)//2) and f.readframes(f.getnframes())==pcm
  else:
   with wave.open(str(dest),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm)
  cases.append({'id':leaf['id'],'meeting':origin['meeting'],'wav':str(dest),'wavSha256':sha(dest),'pcmSha256':hashlib.sha256(pcm).hexdigest(),
   'frames':leaf['endSample']-leaf['startSample'],'sourceStartFrame':leaf['startSample'],'sourceEndFrame':leaf['endSample'],'text':leaf['text'],'language':'Chinese',
   'rawAsrFile':leaf['nodeFile'],'rawAsrSha256':leaf['nodeSha256'],'rawAsrTextPath':['raw','text'],'asrInferenceOrigin':'Protected native GPU Qwen result retained unchanged; this run only ports alignment and uses prior CPU voice journal.'})
 assert cursor==original.getnframes()
atomic_json(C/'frozen-audio-recognized-text-only.json',{'meeting':origin['meeting'],'audioSha256':origin['audioSha256'],'sourceDocument':origin['sourceDocument'],'sourceDocumentSha256':origin['sourceDocumentSha256'],'cases':cases,'referencePassedToModel':False,'newAsrCalls':0})
old_worker=subprocess.check_output(['git','-C',str(R/'model-research'),'show','f7c667cdb4c7cc79f1fc3c6631325926a8e983be:src/cpu_forced_alignment_worker_20261116.py']).decode('utf-8');new_worker=(S/'cpu_forced_alignment_worker_20261116.py').read_text(encoding='utf-8')
core=lambda t:t.split("    with wave.open(case['wav'],'rb') as source:",1)[1].split("    state['newNeuralCalls']+=1",1)[0]
assert core(old_worker)==core(new_worker)
atomic_json(C/'worker-source-port-proof.json',{'oldProtectedCommit':'f7c667cdb4c7cc79f1fc3c6631325926a8e983be','newWorkerSha256':sha(S/'cpu_forced_alignment_worker_20261116.py'),
 'pcmProcessorForwardTimestampAndTextMappingCoreUnchanged':True,'modelCoreSha256':hashlib.sha256(core(new_worker).encode()).hexdigest(),'onlyAdded':'Explicit recognized-text JSON key path and exact-source accepted-leaf reuse, without changing model math or weights.'})
binding=read(B/'cpu-forced-alignment-control-r2/binding.json');binding.pop('correctedBeforeAnyModelNeuralCall',None);binding['workerSha256']=sha(S/'cpu_forced_alignment_worker_20261116.py')
for file,digest in read(old/'protocol.json')['runtimeSources'].items():assert sha(file)==digest;binding['helpers'][file]=digest
binding['reuseTinyControl']={'file':str(E/'cpu-forced-alignment-control-r2/tiny-control.json'),'sha256':sha(E/'cpu-forced-alignment-control-r2/tiny-control.json')}
binding.update(cases=cases[:1],sourceAsrInferenceBackend='Protected native GPU ASR reused; only timestamp classifier and independent speaker journal are CPU.',scope='Existing preferred native single-mic no-overlap full development recording; one changed-input first-leaf pilot then unchanged full classifier port. No failed Q8 ASR expansion or new recognition.')
(C/'pilot').mkdir();atomic_json(C/'pilot/binding.json',binding)
case=read(B/'qwen-cpu-chinese-characterization-r2/whole-scoring-only.json')['cases'][0];assert case['meeting']==origin['meeting']
reference=[x for row in lexical_references(case) for x in units(row['text'],'Chinese')];raw=measure(reference,units(source_document['text'],'Chinese'));assert raw['errors']==461 and raw['referenceUnits']==8325
atomic_json(C/'original-native-raw-control.json',{'state':'REPRODUCED_RETAINED_NATIVE_GPU_ASR_RAW_SCORE_ZERO_NEW_RECOGNITION','meetings':[{'meeting':case['meeting'],'rawText':raw,'nativeBaselineRawText':raw}],'newAsrNeuralCalls':0,'sourceAsrInferenceBackend':binding['sourceAsrInferenceBackend']})
manifest=read(B/'qwen-cpu-chinese-characterization-r2/whole-scoring-only.json');manifest['cases']=[case];atomic_json(C/'whole-scoring-only.json',manifest)
speaker=read(B/'all-cpu-full4-composition-r1/predicted-speaker-bindings.json')['sources'][origin['meeting']]
for name in ['compose_cpu_qwen_alignment_20261116.py','score_cpu_qwen_alignment_20261116.py']:py_compile.compile(str(S/name),doraise=True)
composition={'composerSha256':sha(S/'compose_cpu_qwen_alignment_20261116.py'),'sourceAsrInferenceBackend':binding['sourceAsrInferenceBackend'],'speakerSources':{origin['meeting']:speaker},
 'files':{str(p):sha(p) for p in [S/'practical_transcript_20261107.py',C/'frozen-audio-recognized-text-only.json']},'inheritedMarginSeconds':.06,'qualityQualified':False}
atomic_json(C/'composition-binding.json',composition)
scoring={'scorerSha256':sha(S/'score_cpu_qwen_alignment_20261116.py'),'files':{str(p):sha(p) for p in [S/'score_joint_whole_meetings_20261115.py',C/'whole-scoring-only.json',C/'composition-binding.json']},
 'rawAsrWholeScore':str(C/'original-native-raw-control.json'),'rawAsrWholeScoreSha256':sha(C/'original-native-raw-control.json')}
for file,digest in manifest['helpers'].items():assert sha(file)==digest;scoring['files'][file]=digest
atomic_json(C/'scoring-binding.json',scoring)
atomic_json(C/'preparation.json',{'state':'PREPARED_ONE_RETAINED_NATIVE_ASR_FULL_MEETING_CPU_CLASSIFIER_PILOT_THEN_FULL_NOT_NEW_ASR','at':datetime.now().astimezone().isoformat(),'leaves':len(cases),'frames':cursor,
 'originalRawTextErrors':raw,'sourceAsrBackendIsPreviousGpu':True,'wholePipelineCpuRerun':False,'failedQ8WholeExpansion':False,'noTrainingOrQualityImprovementClaim':True,'newNeuralCalls':0,'limits':limits.query()})
print(json.dumps({'leaves':len(cases),'firstLeafSeconds':cases[0]['frames']/16000,'originalRawErrors':raw['errors'],'sourceAsrBackend':'retained GPU, not a new CPU decode'}))
