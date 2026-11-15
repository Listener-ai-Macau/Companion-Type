"""One fixed reference-free fusion control: neural predicted count + cached voice vectors.

No oracle counts, thresholds searched, new audio inference, or per-meeting choice.
Both complete exposed recordings are evaluated, including any regression.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');base=R/'docs/handoffs/20261107-model-generation-recovery';B=base/'bounded-speaker-full-r1';N=base/'native8-vulkan-full-r1';C=base/'native8-count-control-r1';C.mkdir(exist_ok=False)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();assert not pressure.low()
import numpy as np
from scipy.cluster.hierarchy import linkage,cut_tree
from bounded_speaker_20261107 import powerset_labels,speaker_intervals,prefix_sha,bounded_votes,vote_segments
assert read(N/'native-run.json')['state']=='COMPLETE_NATIVE8_BATCH_REVIEW_REQUIRED'
cases=read(B/'audio-only.json');P=read(B/'protocol.json');state={'state':'RUNNING_FIXED_PREDICTED_COUNT_FUSION','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'neuralItemsAdded':0,'referencePassedToReconstruction':False,'participantCountFromHumanOrReference':False,'results':[],'qualified':False};atomic_json(C/'predicted-count-run.json',state)
atomic_json(C/'audio-only.json',cases);atomic_json(C/'protocol.json',{'clustering':'Same complete-link distances, cluster count from exited independent8-channel neural output; no threshold cut or known reference count','minDurationOn':P['minDurationOn'],'minDurationOff':P['minDurationOff'],'sameRuleForEveryMeeting':True,'noTraining':True})
try:
    for case in cases:
        assert not pressure.low();tick=time.perf_counter();meeting=case['meeting'];native=N/'results'/meeting;producer=read(native/'completed-state.json');journal=read(native/'speaker-journal.json');assert producer['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' and producer['audioSha256']==case['audioSha256']==journal['audioSha256']
        count=len({r['speaker'] for r in journal['segments']});assert count==producer['predictedSpeakers'] and 1<=count<=8
        cache=Path(P['boundedCacheRoot'])/meeting;seg=read(cache/'segment.json');emb=read(cache/'embed.json');arrays=[]
        for name,manifest in [('segment',seg),('embed',emb)]:
            assert manifest['binding']['audioSha256']==case['audioSha256'];value=np.load(cache/(name+'.npy'),mmap_mode='r',allow_pickle=False);assert manifest['done']==value.shape[0] and prefix_sha(value,manifest['done'])==manifest['committedPrefixSha256'];arrays.append(value)
        labels=powerset_labels(arrays[0]);pairs,runs=speaker_intervals(labels,seg['meta']);valid=~np.isnan(arrays[1]).any(axis=1);pairs=[x for x,k in zip(pairs,valid) if k];values=np.asarray(arrays[1][valid],dtype=np.float32).copy();values/=np.sqrt(np.sum(values*values,axis=1,dtype=np.float32))[:,None]
        distance=np.empty(len(values)*(len(values)-1)//2,dtype=np.float64);offset=0
        for i in range(len(values)-1):
            block=np.einsum('ij,j->i',values[i+1:],values[i],dtype=np.float32);n=len(block);distance[offset:offset+n]=np.maximum(0.,1.-block.astype(np.float64));offset+=n
        clusters=cut_tree(linkage(distance,method='complete'),n_clusters=[count]).reshape(-1);order={value:i for i,value in enumerate(dict.fromkeys(clusters.tolist()))};clusters=np.asarray([order[v] for v in clusters],np.int32)
        counts,expected,memory=bounded_votes(labels,pairs,clusters,seg['meta'],round(case['audioSeconds']*16000));rows=vote_segments(counts,expected,seg['meta'],P['minDurationOn'],P['minDurationOff']);out=C/'results'/meeting;out.mkdir(parents=True)
        atomic_json(out/'speaker-journal.json',{'meeting':meeting,'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'segments':rows,'scope':'Fixed development fusion control only; predicted count from a real model, not reference.0new neural items, no threshold search or accepted improvement.'})
        rttm=out/'predicted.rttm';rttm.write_text(''.join(f"SPEAKER {meeting} 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> speaker_{r['speaker']} <NA> <NA>\n" for r in rows),encoding='utf8')
        result={'meeting':meeting,'audioSha256':case['audioSha256'],'predictedCountSource':str(native/'speaker-journal.json'),'predictedCountSourceSha256':sha(native/'speaker-journal.json'),'neuralPredictedCount':count,'activeReconstructedGroups':len({r['speaker'] for r in rows}),'newNeuralItems':0,'reconstructionSeconds':time.perf_counter()-tick,'memoryLayout':memory,'rttmSha256':sha(rttm),'referenceUsedForClustering':False};atomic_json(out/'completed-reconstruction.json',result)
        # Only now open the existing scoring case; references never reach any
        # count/distance/clustering/segmentation operation above.
        scoring=next(x for x in read(B/'scoring-only.json') if x['meeting']==meeting);atomic_json(out/'scoring-case.json',scoring)
        with (out/'scoring.log').open('xb') as log:code=subprocess.run([str(Path(os.sys.executable)),str(Path(__file__).with_name('score_cross_corpus_diarization_20261103.py')),'--case',str(out/'scoring-case.json'),'--rttm',str(rttm),'--out',str(out/'review.json')],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS).returncode
        assert code==0;result['qualityReview']=read(out/'review.json');state['results'].append(result);atomic_json(C/'predicted-count-run.json',state)
    state['state']='COMPLETE_FIXED_COUNT_FUSION_REVIEW_REQUIRED_NO_QUALIFICATION'
finally:
    pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');state['limits']=limits.query();atomic_json(C/'predicted-count-run.json',state);print(json.dumps({'state':state['state'],'results':[{'meeting':r['meeting'],'predictedCount':r['neuralPredictedCount'],'der':r['qualityReview']['components']['diarization error rate']} for r in state['results']]},ensure_ascii=False),flush=True)
