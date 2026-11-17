"""One English meeting-domain full-weight adaptation; nativeGPU only.

baseline -> actual loss/gradient/maximum-shape/checkpoint preflight -> one
fresh fixed epoch -> final validation. No validation labels, search grid,
automatic retry, deployment, CPU/iGPU training, or changed audio selection.
"""
from pathlib import Path
from datetime import datetime
import argparse
import gc
import hashlib
import json
import os
import random
import sys
import time
import wave

os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from meeting_acoustic_contract_20261116 import read,require,sha
from meeting_acoustic_worker_20261116 import own_limits,available_ram,present_discrete_gpu,exclusive_run
from moss_windows_resource_limits_20261104 import SystemRamPressure
from companion_local_pcm_session_20261114 import exclusive_file
from companion_windows_power_request_20261115 import PowerLease
from durable_model_state_20261117 import atomic_json
from companion_gpu_execution_20261116 import GuardedGpu
from english_transducer_worker_20261116 import make_empty
from tdt_selected_loss_20261116 import gpu_loss_contract,blocked_joint_loss
from tdt_adaptation_checkpoint_20261116 import CheckpointStore,frozen_digest,digest_tensors
from tdt_adaptation_contract_20261117 import valid_resume_position,checkpoint_identity,require_final_checkpoint
from model_thermal_guard_20261117 import ThermalGuard,inspect_thermal_policy

now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')

def inspect(P):
    inspect_thermal_policy(P['thermal'])
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen adaptation dependency changed: '+item['file'])
    plan=read(P['dataPlan']);require(plan['examples']==475 and plan['trainableParameters']==118886022,
        'Fixed adaptation data/parameter scope changed')
    require(plan['englishGlobalParticipantsDisjointFromSeenValidationVerified'],'English participant split not verified')
    require(plan['targetAnnotationProjection']['canonicalLexicalWordEdits']==0,'Training lexical words changed')
    require(P['training']['epochs']==1 and P['training']['learningRate']==1e-5
        and P['training']['gradientAccumulationExamples']==4 and P['training']['seed']==20261116
        and P['training']['optimizer']=='AdamW' and P['training']['betas']==[.9,.999]
        and P['training']['weightDecay']==.01 and P['training']['epsilon']==1e-8
        and P['training']['gradientClipNorm']==1.,'No parameter/epoch grid')
    require(plan['publishedWeightsSha256']==P['weights']['sha256']
        and sha(plan['trainingManifest'])==plan['trainingManifestSha256'],'Frozen training data/base mismatch')
    return plan

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--phase',required=True);parser.add_argument('--run',type=Path);a=parser.parse_args()
    resume=a.phase.startswith('resume-') and a.phase[7:].isdigit()
    require(a.phase in ('inspect','baseline','preflight','train','validate') or resume,'Unknown adaptation phase')
    limits=own_limits(5 if a.phase=='inspect' else 25);P=read(a.protocol);plan=inspect(P)
    if a.phase=='inspect':
        require('torch' not in sys.modules,'Offline inspect imported torch')
        print(json.dumps({'state':'PASS_ENGLISH_DOMAIN_ADAPTATION_OFFLINE_CONTRACT','examples':475,
            'trainableParameters':118886022,'gpuPreflightPassed':False,'trainingStarted':False,'torchImported':False}));return
    require(P.get('gpuExecutionEnabled') is True,'GPU execution not enabled in this frozen preparation')
    require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Frozen execution window expired')
    require(a.run is not None,'Explicit isolated run required');run=a.run.resolve();run.mkdir(parents=True,exist_ok=True)
    out=run/a.phase;out.mkdir(exist_ok=False);(out/'results').mkdir()
    binding={'protocolSha256':sha(a.protocol),'workerSha256':sha(__file__),
        'publishedWeightsSha256':P['weights']['sha256'],'dataSha256':plan['trainingManifestSha256']}
    state={'state':'PREPARING_ENGLISH_ADAPTATION_'+a.phase.upper(),'at':now(),'pid':os.getpid(),
        'binding':binding,'phase':a.phase,'newNeuralCalls':0,'completed':[],'parameterUpdates':0,
        'candidateOptimizerUpdates':0,'completedTrainingExamples':0,'validationReferencesRead':False,
        'qualityQualified':False,'saleQualified':False,'currentOperationBudgetSeconds':180}
    pressure=SystemRamPressure();guard=None;thermal=ThermalGuard(P['thermal'])
    def save(**values):
        state.update(values,observedAt=now(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
    def stop():
        require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Original overnight cutoff')
        require(not pressure.low() and available_ram()>=P['minimumAvailableBytes'],'Original system RAM protection')
        require(not(run/'stop.request').exists(),'Owned stop requested; no automatic restart')
        state['cpuThermalObservation']=thermal.check()
    def train_rows():
        require(sha(plan['trainingManifest'])==plan['trainingManifestSha256'],'Training manifest changed')
        rows=[json.loads(s) for s in Path(plan['trainingManifest']).read_text(encoding='utf-8').splitlines() if s]
        require(len(rows)==475 and all(r['role']=='train-only' and r['language']=='English' for r in rows),
            'Nontraining rows entered adaptation')
        for row in rows:require(sha(row['audio'])==row['audioSha256'],'Training PCM changed')
        return rows
    def require_baseline():
        baseline=read(run/'baseline/completed.json')
        require(baseline['state']=='COMPLETE_TDT_BASELINE_12_PENDING_INDEPENDENT_SCORE'
            and baseline['binding']==binding and len(baseline['completed'])==12
            and baseline['parameterUpdates']==0,'Same-profile complete untrained baseline missing')
        return baseline
    with exclusive_run(run),exclusive_file(Path(P['neuralLock'])),PowerLease():
        try:
            save();state['presentDevices']=present_discrete_gpu();began=time.monotonic()
            while time.monotonic()-began<60:
                stop();state['cpuThermalObservation']=thermal.check(starting=True);save();time.sleep(1)
            import torch
            import numpy as np
            import transformers
            require(torch.__version__==P['runtime']['torch'] and transformers.__version__==P['runtime']['transformers']
                and torch.version.hip,'Frozen native AMD runtime changed')
            torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.set_float32_matmul_precision('highest')
            devices=[]
            from meeting_acoustic_contract_20261116 import select_gpu
            for i in range(torch.cuda.device_count()):
                prop=torch.cuda.get_device_properties(i);devices.append({'index':i,'name':prop.name,'architecture':prop.gcnArchName})
            chosen=select_gpu(devices);torch.cuda.set_device(chosen['index']);device='cuda:'+str(chosen['index'])
            from companion_community1_adapter_20261115 import pin_rocm_blas
            pin_rocm_blas(P['blas']['file'],P['blas']['sha256']);save(device=chosen)
            guard=GuardedGpu(torch,out,save,stop,fraction=.5,minimum_ram=P['minimumAvailableBytes'])
            if a.phase=='preflight':
                require_baseline()
                guard.heartbeat(force=True,state='PROVING_NATIVE_AND_BLOCKED_GPU_TDT_LOSS')
                proof=gpu_loss_contract(torch,device);atomic_json(out/'loss-contract.json',proof)
                state['tinyLossGradientProofPassed']=True;gc.collect();torch.cuda.empty_cache()
            from transformers import AutoConfig,AutoProcessor,GenerationConfig,StoppingCriteria,StoppingCriteriaList
            from moss_streamed_weights_20261104 import load_streamed_weights
            config=AutoConfig.from_pretrained(P['modelRoot'],local_files_only=True,trust_remote_code=False)
            config._attn_implementation='eager';config.encoder_config._attn_implementation='eager'
            model=make_empty(config,torch)
            save(state='LOADING_EXACT_NATIVE_TDT_FACTORY',currentOperationBudgetSeconds=180)
            weights,receipt=load_streamed_weights(P['weights']['file'],torch=torch,device=device,
                expected_sha256=P['weights']['sha256'],chunk_bytes=8*1024**2)
            model.load_state_dict(weights,strict=True,assign=True);del weights;gc.collect()
            model=model.to(device).eval().requires_grad_(False)
            require(all(p.device==torch.device(device) and p.dtype==torch.float32 and not p.is_meta
                for p in model.parameters()),'PublishedF32 native GPU parameters required')
            model.generation_config=GenerationConfig.from_pretrained(P['modelRoot'],local_files_only=True)
            require(set(model.generation_config.suppress_tokens)==set(range(config.vocab_size,config.vocab_size+5)),
                'Published duration-logit suppression differs')
            atomic_json(out/'factory-load.json',receipt);guard.attach(model)
            processor=AutoProcessor.from_pretrained(P['modelRoot'],local_files_only=True,trust_remote_code=False)
            require(processor._decoder_type=='tdt' and processor.feature_extractor.sampling_rate==16000
                and processor.feature_extractor.hop_length==160,'Published TDT frontend/decoder differs')
            named=dict(model.named_parameters());buffers=dict(model.named_buffers())
            names=plan['trainableParameterNames'];mutable=plan['allowedMutableBufferNames']
            require(sum(named[n].numel() for n in names)==118886022,'Exact trainable parameter count differs')
            def checkpoint_store(root,optimizer=None):
                return CheckpointStore(root,binding,torch=torch,model=model,names=names,buffer_names=mutable,
                    optimizer=optimizer,device=device,heartbeat=guard.heartbeat,
                    minimum_free_bytes=P['minimumDiskFreeBytes'],budget_bytes=P['checkpointBudgetBytes'])
            def features(row):
                with wave.open(row['audio'],'rb') as stream:
                    require((stream.getnchannels(),stream.getsampwidth(),stream.getframerate(),stream.getnframes())
                        ==(1,2,16000,row['frames']),'Original PCM format/frame count differs')
                    raw=stream.readframes(stream.getnframes())
                samples=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768
                request=processor(audio=samples,sampling_rate=16000,return_tensors='pt',
                    audio_kwargs={'truncation':False,'device':'cpu'}).to(device)
                require(int(request['attention_mask'].sum())==row['frames']//160,'Feature extractor truncated input')
                return request
            training=a.phase in ('preflight','train') or resume
            if not training:
                evaluated_checkpoint=None
                if a.phase=='validate':
                    final=read(run/'training-completed.json')
                    require(final['binding']==binding and final['completedTrainingExamples']==475
                        and final['candidateOptimizerUpdates']==119,'Fixed one-epoch training incomplete')
                    restored=checkpoint_store(run/'checkpoints').restore(include_optimizer=False,restore_rng=False)
                    evaluated_checkpoint=require_final_checkpoint(restored,final)
                    state['evaluatedCheckpoint']=evaluated_checkpoint
                    state['candidateOptimizerUpdates']=restored['optimizerUpdates']
                    state['completedTrainingExamples']=restored['completedExamples']
                    state['checkpointPointerSelection']=restored['pointerSelection']
                    require(frozen_digest(model,names,mutable,torch=torch,heartbeat=guard.heartbeat)==final['frozenDigest'],
                        'Validation factory frozen tensors differ')
                cases=read(P['validationAudioOnly']);require(len(cases)==12,'Fixed English12 required')
                for row in cases:
                    require(sha(row['audio'])==row['audioSha256'],'Original validation input changed')
                    guard.heartbeat(force=True,state='DECODING_TDT_'+a.phase.upper(),currentId=row['id'])
                    request=features(row);encoder_frames=int(model._get_subsampling_output_length(request['attention_mask'].sum(-1))[0])
                    tick=time.perf_counter()
                    class OwnedStop(StoppingCriteria):
                        def __call__(self,input_ids,scores,**kwargs):
                            guard.heartbeat();require(time.perf_counter()-tick<600,'Fixed English decode time budget');return False
                    state['newNeuralCalls']+=1
                    with torch.inference_mode():result=model.generate(**request,do_sample=False,disable_compile=True,
                        stopping_criteria=StoppingCriteriaList([OwnedStop()]))
                    torch.cuda.synchronize();seconds=time.perf_counter()-tick
                    ids=result.sequences[0].cpu().tolist();durations=result.durations[0].cpu().tolist()
                    require(len(ids)==len(durations) and all(d>=0 for d in durations),'Native token/duration pairing differs')
                    eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos or []
                    natural=sum(durations)>=encoder_frames or bool(ids and ids[-1] in eos)
                    packet={'id':row['id'],'binding':binding,'audioSha256':row['audioSha256'],
                        'generatedIdsIncludingBlank':ids,'frameDurations':durations,'encoderFrames':encoder_frames,
                        'naturalTermination':natural,'seconds':seconds,'allInputFramesPreserved':True,
                        'text':processor.batch_decode(result.sequences,skip_special_tokens=True,
                            clean_up_tokenization_spaces=False,group_tokens=False)[0],
                        'wordsPostEdited':False,'referenceUsed':False,'phase':a.phase,
                        'evaluatedCheckpoint':evaluated_checkpoint,'inputFrames':row['frames'],
                        'weightsDtype':'published float32 unchanged','repeatedLexicalTokensCollapsed':False}
                    f=out/'results'/(row['id']+'.json');atomic_json(f,packet)
                    require(natural,'Incomplete TDT output; no changed-window retry')
                    state['completed'].append({'id':row['id'],'file':str(f),'sha256':sha(f)})
                    del result,request;gc.collect();torch.cuda.empty_cache();guard.heartbeat(force=True)
                save(state='COMPLETE_TDT_'+a.phase.upper()+'_12_PENDING_INDEPENDENT_SCORE')
            else:
                if a.phase!='preflight':
                    pre=read(run/'preflight/completed.json')
                    require(pre['binding']==binding and pre['state']=='PASS_REAL_TDT_GPU_TRAINING_AND_CHECKPOINT_PREFLIGHT'
                        and pre['checkpointExactRoundtrip'] and pre['tinyLossGradientProofPassed']
                        and pre['steadyAdamStatesPresentForMaximumShape']
                        and pre['integerBuffersOptimizerStepsAndRngExactRoundtrip'],
                        'Actual GPU preflight not passed; training prohibited')
                    require_baseline()
                rows=train_rows();order=list(range(475));random.Random(P['training']['seed']).shuffle(order)
                order_sha=hashlib.sha256(json.dumps([rows[i]['id'] for i in order]).encode()).hexdigest()
                before=frozen_digest(model,names,mutable,torch=torch,heartbeat=guard.heartbeat)
                model.eval()
                for name in names:named[name].requires_grad_(True)
                # Frozen parent/subsampling/first20layers remain eval. Only the
                # chosen modules use dropout and update their own running stats.
                for layer in model.encoder.layers[20:]:layer.train()
                model.encoder_projector.train();model.decoder.train();model.joint.train()
                require(not model.encoder.training and all(not m.training for m in model.encoder.layers[:20]),
                    'Frozen encoder modules acquired mutable training behavior')
                parameters=[named[n] for n in names]
                optimizer=torch.optim.AdamW(parameters,lr=1e-5,betas=(.9,.999),eps=1e-8,
                    weight_decay=.01,foreach=False,fused=False,amsgrad=False)
                # Account for steady-state Adam storage before the largest
                # real backward, rather than allocating it only afterwards.
                for parameter in parameters:
                    adam=optimizer.state[parameter]
                    adam['step']=torch.tensor(0.,dtype=torch.float32)
                    adam['exp_avg']=torch.zeros_like(parameter)
                    adam['exp_avg_sq']=torch.zeros_like(parameter)
                optimizer.zero_grad(set_to_none=True)
                torch.random.default_generator.manual_seed(P['training']['seed']);torch.cuda.manual_seed(P['training']['seed'])
                random.seed(P['training']['seed'])
                store=checkpoint_store(out/'checkpoints' if a.phase=='preflight' else run/'checkpoints',optimizer)
                start=0;updates=0
                if resume:
                    saved=store.restore();require(not saved['preflightOnly'] and saved['orderSha256']==order_sha
                        and saved['frozenDigest']==before,'Recovery data/order/frozen factory differs')
                    start=saved['completedExamples'];updates=saved['optimizerUpdates']
                    valid_resume_position(start,updates)
                    state['checkpointPointerSelection']=saved['pointerSelection']
                elif a.phase=='train':require(not(run/'checkpoints/latest-checkpoint.json').exists(),'Use explicit resume for committed progress')
                def loss_for(row):
                    guard.heartbeat(force=True,state='FORWARD_TDT_TRAIN_ONLY',currentId=row['id'])
                    request=features(row);labels=torch.tensor([row['targetIds']],device=device,dtype=torch.long)
                    decoder_ids=torch.cat([torch.full((1,1),config.blank_token_id,device=device,dtype=torch.long),labels],dim=1)
                    state['newNeuralCalls']+=1
                    encoded=model.get_audio_features(**request);decoded=model.decoder(decoder_ids)
                    loss=blocked_joint_loss(model.joint,encoded.pooler_output,decoded,labels,
                        encoded.attention_mask.sum(-1),vocab_size=config.vocab_size,
                        blank_token_id=config.blank_token_id,durations=config.durations,
                        torch=torch,chunk_frames=16,heartbeat=guard.heartbeat,checkpoint_joint=True)
                    require(torch.isfinite(loss),'Nonfinite real training loss')
                    return loss
                if a.phase=='preflight':
                    probes=list(dict.fromkeys([plan['largestJointCase']['id'],plan['longestCase']['id']]))
                    measurements=[]
                    for identity in probes:
                        row=next(r for r in rows if r['id']==identity);optimizer.zero_grad(set_to_none=True)
                        torch.cuda.reset_peak_memory_stats();tick=time.perf_counter();loss=loss_for(row)
                        guard.heartbeat(force=True,state='BACKWARD_REAL_TDT_MAXIMUM_SHAPE',currentId=identity)
                        loss.backward();norm=torch.nn.utils.clip_grad_norm_(parameters,1.,error_if_nonfinite=True)
                        require(all(named[n].grad is not None and torch.isfinite(named[n].grad).all() for n in names),
                            'A selected parameter lacks finite gradients')
                        require(all(p.grad is None for n,p in named.items() if n not in set(names)),'Frozen parameter acquired gradient')
                        measurements.append({'id':identity,'frames':row['frames'],'labels':len(row['targetIds']),
                            'loss':float(loss),'gradientNormBeforeClip':float(norm),
                            'seconds':time.perf_counter()-tick,'gpu':guard.memory()})
                        del loss;gc.collect();guard.heartbeat(force=True)
                    optimizer.step();state['parameterUpdates']+=1;optimizer.zero_grad(set_to_none=True)
                    require(frozen_digest(model,names,mutable,torch=torch,heartbeat=guard.heartbeat)==before,'Frozen factory mutated')
                    expected=digest_tensors(store.tensors().items(),torch=torch,heartbeat=guard.heartbeat)
                    expected_auxiliary=json.dumps(store.auxiliary_state(),sort_keys=True)
                    path,saved=store.save(completed_examples=0,optimizer_updates=1,order_sha256=order_sha,
                        frozen_sha256=before,preflight_only=True)
                    with torch.no_grad():
                        for value in store.tensors().values():value.zero_()
                        for name in mutable:
                            if buffers[name].dtype!=torch.float32:buffers[name].zero_()
                        for parameter in parameters:optimizer.state[parameter]['step'].zero_()
                    torch.random.default_generator.manual_seed(P['training']['seed']+1)
                    torch.cuda.manual_seed(P['training']['seed']+1);random.seed(P['training']['seed']+1)
                    store.restore()
                    actual=digest_tensors(store.tensors().items(),torch=torch,heartbeat=guard.heartbeat)
                    require(actual==expected,'Restored learned tensors/Adam state differ')
                    require(json.dumps(store.auxiliary_state(),sort_keys=True)==expected_auxiliary,
                        'Restored integer buffers, optimizer steps or RNG differ')
                    require(frozen_digest(model,names,mutable,torch=torch,heartbeat=guard.heartbeat)==before,
                        'Checkpoint roundtrip mutated frozen tensors')
                    save(state='PASS_REAL_TDT_GPU_TRAINING_AND_CHECKPOINT_PREFLIGHT',maximumShapeProofs=measurements,
                        checkpointExactRoundtrip=True,checkpointPayloadSha256=sha(path),frozenDigest=before,
                        candidateTrainingStarted=False,preflightParameterUpdates=1,
                        preflightWeightsMustNotInitializeCandidate=True,steadyAdamStatesPresentForMaximumShape=True,
                        integerBuffersOptimizerStepsAndRngExactRoundtrip=True)
                else:
                    losses=[];completed=start;last_saved=saved if resume else None
                    with (out/'training-loss.jsonl').open('w',encoding='utf-8') as log:
                        for first in range(start,475,4):
                            stop();group=order[first:first+4];optimizer.zero_grad(set_to_none=True)
                            for within,index in enumerate(group):
                                row=rows[index];tick=time.perf_counter();loss=loss_for(row);value=float(loss)
                                guard.heartbeat(force=True,state='BACKWARD_FIXED_TDT_EPOCH',currentId=row['id'])
                                (loss/len(group)).backward();del loss
                                item={'id':row['id'],'trainingIndex':first+within,'loss':value,
                                    'seconds':time.perf_counter()-tick,'at':now()}
                                log.write(json.dumps(item)+'\n');log.flush();losses.append(value)
                                guard.heartbeat(force=True)
                            norm=torch.nn.utils.clip_grad_norm_(parameters,1.,error_if_nonfinite=True)
                            optimizer.step();optimizer.zero_grad(set_to_none=True);updates+=1;state['parameterUpdates']+=1
                            completed=first+len(group)
                            save(state='TRAINING_FIXED_ONE_TDT_EPOCH',candidateOptimizerUpdates=updates,
                                completedTrainingExamples=completed,lastGradientNormBeforeClip=float(norm))
                            if updates%8==0 or completed==475:
                                _,last_saved=store.save(completed_examples=completed,optimizer_updates=updates,
                                    order_sha256=order_sha,frozen_sha256=before)
                    require(frozen_digest(model,names,mutable,torch=torch,heartbeat=guard.heartbeat)==before,'Frozen factory mutated in epoch')
                    require(updates==119 and completed==475,'Fixed epoch incomplete')
                    require(last_saved is not None and last_saved['completedExamples']==475
                        and last_saved['optimizerUpdates']==119,'Final durable checkpoint missing')
                    save(state='COMPLETE_FIXED_ONE_EPOCH_TDT_ENGLISH_ADAPTATION_PENDING_VALIDATION',
                        candidateOptimizerUpdates=updates,completedTrainingExamples=completed,
                        frozenDigest=before,meanTrainingLossThisProcess=sum(losses)/len(losses) if losses else None,
                        finalCheckpoint=checkpoint_identity(last_saved),freshFactoryInitialization=not resume,
                        finalizedCompletedCheckpointWithoutNewUpdates=bool(start==475))
                    atomic_json(run/'training-completed.json',state)
            state['gpuSummary']=guard.close();guard=None;save(currentOperation=None)
            atomic_json(out/'completed.json',state)
        except BaseException as error:
            import traceback
            save(state='FAILED_TDT_'+a.phase.upper()+'_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc());raise
        finally:
            if guard is not None:guard.close()
            pressure.close()

if __name__=='__main__':main()
