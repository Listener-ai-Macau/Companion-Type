"""Verify real source samples, complete target labels and disjoint training pairs."""
from pathlib import Path
import hashlib,json,os,sys,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools');import soundfile as sf
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-joint-neural-spatial';read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
rows=read(C/'training-pair-manifest.json');state=read(C/'training-pair-preparation.json');sources=read(R/'docs/handoffs/20261108-target-activity-adaptation/selected-training-sources.json');checked=0;profiles=set()
assert not (C/'training-pair-verification.json').exists()
for source in sources:
    proof=next(x for x in state['sources'] if x['meeting']==source['meeting']);assert proof['wholeSha256']==source['expectedWholeFileLfsSha256'];assert Path(proof['file']).stat().st_size==source['fileSize'];assert sha(source['reference'])==source['referenceSha256'];truth=[x for x in read_reference_intervals(source['reference']) if normalize(x['text'])]
    with sf.SoundFile(proof['file']) as original:
        for row in [x for x in rows if x['meeting']==source['meeting']]:
            assert sha(row['audio'])==row['audioSha256'];lo,hi=row['sourceStartSample'],row['sourceEndSample'];original.seek(lo);expected=original.read(hi-lo,dtype='int16',always_2d=True)[:,:2]
            with wave.open(row['audio'],'rb') as f:assert (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes())==(2,2,16000,hi-lo);assert f.readframes(hi-lo)==expected.astype('<i2',copy=False).tobytes()
            target=[x for x in truth if x['speaker']==row['targetPersonForSupervisedTrainingOnly'] and x['end']>lo/16000 and x['start']<hi/16000];assert all(x['start']>=lo/16000-1e-6 and x['end']<=hi/16000+1e-6 for x in target);text=''.join(x['text'] for x in sorted(target,key=lambda x:(x['start'],x['end'])));assert text==row['referenceTranscriptForTrainingOnly'];assert bool(target)==(row['category']!='absent_other_speech')
            assert hi<=row['profileSourceStartSample'] or lo>=row['profileSourceEndSample'];assert sha(row['profileAudio'])==row['profileAudioSha256']
            if row['profileAudioSha256'] not in profiles:
                a,b=row['profileSourceStartSample'],row['profileSourceEndSample'];original.seek(a);expected=original.read(b-a,dtype='int16',always_2d=True)[:,0]
                with wave.open(row['profileAudio'],'rb') as f:assert f.getnchannels()==1 and f.getnframes()==b-a;assert f.readframes(b-a)==expected.astype('<i2',copy=False).tobytes()
                profiles.add(row['profileAudioSha256'])
            checked+=1
assert checked==len(rows) and {r['meeting'] for r in rows if r['role']=='train'}.isdisjoint({r['meeting'] for r in rows if r['role']=='validation'})
atomic_json(C/'training-pair-verification.json',{'state':'PASS_ALL_SOURCE_PCM_COMPLETE_TARGET_TEXT_AND_DISJOINT_PROFILE_CHECKS','pairsChecked':checked,'uniqueProfilesCheckedAgainstWholeSourcePcm':len(profiles),'allTwoChannelSamplesBitIdenticalToVerifiedWholeFlacSource':True,'allTargetTextEntirelyInsideAudio':True,'allQueryAndOwnProfileDisjoint':True,'trainingAndValidationSourceMeetingsDisjoint':True,'cleanWaveformTargetsForRealOverlapAvailable':False,'physicalSpeakerIndependenceEstablished':False,'newModelCalls':0,'qualityQualified':False,'limits':limits.query()});print('PASS_ALL_214_REAL_TRAIN_PAIRS_SOURCE_AND_LABEL_INTEGRITY',flush=True)
