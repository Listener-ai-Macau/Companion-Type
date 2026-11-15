"""One fixed source-supervised pass, with both new real meetings frozen in advance."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,time,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from independent_pcm_publication_20261108 import publish_pcm16_wave
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read,sha,load_models,tensor_hash
from companion_tse_training_20261108 import make_spatial_extractor
from companion_tse_activation_memory_20261108 import checkpoint_residual_rnns
from companion_tse_checkpoint_streamed_20261108 import save_checkpoint,restore_checkpoint
from companion_tse_source_runtime_20261108 import unit_inputs,unit_objective
from companion_tse_source_objective_20261108 import waveform_metrics
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();C=Path(args.control);P=read(args.protocol);out=C/args.run_id;out.mkdir(exist_ok=False);protocol_sha=sha(args.protocol);assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
assert read(P['objectiveProof'])['state']=='PASS_SOURCE_OBJECTIVE_ANTI_COLLAPSE_AND_LONGEST_PAIRED_GRADIENTS'
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();state={'state':'LOADING_ORIGINAL_SOURCE_SUPERVISION_MODEL','pid':os.getpid(),'startedAt':datetime.now().astimezone().isoformat(),'protocolSha256':protocol_sha,'newWeightUpdates':0,'completedInputs':0,'qualityQualified':False};save=lambda:atomic_json(out/'state.json',{**state,'limits':limits.query()},progress=True);save()
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(P['seed']);assert torch.version.hip and torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0);base,_,_=load_models(P,out,torch=torch,with_teacher=False);checkpoint_residual_rnns(base,torch=torch);model=make_spatial_extractor(base,torch=torch).cuda();profiles={x['id']:x for x in read(C/'profiles.json')};train=read(C/'training-units.json');validation=read(C/'synthetic-validation-units.json');natural=read(C/'natural-validation-queries.json');assert len(train)==128
    parameters=[(n,p) for n,p in model.named_parameters() if p.requires_grad];names=[n for n,p in parameters];optimizer=torch.optim.AdamW([p for n,p in parameters],lr=P['learningRate'],weight_decay=P['weightDecay']);frozen_before=tensor_hash(list(base.spk_model.named_parameters())+list(base.spk_model.named_buffers()));buffers_before=tensor_hash(model.named_buffers());checkpoint_root=Path(P['checkpointRoot']);checkpoint_root.mkdir(parents=True,exist_ok=True)
    def export(value,peak,folder,identity):
        folder.mkdir(parents=True,exist_ok=True);audio=(value*peak).float().cpu().numpy();assert np.isfinite(audio).all();divisor=max(1.,float(np.max(np.abs(audio))));pcm=np.rint(audio/divisor*32768).clip(-32768,32767).astype('<i2');dest=folder/(identity+'.wav');published=publish_pcm16_wave(dest,pcm.tobytes());return {'audio':str(dest),'audioSha256':published['audioSha256'],'audioSeconds':len(pcm)/16000,'pcmExportDivisor':divisor}
    def evaluate(label):
        model.eval();result=[];audio=[];state['state']='VALIDATING_'+label.upper();save()
        for unit in validation:
            pair,enrollments,targets,peak=unit_inputs(unit,profiles,torch=torch);start=time.perf_counter()
            with torch.no_grad():
                estimates=[model(pair,p)[0] for p in enrollments]
                for index,value in enumerate(estimates):
                    metrics=waveform_metrics(value,targets[index],torch=torch) if targets else None;ratio=float(value.square().mean().sqrt()/pair[0,0].square().mean().sqrt().clamp_min(1e-6));packet=export(value,peak,Path(P['audioRoot'])/'synthetic'/label,unit['id']+'--'+str(index));result.append({'id':unit['id']+'--'+str(index),'unitId':unit['id'],'meeting':unit['meeting'],'kind':unit['kind'],'metrics':metrics,'rmsToMixture':ratio,'profileId':unit['targets'][index]['profileId'] if targets else unit['profileId'],**packet})
            state['completedInputs']+=1;save();del pair,enrollments,targets,estimates
        for query in natural:
            unit={'mixture':query,'profileId':query['profileId']};pair,enrollments,_,peak=unit_inputs(unit,profiles,torch=torch)
            with torch.no_grad():value=model(pair,enrollments[0])[0];packet=export(value,peak,Path(P['audioRoot'])/'natural'/label,query['id'])
            audio.append({'id':label+'--'+query['id'],'sourceExampleId':query['id'],'condition':label,'kind':'natural_real_meeting','meeting':query['meeting'],'category':query['category'],'profileId':query['profileId'],'sourceAudioSha256':query['audioSha256'],'inferenceReferenceProvided':False,**packet});state['completedInputs']+=1;save();del value,pair,enrollments
        record={'state':'COMPLETE_FROZEN_SOURCE_VALIDATION_AUDIO','protocolSha256':protocol_sha,'synthetic':result,'naturalAudioOnly':audio,'supervisedProfilesNotAutomaticMeetingIdentity':True,'qualityQualified':False};atomic_json(C/(label+'-validation.json'),record);return record
    resume=read(C/'latest-training-checkpoint.json') if (C/'latest-training-checkpoint.json').exists() else None;committed=[read(p) for p in checkpoint_root.glob('step-*/checkpoint.json') if read(p)['protocolSha256']==protocol_sha]
    if committed:
        newest=max(committed,key=lambda x:x['completedSteps'])
        if resume is None or newest['completedSteps']>resume['completedSteps']:resume=newest;atomic_json(C/'latest-training-checkpoint.json',resume)
    completed=0
    if resume:
        completed=restore_checkpoint(model,optimizer,resume,torch=torch,protocol_sha=protocol_sha,parameter_names=names);before=read(C/'baseline-validation.json');assert before['protocolSha256']==protocol_sha;state.update(newWeightUpdates=completed,resumedCompletedSteps=completed);save()
    else:
        before=evaluate('baseline');record=save_checkpoint(model,optimizer,torch=torch,root=checkpoint_root,step=0,protocol_sha=protocol_sha,parameter_names=names);atomic_json(C/'latest-training-checkpoint.json',record)
    model.train();state['state']='TRAINING_FIXED_SOURCE_SUPERVISION_PASS';save()
    for index in range(completed,len(train)):
        assert not (C/'stop.request').exists();unit=train[index];optimizer.zero_grad(set_to_none=True);pair,enrollments,targets,peak=unit_inputs(unit,profiles,torch=torch);torch.cuda.synchronize();start=time.perf_counter();estimates=[model(pair,p)[0] for p in enrollments];loss=unit_objective(unit,estimates,targets,pair,torch=torch);assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_([p for n,p in parameters],P['gradientClipNorm'],error_if_nonfinite=True);optimizer.step();torch.cuda.synchronize();step=index+1;row={'step':step,'id':unit['id'],'kind':unit['kind'],'loss':float(loss),'gradientNormBeforeClip':float(norm),'wholeStepSeconds':time.perf_counter()-start,'gpuPeakAllocatedBytes':torch.cuda.max_memory_allocated(),'gpuPeakReservedBytes':torch.cuda.max_memory_reserved()}
        with (out/'history.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
        state.update(state='TRAINING_FIXED_SOURCE_SUPERVISION_PASS',newWeightUpdates=step,completedInputs=step,latestTrainingMetrics=row);save();del pair,enrollments,targets,estimates,loss
        if step%P['checkpointInterval']==0 or step==len(train):
            record=save_checkpoint(model,optimizer,torch=torch,root=checkpoint_root,step=step,protocol_sha=protocol_sha,parameter_names=names);atomic_json(C/'latest-training-checkpoint.json',record);state['lastDurableCheckpointStep']=step;save()
        time.sleep(P['interStepIdleSeconds'])
    assert tensor_hash(list(base.spk_model.named_parameters())+list(base.spk_model.named_buffers()))==frozen_before and tensor_hash(model.named_buffers())==buffers_before
    after=evaluate('adapted')
    def aggregate(record):
        result={}
        for kind in ['known_additive_mixture','single_target_preservation','absent_known_identity']:
            group=[x for x in record['synthetic'] if x['kind']==kind];value={'examples':len(group),'meanRmsToMixture':sum(x['rmsToMixture'] for x in group)/len(group)}
            if kind!='absent_known_identity':value.update({k:sum(x['metrics'][k] for x in group)/len(group) for k in ['normalizedL1','rmsGain','absoluteRmsGainError','scaleSensitiveSdrDb']})
            result[kind]=value
        return result
    a,b=aggregate(before),aggregate(after);tolerance=P['comparisonTolerance'];meetings=sorted({r['meeting'] for r in after['synthetic']});per_meeting={}
    for meeting in meetings:
        per_meeting[meeting]={arm:sum(x['metrics']['normalizedL1'] for x in record['synthetic'] if x['meeting']==meeting and x['kind']=='known_additive_mixture')/sum(x['meeting']==meeting and x['kind']=='known_additive_mixture' for x in record['synthetic']) for arm,record in [('baseline',before),('adapted',after)]}
    both=all(x['adapted']<x['baseline'] for x in per_meeting.values());beats_silence=all(b[k]['normalizedL1']<1 for k in ['known_additive_mixture','single_target_preservation']);gain_ok=b['known_additive_mixture']['absoluteRmsGainError']<=a['known_additive_mixture']['absoluteRmsGainError']+tolerance;solo_ok=b['single_target_preservation']['normalizedL1']<=a['single_target_preservation']['normalizedL1']+tolerance;absent_ok=b['absent_known_identity']['meanRmsToMixture']<=a['absent_known_identity']['meanRmsToMixture']+tolerance;advance=both and beats_silence and gain_ok and solo_ok and absent_ok
    atomic_json(C/'training-review.json',{'state':'SOURCE_SUPERVISION_WAVEFORM_GATE_PASSED_REQUIRES_NATURAL_FREE_ASR' if advance else 'SOURCE_SUPERVISION_REJECTED_FROZEN_WAVEFORM_VALIDATION','protocolSha256':protocol_sha,'completedWeightUpdates':len(train),'actualTrainingTargetQueries':192,'before':a,'after':b,'perNewMeetingMixedNormalizedL1':per_meeting,'bothNewMeetingsMixedWaveformImproved':both,'positiveWaveformBeatsSilence':beats_silence,'mixedGainErrorNonregression':gain_ok,'singleTargetPreservationNonregression':solo_ok,'absentRmsNonregression':absent_ok,'advanceToNaturalFreeAsr':advance,'naturalQueryCountEachCondition':len(natural),'recognizerUsedForTraining':False,'speakerEncoderFrozen':True,'modelBuffersUnchanged':True,'validationNotUsedForWeightUpdates':True,'physicalSpeakerIndependenceKnown':False,'qualityQualified':False,'saleQualified':False,'finalCheckpoint':read(C/'latest-training-checkpoint.json')});state.update(state='COMPLETE_SOURCE_SUPERVISION_TRAINING_REVIEW_REQUIRED',newWeightUpdates=len(train),lastDurableCheckpointStep=len(train),qualityQualified=False)
except BaseException as error:state.update(state='SOURCE_SUPERVISION_TRAINING_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps(state),flush=True)
