"""One author-style binary timestamp-mask control, no threshold/reference tuning."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-sedicow-r1';M=R/'model-research';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from companion_sedicow_conditioning_20261109 import stno_from_activity
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);assert not SystemRamPressure().low()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
J=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results/L_R003S01C02/speaker-journal.json';journal=read(J);out=Path('E:/CodexData/Companion/.model-cache/sedicow-20261109/author-mask-inputs');out.mkdir(exist_ok=False);jobs=[]
def mask_for_window(begin):
 activity=np.zeros((1500,8),dtype=np.float32)
 for row in journal['segments']:
  if row['end']<=begin or row['start']>=begin+30:continue
  a=max(0,round((row['start']-begin)*50));b=min(1500,round((row['end']-begin)*50));assert 0<=int(row['speaker'])<8
  if b>a:activity[a:b,int(row['speaker'])]=1
 return activity
for job in read(C/'audio-only-inputs.json'):
 with np.load(job['modelInputs'],allow_pickle=False) as data:arrays={key:data[key].copy() for key in data.files}
 native=job['nativePerson'];main=stno_from_activity(mask_for_window(job['sourceStartSample']/16000),native);enroll=stno_from_activity(mask_for_window(job['enrollmentStartSample']/16000),native)
 arrays['stno_mask']=main[None];arrays['enrollment_stno_mask']=enroll[None];assert set(np.unique(main))<={0.,1.} and np.all(main.sum(axis=0)==1)
 file=out/(job['id']+'-inputs.npz');np.savez_compressed(file,**arrays)
 # Only masks differ; preserve all six feature/attention/audio hashes.
 with np.load(job['modelInputs'],allow_pickle=False) as original:
  assert all(np.array_equal(arrays[key],original[key]) for key in ['input_features','attention_mask','enrollment_input_features','enrollment_attention_mask'])
 jobs.append(dict(job,modelInputs=str(file),modelInputsSha256=sha(file),conditioningKind='author-style-binary-from-existing-automatic-journal',sourceSpeakerJournalSha256=sha(J)))
(C/'author-mask-audio-only.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
protocol={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'FROZEN_SINGLE_AUTHOR_FORMAT_ABLATION_NOT_TRAINING','reason':'Native2softconditioning producedEnglish despiteforcedzh; testwhether deviationfromauthorbinarytimestampmask causesfailure beforeattributingittoChinesecheckpoint. Oneauthor-stylebinarycontrol onexactly sameaudio/enrollment/features, target2, no threshold/model/beam/hint sweep.','sourceSpeakerJournal':str(J),'sourceSpeakerJournalSha256':sha(J),'referenceLabelsOrWordsUsed':False,'modelWeightsOrAudioChanged':False,'authorClock':'50Hz localwindow mask, round(start*50):round(end*50), STNO products. Main1560s andnative2enrollment111.2s alignfull50Hzgrid. Preserveoldautomaticjournal all8heads, no oraclepersoncount.','changed':'Onlymain/enrollmentSTNO binary masks, allfeature/audioarraysunchanged. References/enrollmentselectionnotchanged.','selectedTarget':'native-2','inputManifestSha256':sha(C/'author-mask-audio-only.json'),'saleQualified':False};(C/'author-mask-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(protocol,ensure_ascii=False))
