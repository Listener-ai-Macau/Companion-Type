"""One frozen full-core meeting-style blind separation adaptation."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,sys,time,traceback
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_community1_adapter_20261115 import sha,pin_rocm_blas
from companion_local_pcm_session_20261114 import atomic_json
from blind_separator_supervision_20261115 import (restore_common_units,pit_source_aggregated_sdr,
    loss_controls,load_trainable_core,checkpoint,apply_full_checkpoint,restore_optimizer)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    p=argparse.ArgumentParser()
    for name in ['control','inventory','run']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--phase',choices=['control','baseline','train','candidate'],required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    protocol=read(a.control/'protocol.json');binding=read(a.control/'worker-binding.json')
    assert sha(__file__)==binding['workerSha256'] and sha(a.control/'protocol.json')==binding['protocolSha256']
    for path,digest in binding['helpers'].items():assert sha(path)==digest
    for item in protocol['sourceAndRuntimeFiles']:assert sha(item['file'])==item['sha256']
    assert sha(protocol['checkpoint'])==protocol['checkpointSha256']
    sys.path[:0]=[protocol['isolatedDependencies'],protocol['sourceRoot']]
    state=dict(state='STARTING_FIXED_BLIND_SEPARATOR_SUPERVISED_PHASE',phase=a.phase,
               startedAt=datetime.now().astimezone().isoformat(),explicitNeuralCalls=0,
               trainingExamples=0,optimizerUpdates=0,validationReferenceRead=False,
               qualityQualified=False,protocolSha256=binding['protocolSha256'])
    began=time.perf_counter()
    def save(**values):
        state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
        atomic_json(a.run/'state.json',state)
    def check():
        if (a.run/'stop.request').exists():raise InterruptedError('Owned training resource stop; all completed checkpoints retained')
    save()
    try:
        inv=read(a.inventory);assert inv['selected']['name']=='AMD Radeon RX 6800 XT'
        assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inv['finishedAt'])).total_seconds()<1800
        import torch,numpy as np
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        assert torch.version.hip and torch.cuda.device_count()==1
        torch.cuda.set_device(0);gpu=torch.cuda.get_device_properties(0)
        assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
        blas=pin_rocm_blas(protocol['rocmBlasLibrary'],protocol['rocmBlasLibrarySha256'])
        torch.manual_seed(20261115);np.random.seed(20261115)
        model,weights=load_trainable_core(protocol,torch)
        trainable=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
        parameters=[p for _,p in trainable]
        save(state='FIXED_PRETRAINED_CORE_LOADED',gpu=gpu.name,blas=blas,weights=weights,
             originalFactoryTrainableNames=[n for n,_ in trainable])
        def data(row,targets=False):
            check();assert sha(row['file'])==row['sha256'];value=np.load(row['file'],allow_pickle=False)
            assert value.dtype==np.float32 and np.isfinite(value).all()
            if targets:
                assert value.shape==(3,32000) and np.array_equal(value[0],value[1:].sum(0))
                return torch.from_numpy(value[0]).to('cuda:0'),torch.from_numpy(value[1:]).to('cuda:0')
            assert value.shape==(32000,);return torch.from_numpy(value).to('cuda:0')
        def forward(x):
            check();out=model(x.reshape(1,-1));state['explicitNeuralCalls']+=1
            value=torch.stack([v[0] for v in out]);assert value.shape==(2,len(x)) and torch.isfinite(value).all()
            return restore_common_units(torch,value,x)
        if a.phase=='control':
            controls=loss_controls(torch)
            assert sha(a.control/'train-examples.json')==protocol['trainExamplesSha256']
            selected=None
            for row in read(a.control/'train-examples.json'):
                value=np.load(row['file'],allow_pickle=False)
                if np.any(value[1]) and np.any(value[2]):selected=row;break
            assert selected is not None
            x,target=data(selected,targets=True);out=forward(x);loss,swap,ratio=pit_source_aggregated_sdr(torch,out,target)
            assert torch.isfinite(loss);loss.backward()
            assert all(p.grad is None or torch.isfinite(p.grad).all() for p in parameters)
            nonzero=sum(p.grad is not None and bool((p.grad!=0).any()) for p in parameters)
            assert nonzero>0 and all(p.grad is None for p in model.parameters() if not p.requires_grad)
            norm=torch.nn.utils.clip_grad_norm_(parameters,1.,error_if_nonfinite=True)
            save(state='PASS_BLIND_SEPARATOR_SOURCE_LOSS_AND_REAL_GRADIENT_BEFORE_UPDATES',
                 lossControls=controls,realTrainingExample=selected['id'],realTrainingLossDb=float(loss.detach()),
                 realErrorEnergyRatio=float(ratio.detach()),nonzeroGradientTensors=nonzero,
                 preClipGradientNorm=float(norm),noOptimizerUpdateForControl=True,
                 frozenFactoryParametersWithoutGradient=True,peakGpuAllocatedBytes=torch.cuda.max_memory_allocated())
        elif a.phase=='train':
            proof=read(Path(protocol['controlRun'])/'state.json')
            assert proof['state']=='PASS_BLIND_SEPARATOR_SOURCE_LOSS_AND_REAL_GRADIENT_BEFORE_UPDATES' and proof['protocolSha256']==binding['protocolSha256']
            assert sha(a.control/'train-examples.json')==protocol['trainExamplesSha256']
            assert proof['originalFactoryTrainableNames']==[n for n,_ in trainable]
            examples=read(a.control/'train-examples.json');order=protocol['order'];assert sorted(order)==list(range(len(examples)))
            optimizer=torch.optim.AdamW(parameters,lr=1e-5,betas=(.9,.999),weight_decay=0.,foreach=False)
            start=0;execution=a.control/'train-execution.json'
            if execution.exists() and read(execution).get('resumeCheckpoint'):
                saved=read(read(execution)['resumeCheckpoint']);start=restore_optimizer(model,optimizer,saved,torch,binding['protocolSha256'])
                state['optimizerUpdates']=saved['optimizerUpdates'];state['trainingExamples']=start
            records=[];optimizer.zero_grad(set_to_none=True)
            for step in range(start,len(order)):
                x,target=data(examples[order[step]],targets=True);out=forward(x)
                loss,swap,ratio=pit_source_aggregated_sdr(torch,out,target);assert torch.isfinite(loss)
                group_size=min(4,len(order)-(step//4)*4);(loss/group_size).backward()
                value=float(loss.detach());energy=float(ratio.detach())
                if (step+1)%4==0 or step+1==len(order):
                    norm=torch.nn.utils.clip_grad_norm_(parameters,1.,error_if_nonfinite=True)
                    optimizer.step();optimizer.zero_grad(set_to_none=True);state['optimizerUpdates']+=1
                state['trainingExamples']=step+1
                with (a.run/'history.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps(dict(step=step+1,id=examples[order[step]]['id'],lossDb=value,errorRatio=energy,optimizerUpdates=state['optimizerUpdates']))+'\n')
                del x,target,out,loss
                if ((step+1)%4==0 and state['optimizerUpdates']%16==0) or step+1==len(order):
                    saved=checkpoint(model,optimizer,torch,a.run/'checkpoints'/('update-'+str(state['optimizerUpdates']).zfill(3)),
                        updates=state['optimizerUpdates'],examples=step+1,protocol_sha=binding['protocolSha256'],order=order)
                    records.append(saved);atomic_json(a.run/'latest-checkpoint.json',saved)
                save(state='TRAINING_ONE_FIXED_FULL_CORE_PASS',total=len(order),lastLossDb=value,checkpoints=records,
                     peakGpuAllocatedBytes=torch.cuda.max_memory_allocated())
            assert state['trainingExamples']==len(examples) and state['optimizerUpdates']==(len(examples)+3)//4
            saved=read(a.run/'latest-checkpoint.json');reload=apply_full_checkpoint(model,saved,torch)
            save(state='COMPLETE_ONE_FIXED_BLIND_SEPARATOR_TRAINING_PASS',finalCheckpoint=str(a.run/'latest-checkpoint.json'),
                 finalReloadProof=reload,finalOnlySelectedForValidation=True,newAsrWeightsTrained=False,
                 buffersAndNonlearnedFrequenciesNotOptimized=True)
        else:
            model.requires_grad_(False)
            if a.phase=='candidate':
                saved=read(Path(protocol['trainRun'])/'latest-checkpoint.json')
                assert saved['protocolSha256']==binding['protocolSha256']
                save(reloaded=apply_full_checkpoint(model,saved,torch))
            assert sha(a.control/'validation-audio-only.json')==protocol['validationAudioOnlySha256']
            rows=read(a.control/'validation-audio-only.json');results=[]
            resume=read(a.control/'resume-source.json')
            assert sha(resume['originalState'])==resume['originalStateSha256']
            cached={r['id']:r for r in resume['results']}
            assert len(cached)==resume['completedVerifiedPredictions'] and set(cached).issubset({r['id'] for r in rows})
            for item in cached.values():
                assert sha(item['file'])==item['sha256'] and item['referenceUsed'] is False
                array=np.load(item['file'],allow_pickle=False)
                assert array.shape==(2,32000) and array.dtype==np.float32 and np.isfinite(array).all()
            save(reusedVerifiedPredictions=len(cached),automaticRetries=0)

            for i,row in enumerate(rows):
                if row['id'] in cached:
                    results.append(cached[row['id']])
                    save(state='REUSING_EXACT_COMPLETED_SOURCE_PREDICTIONS',completed=i+1,total=len(rows),results=results)
                    continue
                x=data(row)
                with torch.no_grad():value=forward(x).cpu().numpy()
                file=a.run/(row['id']+'.npy')
                with file.open('wb') as durable:
                    np.save(durable,value,allow_pickle=False)
                    durable.flush();os.fsync(durable.fileno())
                results.append(dict(id=row['id'],file=str(file),sha256=sha(file),referenceUsed=False))
                save(state='PREDICTING_FROZEN_SYNTHETIC_AUDIO_ONLY',completed=i+1,total=len(rows),results=results)
            save(state='COMPLETE_FROZEN_SYNTHETIC_SOURCE_PREDICTIONS_SCORE_PENDING',results=results,
                 predictedSources=2,validationReferenceRead=False)
    except BaseException as error:
        save(state='FAILED_FIXED_BLIND_SEPARATOR_SUPERVISED_PHASE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began)
        atomic_json(a.run/'state.json',state)
        print(json.dumps({k:state.get(k) for k in ['state','phase','error','trainingExamples','optimizerUpdates','explicitNeuralCalls','seconds']},ensure_ascii=False))

if __name__=='__main__':main()
