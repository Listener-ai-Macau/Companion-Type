"""One fixed pass over real TRAIN pairs; separate-room validation, no LR sweep."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from independent_pcm_publication_20261108 import publish_pcm16_wave
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read,sha,load_models,load_pair,tensor_hash
from companion_tse_training_20261108 import make_spatial_extractor,target_text,teacher_batch,teacher_loss,waveform_supervision
from companion_tse_checkpoint_streamed_20261108 import save_checkpoint,restore_checkpoint
from companion_tse_activation_memory_20261108 import checkpoint_residual_rnns
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();C=Path(args.control);P=read(args.protocol);out=C/args.run_id;out.mkdir(exist_ok=False);assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
assert read(P['gradientProof'])['state']=='PASS_TRAINING_GRAPH_PARITY_LABELS_GRADIENTS_AND_FROZEN_TEACHER' and sha(P['gradientProof'])==P['gradientProofSha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();protocol_sha=sha(args.protocol);state={'state':'LOADING_REAL_TSE_TRAINING_JOB','pid':os.getpid(),'startedAt':datetime.now().astimezone().isoformat(),'protocolSha256':protocol_sha,'newWeightUpdates':0,'completedInputs':0,'qualityQualified':False};save=lambda:atomic_json(out/'state.json',{**state,'limits':limits.query()},progress=True);save()
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(P['seed']);assert torch.version.hip and torch.cuda.device_count()==1;gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030');torch.cuda.set_device(0)
    base,teacher,processor=load_models(P,out,torch=torch)
    def memory_point(label):
        import psutil
        torch.cuda.synchronize()
        row={'at':datetime.now().astimezone().isoformat(),'phase':label,'gpuAllocatedBytes':torch.cuda.memory_allocated(),'gpuReservedBytes':torch.cuda.memory_reserved(),'gpuFreeAndTotalBytes':list(torch.cuda.mem_get_info()),'systemAvailableBytes':psutil.virtual_memory().available}
        with (out/'preflight-memory.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
        state.update(state=label,lastMemoryPoint=row);save()
    def observe_rnn(name,edge):
        if state.get('recordRnnMemory',False):memory_point('PREFLIGHT_RNN_'+name+'_'+edge)
    modules=checkpoint_residual_rnns(base,torch=torch,observer=observe_rnn);model=make_spatial_extractor(base,torch=torch).to('cuda:0');memory_point('EXACT_MODELS_READY_WITH_RECOMPUTATION');rows=read(P['dataManifest']);byid={r['id']:r for r in rows};train=[byid[x] for x in P['trainingOrder']];validation=[byid[x] for x in P['validationOrder']];assert all(x['role']=='train' for x in train) and all(x['role']=='validation' for x in validation)
    parameters=[(n,p) for n,p in model.named_parameters() if p.requires_grad];names=[n for n,p in parameters];optimizer=torch.optim.AdamW([p for n,p in parameters],lr=P['learningRate'],weight_decay=P['weightDecay']);teacher_versions={n:p._version for n,p in teacher.named_parameters()};speaker_hash=tensor_hash(list(base.spk_model.named_parameters())+list(base.spk_model.named_buffers()));initial_buffers=tensor_hash(model.named_buffers());E=Path(P['checkpointRoot']);E.mkdir(exist_ok=True)
    def losses(example,output,pair,peak):
        waveform,scope=waveform_supervision(output,pair[0],example,torch=torch)
        # Absent speech has exact zero waveform supervision. Do not depend on
        # a recognizer's Chinese-prefilled blank-token preference for silence.
        if example['category']=='absent_other_speech':ce=output.sum()*0.
        else:ce=teacher_loss(teacher,teacher_batch(output*peak,target_text(example),processor,torch=torch),torch=torch)
        return ce+waveform,ce,waveform,scope
    def validation_pass(label):
        model.eval();folder=Path(P['audioRoot'])/label;folder.mkdir(parents=True,exist_ok=True);results=[]
        for example in validation:
            pair,profile,peak=load_pair(example,torch=torch,device='cuda:0');torch.cuda.synchronize();start=time.perf_counter()
            with torch.no_grad():
                estimate=model(pair,profile)[0];loss,ce,fidelity,scope=losses(example,estimate,pair,peak);rms_ratio=float(estimate.square().mean().sqrt()/pair[0,0].square().mean().sqrt().clamp_min(1e-8));value=(estimate*peak).float().cpu().numpy();divisor=max(1.,float(np.max(np.abs(value))));pcm=np.rint(value/divisor*32768).clip(-32768,32767).astype('<i2')
            torch.cuda.synchronize();dest=folder/(example['id']+'.wav');publication=publish_pcm16_wave(dest,pcm.tobytes());results.append({'id':example['id'],'category':example['category'],'meeting':example['meeting'],'personForScoringOnly':example['targetPersonForSupervisedTrainingOnly'],'condition':label,'audio':str(dest),'audioSha256':publication['audioSha256'],'audioSeconds':example['audioSeconds'],'sourceAudioSha256':example['audioSha256'],'sourceProfileSha256':example['profileAudioSha256'],'sourceReferenceUsedOnlyForLoss':True,'inferenceTranscriptProvided':False,'totalLoss':float(loss),'presentTargetTeacherCe':float(ce) if example['category']!='absent_other_speech' else None,'waveformLoss':float(fidelity),'outputToInputRmsRatio':rms_ratio,'waveformScope':scope,'pcmExportDivisor':divisor,'wholeExampleSeconds':time.perf_counter()-start});state['completedInputs']+=1;state['state']='VALIDATING_'+label.upper();save();del pair,profile,estimate,loss,ce,fidelity
        atomic_json(C/(label+'-validation.json'),{'state':'COMPLETE_FIXED_VALIDATION','protocolSha256':protocol_sha,'conditions':label,'examples':results,'referenceUse':'Supervised-profile diagnostic validation only, not automatic whole-meeting deployment or final holdout.'});return results
    resume=read(C/'latest-training-checkpoint.json') if (C/'latest-training-checkpoint.json').exists() else None;completed=0
    # A crash can occur after the durable checkpoint commits but before its
    # latest-pointer publication. Recover that exact completed checkpoint.
    committed=[read(p) for p in E.glob('step-*/checkpoint.json') if read(p)['protocolSha256']==protocol_sha]
    if committed:
        newest=max(committed,key=lambda x:x['completedSteps']);assert newest['completedSteps']<=len(train)
        if resume is None or newest['completedSteps']>resume['completedSteps']:
            assert sha(newest['trainableWeights'])==newest['trainableWeightsSha256'] and sha(newest['optimizerState'])==newest['optimizerStateSha256'];resume=newest;atomic_json(C/'latest-training-checkpoint.json',resume);state['recoveredCommittedCheckpointPointerStep']=newest['completedSteps'];save()
    if resume:
        assert (C/'baseline-validation.json').exists();completed=restore_checkpoint(model,optimizer,resume,torch=torch,protocol_sha=protocol_sha,parameter_names=names);before=read(C/'baseline-validation.json')['examples'];state.update(resumedCompletedSteps=completed,newWeightUpdates=completed);save()
    else:
        # Largest training query must fit with correct labels before updating
        # anything. No truncation or smaller-query fallback after an OOM.
        example=max(train,key=lambda x:x['audioSeconds']);state['preflightId']=example['id'];state['recordRnnMemory']=True;model.train();torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();pair,profile,peak=load_pair(example,torch=torch,device='cuda:0');memory_point('PREFLIGHT_FULL_LONGEST_EXTRACTOR_FORWARD');estimate=model(pair,profile)[0];memory_point('PREFLIGHT_FULL_LONGEST_TEACHER_LOSS');loss,ce,fidelity,scope=losses(example,estimate,pair,peak);memory_point('PREFLIGHT_FULL_LONGEST_BACKWARD');loss.backward();assert torch.isfinite(loss);model.zero_grad(set_to_none=True);memory_point('PREFLIGHT_FULL_LONGEST_BACKWARD_COMPLETE');state['recordRnnMemory']=False;atomic_json(out/'largest-query-gradient-memory.json',{'state':'PASS_LARGEST_TRAIN_QUERY_BACKWARD_BEFORE_UPDATES','id':example['id'],'seconds':example['audioSeconds'],'allocatedGpuPeakBytes':torch.cuda.max_memory_allocated(),'reservedGpuPeakBytes':torch.cuda.max_memory_reserved(),'newWeightUpdates':0});del pair,profile,estimate,loss,ce,fidelity;torch.cuda.empty_cache()
        before=validation_pass('baseline');record=save_checkpoint(model,optimizer,torch=torch,root=E,step=0,protocol_sha=protocol_sha,parameter_names=names);atomic_json(C/'latest-training-checkpoint.json',record)
    model.train();state['state']='TRAINING_FIXED_SINGLE_PASS';save()
    for index in range(completed,len(train)):
        assert not (C/'stop.request').exists();example=train[index];optimizer.zero_grad(set_to_none=True);pair,profile,peak=load_pair(example,torch=torch,device='cuda:0');torch.cuda.synchronize();start=time.perf_counter();estimate=model(pair,profile)[0];loss,ce,fidelity,scope=losses(example,estimate,pair,peak);assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_([p for n,p in parameters],P['gradientClipNorm'],error_if_nonfinite=True);optimizer.step();torch.cuda.synchronize();step=index+1
        assert all(p._version==teacher_versions[n] and p.grad is None for n,p in teacher.named_parameters());assert not any(p.grad is not None for p in base.spk_model.parameters())
        row={'step':step,'id':example['id'],'category':example['category'],'loss':float(loss.detach()),'presentTargetCe':float(ce.detach()),'waveformLoss':float(fidelity.detach()),'gradientNormBeforeClip':float(norm),'wholeStepSeconds':time.perf_counter()-start,'gpuPeakAllocatedBytes':torch.cuda.max_memory_allocated(),'gpuPeakReservedBytes':torch.cuda.max_memory_reserved()}
        with (out/'history.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
        state.update(state='TRAINING_FIXED_SINGLE_PASS',newWeightUpdates=step,completedInputs=step,latestTrainingMetrics=row);save();del pair,profile,estimate,loss,ce,fidelity
        if step%P['checkpointInterval']==0 or step==len(train):
            checkpoint=save_checkpoint(model,optimizer,torch=torch,root=E,step=step,protocol_sha=protocol_sha,parameter_names=names);atomic_json(C/'latest-training-checkpoint.json',checkpoint);state['lastDurableCheckpointStep']=step;save()
        time.sleep(P['interStepIdleSeconds'])
    assert tensor_hash(list(base.spk_model.named_parameters())+list(base.spk_model.named_buffers()))==speaker_hash;assert tensor_hash(model.named_buffers())==initial_buffers
    after=validation_pass('adapted')
    def aggregate(values):
        return {category:{'examples':len(group),'meanTeacherCe':sum(r['presentTargetTeacherCe'] for r in group)/len(group) if category!='absent_other_speech' else None,'meanWaveformLoss':sum(r['waveformLoss'] for r in group)/len(group),'meanOutputRmsRatio':sum(r['outputToInputRmsRatio'] for r in group)/len(group),'maximumOutputRmsRatio':max(r['outputToInputRmsRatio'] for r in group)} for category in ['present_solo','present_overlap','absent_other_speech'] if (group:=[r for r in values if r['category']==category])}
    a,b=aggregate(before),aggregate(after);present_ok=all(b[k]['meanTeacherCe']<=a[k]['meanTeacherCe']+P['lossComparisonTolerance'] for k in ['present_solo','present_overlap']);absent_ok=b['absent_other_speech']['meanOutputRmsRatio']<a['absent_other_speech']['meanOutputRmsRatio'] and b['absent_other_speech']['maximumOutputRmsRatio']<=a['absent_other_speech']['maximumOutputRmsRatio']+P['lossComparisonTolerance'];solo_ok=b['present_solo']['meanWaveformLoss']<=a['present_solo']['meanWaveformLoss']+P['lossComparisonTolerance'];worth_decoding=present_ok and absent_ok and solo_ok
    atomic_json(C/'training-review.json',{'state':'FIXED_TRAINING_PASS_VALIDATION_PROXY_IMPROVED_NEEDS_FREE_ASR' if worth_decoding else 'FIXED_TRAINING_PASS_REJECTED_VALIDATION_REGRESSION','protocolSha256':protocol_sha,'completedWeightUpdates':len(train),'oneFixedPass':True,'before':a,'after':b,'presentCeNonregression':present_ok,'absenceEnergyImprovedWithoutWorseMaximum':absent_ok,'soloWaveformNonregression':solo_ok,'advanceToUnpromptedFreeGeneration':worth_decoding,'speakerEncoderFrozenHashUnchanged':True,'recognizerWeightsFrozenVersionsUnchanged':True,'modelBuffersUnchanged':True,'validationReferencesNeverUsedForWeightUpdates':True,'supervisedProfilesInValidationNotAutomaticMeetingDiarization':True,'qualityQualified':False,'strictCerBelow5Qualified':False,'finalCheckpoint':read(C/'latest-training-checkpoint.json')})
    state.update(state='COMPLETE_FIXED_TSE_TRAINING_PASS_REVIEW_REQUIRED',lastDurableCheckpointStep=len(train),newWeightUpdates=len(train),qualityQualified=False)
except BaseException as error:state.update(state='TSE_TRAINING_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps(state),flush=True)
