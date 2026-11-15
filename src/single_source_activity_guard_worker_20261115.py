"""Restore and observe the author's frozen activity head; no labels in forward."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,time,traceback
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_local_pcm_session_20261114 import atomic_json
from public_nemotron_adaptation_20261115 import read,sha,pin_rocm_blas,load_original,collect

def main():
    p=argparse.ArgumentParser()
    for key in ['control','run','inventory']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--phase',choices=['baseline'],required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    P=read(a.control/'protocol.json');binding=read(a.control/'worker-binding.json')
    assert sha(__file__)==binding['workerSha256'] and sha(a.control/'protocol.json')==binding['protocolSha256']
    for path,digest in binding['helpers'].items():assert sha(path)==digest
    state=dict(state='STARTING_ORIGINAL_ACTIVITY_HEAD_OBSERVATION',startedAt=datetime.now().astimezone().isoformat(),
        neuralChunkCalls=0,optimizerUpdates=0,referenceRead=False,protocolSha256=binding['protocolSha256'],qualityQualified=False)
    began=time.perf_counter()
    def save(**values):
        state.update(values,limits=limits.query(),observedAt=datetime.now().astimezone().isoformat());atomic_json(a.run/'state.json',state)
    def stop():
        if (a.run/'stop.request').exists():raise InterruptedError('Owned resource stop; retain all completed original outputs')
    def progress(first,last):
        state['neuralChunkCalls']+=1;save(lastCompletedFrame=last)
    save()
    try:
        inv=read(a.inventory)
        assert inv['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
        assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inv['finishedAt'])).total_seconds()<1800
        import torch,numpy as np
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        assert torch.__version__=='2.11.0+rocm10.0.0' and torch.cuda.device_count()==1
        torch.cuda.set_device(0);gpu=torch.cuda.get_device_properties(0)
        assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        blas=pin_rocm_blas(P['rocmBlasLibrary'],P['rocmBlasLibrarySha256'])
        model,activity,weights=load_original(P)
        assert not any(p.requires_grad for p in list(model.parameters())+list(activity.parameters()))
        save(state='ORIGINAL_FROZEN_SPEAKER_AND_ACTIVITY_HEAD_LOADED',weights=weights,blas=blas,gpu=gpu.name)
        assert sha(a.control/'audio-only.json')==P['audioOnlySha256']
        cases=read(a.control/'audio-only.json');results=[]
        for case in cases:
            stop();assert 'labels' not in case and 'reference' not in case
            folder=a.run/'results'/case['meeting'];folder.mkdir(parents=True,exist_ok=False)
            logits,aux=collect(model,activity,case,stop=stop,progress=progress,route_directory=folder/'original-cache-routes')
            probabilities=torch.from_numpy(logits).sigmoid().numpy()
            expected=read(a.control/'baseline-bindings.json')[case['meeting']]
            assert sha(expected['file'])==expected['sha256']
            original=np.load(expected['file'],allow_pickle=False)
            assert np.array_equal(probabilities,original),'Original whole-meeting speaker predictions changed'
            assert aux.shape==(len(probabilities),3) and np.isfinite(aux).all()
            classes=aux.argmax(axis=1).astype(np.uint8)
            active=[]
            # Preserve exact .5 equality handling of original probability_segments.
            for channel in range(8):
                values=probabilities[:,channel]
                last=np.maximum.accumulate(np.where(values!=.5,np.arange(len(values)),-1))
                active.append((last>=0)&(values[np.maximum(last,0)]>.5))
            legacy=np.stack(active,axis=1).sum(axis=1)>=2
            guarded=legacy&(classes==2)
            outputs={}
            for name,value in [('activity-logits',aux),('activity-class',classes),('legacy-overlap',legacy),('guarded-overlap',guarded)]:
                file=folder/(name+'.npy')
                with file.open('wb') as f:np.save(f,value,allow_pickle=False);f.flush();os.fsync(f.fileno())
                outputs[name]=dict(file=str(file),sha256=sha(file),shape=list(value.shape))
            # Public cache routes are saved for later speaker association, not
            # fabricated from posterior arrays or borrowed from adapted weights.
            for file in (folder/'original-cache-routes').glob('*.npy'):
                with file.open('r+b') as f:f.flush();os.fsync(f.fileno())
            result=dict(meeting=case['meeting'],audioSha256=case['audioSha256'],featuresSha256=case['featuresSha256'],
                originalSpeakerProbabilitiesBitExact=True,originalProbabilitySha256=expected['sha256'],
                frames=len(probabilities),outputs=outputs,legacyOverlapFrames=int(legacy.sum()),
                guardedOverlapFrames=int(guarded.sum()),activityClassFrames=np.bincount(classes,minlength=3).tolist(),
                originalCacheRoutes=str(folder/'original-cache-routes/routes.json'),
                referenceRead=False,newWeights=False,speakerAssociationImplemented=False)
            atomic_json(folder/'result.json',result);results.append(result)
            save(state='OBSERVING_ORIGINAL_ACTIVITY_HEAD_COMPLETE_MEETING',results=results,completedMeetings=len(results))
            del logits,aux,probabilities,original,classes,active,legacy,guarded
        save(state='COMPLETE_ORIGINAL_ACTIVITY_HEAD_OBSERVATION_SCORING_PENDING',results=results,
             allOriginalSpeakerPredictionsBitExact=True,optimizerUpdates=0,newWeights=False)
    except BaseException as error:
        save(state='FAILED_ACTIVITY_HEAD_OBSERVATION_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        save(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began)
        print(json.dumps({k:state.get(k) for k in ['state','neuralChunkCalls','optimizerUpdates','error','seconds']},ensure_ascii=False))

if __name__=='__main__':main()
