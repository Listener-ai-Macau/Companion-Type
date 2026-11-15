"""Freeze one diagnostic validation cohort before any model output is seen."""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,os,sys,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from reference_textgrid_20261104 import read_reference_intervals
import soundfile as sf

R=S.parent.parent
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'context-matched-baseline-r1';C.mkdir()
audio_root=Path('E:/CodexData/Companion/product-d1d2-20261114/context-matched-baseline-r1/audio');audio_root.mkdir(parents=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
coverage=D/'asr-training-coverage-audit-r1/coverage.json'
report=read(coverage);sources=read(R/'docs/handoffs/20261108-tse-source-supervision/sources.json')
audio_only=[];scoring=[]
for source in [s for s in sources if s['role']=='validation']:
 assert sha(source['reference'])==source['referenceSha256']
 assert sha(source['localFlac'])==source['expectedWholeFileLfsSha256']
 info=sf.info(source['localFlac']);assert info.samplerate==16000 and info.channels==8 and info.subtype=='PCM_16'
 audit=next(s for s in report['sources'] if s['meeting']==source['meeting'])
 eligible=[c for c in audit['eligibleContextPlans'] if c['seconds']<=29.84]
 assert len(eligible)>=6
 # Fixed uniform positions. No transcript/model error, confidence or speaker
 # performance is consulted for choosing these twelve diagnostic windows.
 indices=[(i*(len(eligible)-1))//5 for i in range(6)]
 assert len(set(indices))==6
 rows=sorted([r for r in read_reference_intervals(source['reference']) if r['text'].strip()],key=lambda r:(r['start'],r['end'],r['speaker']))
 previous_export_end=-1
 with sf.SoundFile(source['localFlac']) as source_audio:
  for sequence,index in enumerate(indices):
   plan=eligible[index];start,end=plan['start'],plan['end']
   contained=[r for r in rows if r['start']>=start-1e-9 and r['end']<=end+1e-9]
   crossing=[r for r in rows if r['start']<end-1e-9 and r['end']>start+1e-9 and r not in contained]
   assert not crossing and len(contained)==plan['utterances']
   assert all('<' not in r['text'] and '>' not in r['text'] for r in contained)
   prior=max((r['end'] for r in rows if r['end']<=start+1e-9),default=0.)
   following=min((r['start'] for r in rows if r['start']>=end-1e-9),default=info.frames/16000)
   low=max(0,math.ceil(start*16000)-1280,math.ceil(prior*16000))
   high=min(info.frames,math.ceil(end*16000)+1280,math.ceil(following*16000))
   assert 0<=low<high<=info.frames and high-low<=30*16000 and low>=previous_export_end
   assert not [r for r in rows if r not in contained and r['start']<high/16000-1e-9 and r['end']>low/16000+1e-9]
   previous_export_end=high
   source_audio.seek(low);pcm=source_audio.read(high-low,dtype='int16',always_2d=True)[:,0].astype('<i2',copy=False).tobytes()
   assert len(pcm)==(high-low)*2
   case_id=source['meeting']+'-context-'+str(sequence+1).zfill(2)
   target=audio_root/(case_id+'.wav');assert not target.exists()
   with wave.open(str(target),'wb') as out:
    out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
   with wave.open(str(target),'rb') as check:
    assert check.getnframes()==high-low and check.readframes(high-low)==pcm
   item={'id':case_id,'meeting':source['meeting'],'wav':str(target),'wavSha256':sha(target),
         'pcmSha256':hashlib.sha256(pcm).hexdigest(),'frames':high-low,'audioSeconds':(high-low)/16000,'language':'Chinese'}
   audio_only.append(item)
   scoring.append({**item,'sourceStartFrame':low,'sourceEndFrame':high,'sourceWholeSha256':source['expectedWholeFileLfsSha256'],
    'reference':source['reference'],'referenceSha256':source['referenceSha256'],'eligiblePlanIndex':index,
    'eligiblePlansAfter30sCap':len(eligible),'utterances':contained,'rawReferenceText':''.join(r['text'] for r in contained),
    'speakers':plan['speakers'],'shortUtterances':plan['shortUtterances'],
    'overlapPresent':any(a['start']<b['end']-1e-9 and b['start']<a['end']-1e-9 for i,a in enumerate(contained) for b in contained[i+1:])})
assert len(audio_only)==12
write(C/'audio-only.json',audio_only);write(C/'scoring-only.json',scoring)
native=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-runtime-r2/source/native-protocol.json')
protocol={'state':'FROZEN_CONTEXT_MATCHED_BASE_MODEL_DIAGNOSTIC_BEFORE_OUTPUTS','at':datetime.now().astimezone().isoformat(),
 'purpose':'Measure the existing base on natural multi-turn windows containing short responses, before considering any further training.',
 'coverageAudit':str(coverage),'coverageAuditSha256':sha(coverage),'cases':12,
 'audioOnlyManifestSha256':sha(C/'audio-only.json'),'scoringOnlyManifestSha256':sha(C/'scoring-only.json'),
 'nativeProtocol':str(native),'nativeProtocolSha256':sha(native),
 'selection':'Six uniformly spaced eligible context plans per validation source; index=floor(i*(N-1)/5). Complete overlap components, 10–29.84s before up to80ms natural padding per side, no tags. No model output consulted.',
 'audio':'Original AISHELL4 training-split first microphone, PCM16 mono16k. No denoising, separation, gain, resampling or synthetic concatenation.',
 'inference':'Unmodified resident NativeDecoder, Chinese, BF16 eager greedy512, original recovery and raw journals. No new weights or parameter updates.',
 'decision':'Describe base errors before any adaptation proposal. Do not qualify the product, lower original gates, select more windows based on errors, or automatically launch training.',
 'limitations':['This validation cohort is annotation-assisted and truncated to complete utterances, unlike a whole product recording.',
  'All voices remain in overlapping windows; chronological merged-character scoring has no unique overlap order. Report overlap status explicitly.',
  'These are original training-split meetings held out from the previous adaptation. Physical speaker/room independence is not established; prior TSE diagnostics used some sources.',
  'Original whole-meeting development cases and final L_R003S03C02 are excluded. Original long and bilingual controls are still required for any future candidate.'],
 'license':'AISHELL4 CC-BY-SA-4.0, https://www.openslr.org/111/; source URL and original hashes retained in source manifest.',
 'automaticRetries':0,'newTraining':False,'qualityQualified':False,'fullMeetingGatesChanged':False,'finalHoldoutOpened':False,
 'totalSeconds':sum(r['audioSeconds'] for r in audio_only),'limits':limits.query()}
write(C/'protocol.json',protocol)
helpers=['companion_local_qwen_worker_20261114.py','companion_local_pcm_session_20261114.py',
 'companion_local_decode_recovery_20261114.py','practical_qwen_bounded_decode_20261107.py','practical_qwen_streamed_loader_20261107.py']
write(C/'worker-binding.json',{'workerSha256':sha(S/'context_baseline_worker_20261115.py'),'protocolSha256':sha(C/'protocol.json'),
 'helpers':{str(S/name):sha(S/name) for name in helpers},'runnerSha256':sha(S/'run_context_baseline_20261115.py')})
print(json.dumps({'control':str(C),'cases':12,'seconds':protocol['totalSeconds'],
 'shortUtterances':sum(r['shortUtterances'] for r in scoring),'overlapCases':sum(r['overlapPresent'] for r in scoring)},ensure_ascii=False))
