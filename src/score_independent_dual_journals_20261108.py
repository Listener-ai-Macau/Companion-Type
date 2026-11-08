"""Post-selection full DER, short turns and per-mic disagreement; never fuse labels."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess,sys,urllib.request
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.optimize import linear_sum_assignment
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-dual-mic-independent-meetings';E=Path('E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108');REV='aada72727856313b19d4a030383c426364931dbf'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
assert (C/'protocol-r2.json').exists() and read(C/'clip-selection-before-reference.json')['referencePayloadRead'] is False
assert not (C/'journal-review.json').exists()
root='https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/'+REV+'/test/TextGrid/'
specs={'M_R003S02C01':(127248,'c6ef498621724be73b9301efc3f380c4da7649a6'),'S_R003S01C01':(198779,'2be87dead5e0095dfcb9cfd988a1e99a76bf12d0')}
run=read(C/'native-run.json');assert run['state']=='COMPLETE_FOUR_FULL_CHANNEL_JOURNALS_UNQUALIFIED';inputs=read(C/'audio-only.json');cases=[];reviews=[]
for audio in inputs:
    meeting=audio['originalMeeting'];size,blob=specs[meeting];path=E/(meeting+'.TextGrid')
    if not path.exists():
        with urllib.request.urlopen(root+meeting+'.TextGrid',timeout=30) as response:data=response.read(size+1)
        assert len(data)==size and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
        path.write_bytes(data)
    else:
        data=path.read_bytes();assert len(data)==size and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
    result=next(r for r in run['results'] if r['meeting']==audio['meeting']);out=Path(result['out']);case={**audio,'reference':str(path),'referenceSha256':sha(path),'referenceKind':'textgrid','fixedMappingReview':str(out/'review.json')};cases.append(case);atomic_json(out/'scoring-case.json',case)
    assert not (out/'review.json').exists()
    with (out/'scoring.log').open('xb') as log:
        code=subprocess.run([sys.executable,str(Path(__file__).with_name('score_cross_corpus_diarization_20261103.py')),'--case',str(out/'scoring-case.json'),'--rttm',str(out/'predicted.rttm'),'--out',str(out/'review.json')],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS).returncode
    assert code==0,(out/'scoring.log').read_text(encoding='utf8',errors='replace')[-3000:]
    reviews.append({'meeting':audio['meeting'],'review':read(out/'review.json'),'resultDirectory':str(out)});print(json.dumps({'meeting':audio['meeting'],'components':reviews[-1]['review']['components']}),flush=True)
atomic_json(C/'scoring-only.json',cases)
agreement=[];coverage=[]
for meeting in specs:
    pair=[r for r in inputs if r['originalMeeting']==meeting];duration=pair[0]['audioSeconds'];frames=int(np.ceil(duration*100));arrays=[]
    for audio in pair:
        out=Path(next(r for r in run['results'] if r['meeting']==audio['meeting'])['out']);mask=np.zeros((8,frames),dtype=bool)
        for row in read(out/'speaker-journal.json')['segments']:mask[row['speaker'],round(row['start']*100):min(frames,round(row['end']*100))]=True
        arrays.append(mask)
    # IDs aligned solely by predicted activity overlap, with zero-evidence
    # pairings explicitly untrusted. No union/vote or GT selection is emitted.
    a,b=arrays;hits=a.astype(np.int32)@b.astype(np.int32).T;left,right=linear_sum_assignment(-hits);mapping=[{'mic0Slot':int(i),'mic1Slot':int(j),'commonPredictedSeconds':float(hits[i,j]/100),'mappingSupported':bool(hits[i,j]>0)} for i,j in zip(left,right)]
    disagreement=[]
    for row in mapping:
        i,j=row['mic0Slot'],row['mic1Slot'];disagreement.append({**row,'mic0OnlySeconds':float(np.count_nonzero(a[i]&~b[j])/100),'mic1OnlySeconds':float(np.count_nonzero(b[j]&~a[i])/100)})
    agreement.append({'meeting':meeting,'mappingSource':'Whole-meeting prediction activity only; Hungarian maximum intersection. Not reference labels or a fused product journal.','perPredictedPair':disagreement,'differentActiveCountSeconds':float(np.count_nonzero(a.sum(0)!=b.sum(0))/100),'twoWayFusionPerformed':False})
    truth=[r for r in read_reference_intervals(E/(meeting+'.TextGrid')) if normalize(r['text'])]
    for case in read(C/'spatial-audio-only.json'):
        if case['meeting']!=meeting:continue
        lo,hi=case['rootStartSample']/16000,case['rootEndSample']/16000;events=[lo,hi]
        selected=[r for r in truth if r['end']>lo and r['start']<hi]
        for r in selected:events += [max(lo,r['start']),min(hi,r['end'])]
        times=sorted(set(events));single=overlap=triple=silence=0.
        for x,y in zip(times,times[1:]):
            mid=(x+y)/2;count=len({r['speaker'] for r in selected if r['start']<=mid<r['end']})
            if count==0:silence+=y-x
            if count==1:single+=y-x
            if count>=2:overlap+=y-x
            if count>=3:triple+=y-x
        coverage.append({'id':case['id'],'selectedKind':case['kind'],'trueSingleSeconds':single,'trueOverlapSeconds':overlap,'trueTripleOrMoreSeconds':triple,'trueSilenceSeconds':silence,'selectionChangedAfterSeeingTruth':False})
atomic_json(C/'journal-review.json',{'at':datetime.now().astimezone().isoformat(),'state':'COMPLETE_FOUR_FULL_JOURNALS_STANDARD_DER_AND_DISAGREEMENT_AUDIT','fullMeetingReviews':reviews,'crossMicAgreement':agreement,'selectedClipActualReferenceCoverage':coverage,'referenceOpenedAfterSelectionAndProtocolFrozen':True,'predictionMicrophoneFixedTo0NotBestReferenceScore':True,'privateLimitBytes':512*1024**2,'limits':limits.query(),'qualityQualified':False,'finalHoldoutOpened':False})
