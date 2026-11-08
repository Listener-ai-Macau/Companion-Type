"""Frozen-backbone real-meeting head adaptation; isolated from product defaults."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave,random
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True,choices=['features','probe','train','evaluate']);parser.add_argument('--resume',action='store_true');args=parser.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-target-activity-adaptation';E=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108');OLD=R/'docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
P=read(C/'protocol.json');assert sha(__file__)==P['workerSourceSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
binding={'protocolSha256':sha(C/'protocol.json'),'workerSourceSha256':P['workerSourceSha256']};target=C/(args.stage+'-state.json');assert args.resume==target.exists();tick=time.perf_counter();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
state={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PREPARING_'+args.stage.upper(),'pid':os.getpid(),'stage':args.stage,'binding':binding,'completedInputs':0,'newNeuralCalls':0,'reusedOutputs':0,'qualityQualified':False}
if target.exists():
    old=read(target);assert old['binding']==binding
    archive=C/('prior-'+args.stage+'-state-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
def save(phase=None):
    if phase:state['state']=phase
    state['limits']=limits.query();atomic_json(target,state,progress=True)
save()
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(P['seed']);np.random.seed(P['seed']);random.seed(P['seed'])
    from target_activity_native_20261108 import load_native_pair,tensor_state_sha
    from target_activity_adapter_20261108 import MeetingActivityAdapter
    pair,proof=load_native_pair(torch);atomic_json(C/('native-loader-'+args.stage+'-'+str(os.getpid())+'.json'),{**proof,'binding':binding,'limits':limits.query()})
    prepared=read(C/'prepared-audio.json');device='cuda:0'
    def pcm(file):
        with wave.open(file,'rb') as f:
            assert f.getframerate()==16000 and f.getnchannels()==1 and f.getsampwidth()==2
            return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
    def artifact_load(row):
        assert sha(row['featureFile'])==row['featureSha256']
        with np.load(row['featureFile'],allow_pickle=False) as data:return {k:torch.from_numpy(data[k]).to(device) for k in data.files}
    def vectors_load():
        v=read(C/'training-enrollment-vectors.json');assert v['binding']==binding;return v['vectors']
    if args.stage=='features':
        folder=E/'features';folder.mkdir(exist_ok=True);receipts=C/'feature-receipts';receipts.mkdir(exist_ok=True);items=[]
        for row in [r for r in prepared if r['kind']=='query']:items.append({**row,'featureKind':'supervised'})
        for case in read(OLD/'audio-only.json'):items.append({**case,'featureKind':'old-evaluation','kind':'old-control'})
        feature_manifest=[];pair.model.eval()
        for row in items:
            receipt=receipts/(row['id']+'.json');output=folder/(row['id']+'.npz')
            if receipt.exists():
                packet=read(receipt);assert packet['binding']==binding and packet['audioSha256']==row['audioSha256'] and sha(output)==packet['featureSha256'];state['reusedOutputs']+=1
            else:
                assert sha(row['audio'])==row['audioSha256'];audio=pcm(row['audio']);assert len(audio)==row['endSample']-row['startSample']
                import nomo_pvad
                with torch.inference_mode():
                    fb=nomo_pvad._eres2netv2_fbank(torch.from_numpy(audio)).unsqueeze(0);frames=pair.model._backbone_forward(fb);lengths=torch.tensor([fb.shape[1]],dtype=torch.long,device=device)
                np.savez(output,fbank=fb.cpu().numpy(),frames=frames.cpu().numpy(),lengths=lengths.cpu().numpy())
                packet={'id':row['id'],'binding':binding,'featureKind':row['featureKind'],'audioSha256':row['audioSha256'],'featureFile':str(output),'featureSha256':sha(output),'inputFeatureFrames':fb.shape[1],'frameFeatureShape':list(frames.shape),'role':row.get('role'),'meeting':row['meeting']};atomic_json(receipt,packet);state['newNeuralCalls']+=1;time.sleep(1)
            feature_manifest.append(packet);state['completedInputs']+=1;save('EXTRACTING_FROZEN_NATIVE_FEATURES')
        vectorfile=C/'training-enrollment-vectors.json'
        if vectorfile.exists():vectors=vectors_load();state['reusedOutputs']+=len(vectors)
        else:
            vectors={}
            for row in [r for r in prepared if r['kind']=='profile']:
                assert sha(row['audio'])==row['audioSha256'];vector=pair.extract_emb(pcm(row['audio']));assert vector.shape==(1,192) and torch.isfinite(vector).all();vectors[row['meeting']+':'+row['person']]=vector.cpu().tolist();state['newNeuralCalls']+=1;state['completedInputs']+=1;save('EXTRACTING_MATCHED_SUPERVISED_PROFILES');time.sleep(1)
            atomic_json(vectorfile,{'binding':binding,'vectors':vectors,'supervisionOnlyInTrainingProfiles':True})
        oldvectors=read(OLD/'native-enrollment-vectors.json');oldprotocol=read(OLD/'protocol.json');assert oldvectors['binding']['protocolSha256']==sha(OLD/'protocol.json') and oldvectors['binding']['modelReadySha256']==oldprotocol['modelReadySha256']==proof['modelReadySha256']
        for anchor in read(OLD/'automatic-enrollments.json'):assert sha(anchor['audio'])==anchor['audioSha256']
        atomic_json(C/'old-evaluation-vector-reuse.json',{'source':str(OLD/'native-enrollment-vectors.json'),'sourceSha256':sha(OLD/'native-enrollment-vectors.json'),'sameFrozenMatchedEncoderAndFeatureRule':True,'vectors':oldvectors['vectors'],'newEncoderCalls':0})
        adapter=MeetingActivityAdapter(pair.model).eval();max_error=0.;tested=0
        for case in read(OLD/'audio-only.json'):
            feature=next(r for r in feature_manifest if r['id']==case['id']);data=artifact_load(feature)
            for person in case['allAnonymousTargets']:
                embedding=torch.tensor(oldvectors['vectors'][case['meeting']+':'+str(person)],dtype=torch.float32,device=device)
                with torch.inference_mode():out=adapter.from_frozen_features(embedding,data['frames'],data['lengths'],feature['inputFeatureFrames']);prob=torch.softmax(out['chunk_logits'],dim=-1)[0,:,1][out['chunk_mask'][0]].cpu().numpy()
                original=np.asarray(read(OLD/'outputs'/(case['id']+'-speaker-'+str(person)+'.json'))['probabilities']);assert prob.shape==original.shape;error=float(np.max(np.abs(prob-original)));max_error=max(max_error,error);tested+=1;state['newNeuralCalls']+=1
        assert tested==67 and max_error<=P['cachedBaseProbabilityTolerance']
        atomic_json(C/'cached-base-parity.json',{'binding':binding,'state':'PASS_NATIVE_HEAD_FEATURE_REUSE_OLD67_PROBABILITIES','queries':tested,'maxAbsoluteProbabilityError':max_error,'tolerance':P['cachedBaseProbabilityTolerance'],'noTrainingBeforeParity':True})
        atomic_json(C/'feature-manifest.json',{'binding':binding,'items':feature_manifest,'vectorCount':len(vectors),'oldAutomaticVectorsReused':15,'originalAcousticBackboneFrozen':True})
        state.update(state='COMPLETE_FROZEN_FEATURES_AND_BASE_PARITY')
    elif args.stage=='probe':
        assert read(C/'cached-base-parity.json')['state']=='PASS_NATIVE_HEAD_FEATURE_REUSE_OLD67_PROBABILITIES';features=read(C/'feature-manifest.json');inputs=read(C/'training-inputs-only.json');labels=read(C/'training-labels.json');vectors=vectors_load()
        example=next(r for r in inputs if r['role']=='train');feature=next(r for r in features['items'] if r['id']==example['id']);data=artifact_load(feature);emb=torch.tensor(vectors[example['meeting']+':'+example['person']],dtype=torch.float32,device=device);adapter=MeetingActivityAdapter(pair.model).eval()
        with torch.no_grad():
            native=pair.model(emb,data['fbank'],data['lengths']);unwrapped=adapter(emb,data['fbank'],data['lengths']);cached=adapter.from_frozen_features(emb,data['frames'],data['lengths'],feature['inputFeatureFrames'])
        assert torch.equal(native['chunk_logits'],unwrapped['chunk_logits']) and torch.equal(native['chunk_logits'],cached['chunk_logits']) and torch.equal(native['chunk_mask'],cached['chunk_mask'])
        backbone_before=tensor_state_sha(pair.model.backbone);speaker_before=tensor_state_sha(pair._eres);head_before=tensor_state_sha(pair.model)
        adapter.train();optimizer=torch.optim.AdamW(adapter.trainable_parameters(),lr=P['learningRate'],weight_decay=P['weightDecay']);optimizer.zero_grad(set_to_none=True)
        truth=torch.tensor(next(r for r in labels if r['id']==example['id'])['activityLabels'],dtype=torch.long,device=device);out=adapter.from_frozen_features(emb,data['frames'],data['lengths'],feature['inputFeatureFrames']);mask=out['chunk_mask'][0];assert out['chunk_logits'][0,mask].shape[0]==len(truth)
        loss=torch.nn.functional.cross_entropy(out['chunk_logits'][0,mask],truth);assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_(adapter.trainable_parameters(),P['gradientClipNorm']);assert torch.isfinite(norm) and float(norm)>0
        gradients=[p.grad for p in adapter.trainable_parameters() if p.grad is not None];assert gradients and all(torch.isfinite(g).all() for g in gradients);assert all(p.grad is None for p in pair.model.backbone.parameters()) and all(p.grad is None for p in pair._eres.parameters())
        optimizer.step();assert tensor_state_sha(pair.model.backbone)==backbone_before and tensor_state_sha(pair._eres)==speaker_before and tensor_state_sha(pair.model)!=head_before
        state['newNeuralCalls']=4
        atomic_json(C/'gradient-proof.json',{'binding':binding,'state':'PASS_REAL_TRAINING_GRADIENT_FROZEN_BACKBONE_AND_EXACT_EVAL','example':example['id'],'sourceRole':'train','sourceIsIndependentFromOldDevelopmentMeetings':True,'nativeDecoratedUnwrappedAndCachedEvalLogitsExactlyEqual':True,'trainableParameters':sum(p.numel() for p in adapter.trainable_parameters()),'frozenBackboneParameters':sum(p.numel() for p in pair.model.backbone.parameters()),'finiteHeadGradientNormBeforeClipping':float(norm),'lossBeforeProbeStep':float(loss),'headValuesChanged':True,'backboneValuesAndBuffersUnchanged':True,'speakerEncoderUnchanged':True,'probeStepNotUsedAsTrainingInitialization':True,'cudaPeakAllocatedBytes':torch.cuda.max_memory_allocated(),'accuracyImprovementClaimed':False,'limits':limits.query()})
        state.update(state='COMPLETE_REAL_GRADIENT_AND_RESOURCE_PROBE',completedInputs=1)
    elif args.stage=='train':
        assert read(C/'gradient-proof.json')['state']=='PASS_REAL_TRAINING_GRADIENT_FROZEN_BACKBONE_AND_EXACT_EVAL'
        features={r['id']:r for r in read(C/'feature-manifest.json')['items']};inputs=read(C/'training-inputs-only.json');labels={r['id']:r for r in read(C/'training-labels.json')};vectors=vectors_load();adapter=MeetingActivityAdapter(pair.model);optimizer=torch.optim.AdamW(adapter.trainable_parameters(),lr=P['learningRate'],weight_decay=P['weightDecay']);folder=E/'checkpoints';folder.mkdir(exist_ok=True);resume=folder/'completed-epoch-resume.pt';history=[];start_epoch=0
        frozen_before=tensor_state_sha(pair.model.backbone)
        if resume.exists():
            packet=torch.load(resume,map_location='cpu',weights_only=True);assert packet['binding']==binding;adapter.load_head_state(packet['head']);optimizer.load_state_dict(packet['optimizer']);start_epoch=packet['epoch'];history=packet['history'];random.setstate(packet['pythonRandomState']);torch.set_rng_state(packet['torchCpuRandomState']);torch.cuda.set_rng_state(packet['torchGpuRandomState']);state['reusedOutputs']=start_epoch
        def forward(item):
            feature=features[item['id']];data=artifact_load(feature);embedding=torch.tensor(vectors[item['meeting']+':'+item['person']],dtype=torch.float32,device=device);truth=torch.tensor(labels[item['id']]['activityLabels'],dtype=torch.long,device=device);out=adapter.from_frozen_features(embedding,data['frames'],data['lengths'],feature['inputFeatureFrames']);logits=out['chunk_logits'][0,out['chunk_mask'][0]];state['newNeuralCalls']+=1;assert len(logits)==len(truth);return logits,truth
        def validate():
            adapter.eval();total=0.;frames=0
            with torch.no_grad():
                for item in [r for r in inputs if r['role']=='validation']:
                    logits,truth=forward(item);total+=float(torch.nn.functional.cross_entropy(logits,truth,reduction='sum'));frames+=len(truth)
            return total/frames
        before=validate();state['baselineSeparateRoomValidationLoss']=before;save('TRAINING_FIXED_SMALL_CONDITIONED_HEAD')
        if not history:history.append({'epoch':0,'validationLoss':before,'checkpoint':None})
        for epoch in range(start_epoch,P['epochs']):
            adapter.train();training=[r for r in inputs if r['role']=='train'];random.Random(P['seed']+epoch).shuffle(training);optimizer.zero_grad(set_to_none=True);epoch_loss=0.
            for i,item in enumerate(training):
                logits,truth=forward(item);loss=torch.nn.functional.cross_entropy(logits,truth);assert torch.isfinite(loss);(loss/P['gradientAccumulation']).backward();epoch_loss+=float(loss)
                if (i+1)%P['gradientAccumulation']==0 or i+1==len(training):
                    norm=torch.nn.utils.clip_grad_norm_(adapter.trainable_parameters(),P['gradientClipNorm']);assert torch.isfinite(norm);optimizer.step();optimizer.zero_grad(set_to_none=True);time.sleep(1)
                state['completedInputs']=epoch*len(training)+i+1;save('TRAINING_FIXED_SMALL_CONDITIONED_HEAD')
            assert tensor_state_sha(pair.model.backbone)==frozen_before
            val=validate();checkpoint=folder/('head-epoch-%02d.pt'%(epoch+1));assert not checkpoint.exists();torch.save(adapter.head_state_dict(),checkpoint)
            row={'epoch':epoch+1,'trainingLoss':epoch_loss/len(training),'validationLoss':val,'checkpoint':str(checkpoint),'checkpointSha256':sha(checkpoint)};history.append(row);atomic_json(C/'training-history.json',{'binding':binding,'epochs':history,'checkpointSelectionUsesOnlySeparateRoomValidationLoss':True,'old13ControlsNeverUsedForCheckpointSelection':True})
            temp=resume.with_suffix('.tmp');torch.save({'binding':binding,'head':adapter.head_state_dict(),'optimizer':optimizer.state_dict(),'epoch':epoch+1,'history':history,'pythonRandomState':random.getstate(),'torchCpuRandomState':torch.get_rng_state(),'torchGpuRandomState':torch.cuda.get_rng_state()},temp);os.replace(temp,resume);state['completedEpochs']=epoch+1;save('COMPLETED_DURABLE_TRAINING_EPOCH')
        best=min(history,key=lambda r:r['validationLoss']);assert best['checkpoint'] is not None,'No adapted checkpoint improves separate-room validation loss: retain base and stop adaptation evaluation'
        atomic_json(C/'best-checkpoint.json',{**best,'binding':binding,'baselineValidationLoss':history[0]['validationLoss'],'selectedOnlyBySeparateRoomLoss':True,'headOnly':True,'backboneUnchanged':True,'qualityQualified':False})
        state.update(state='COMPLETE_SMALL_HEAD_TRAINING_HELDOUT_ROOM_SELECTED',trainingEpochs=len(history)-1)
    else:
        best=read(C/'best-checkpoint.json');assert best['binding']==binding and sha(best['checkpoint'])==best['checkpointSha256'];adapter=MeetingActivityAdapter(pair.model).eval();adapter.load_head_state(torch.load(best['checkpoint'],map_location='cpu',weights_only=True));adapter.eval()
        features={r['id']:r for r in read(C/'feature-manifest.json')['items']};vectors=read(C/'old-evaluation-vector-reuse.json')['vectors'];outdir=C/'evaluation/outputs';outdir.mkdir(parents=True,exist_ok=True);outputs=[];evaluation_binding={'protocolSha256':sha(C/'evaluation/protocol.json'),'adaptationProtocolSha256':binding['protocolSha256'],'headSha256':best['checkpointSha256']}
        for case in read(OLD/'audio-only.json'):
            feature=features[case['id']];data=artifact_load(feature)
            for person in case['allAnonymousTargets']:
                key=case['id']+'-speaker-'+str(person);file=outdir/(key+'.json')
                if file.exists():result=read(file);assert result['binding']==evaluation_binding;state['reusedOutputs']+=1
                else:
                    embedding=torch.tensor(vectors[case['meeting']+':'+str(person)],dtype=torch.float32,device=device)
                    with torch.no_grad():out=adapter.from_frozen_features(embedding,data['frames'],data['lengths'],feature['inputFeatureFrames']);prob=torch.softmax(out['chunk_logits'],dim=-1)[0,:,1][out['chunk_mask'][0]].cpu().tolist()
                    anchor=next(a for a in read(OLD/'automatic-enrollments.json') if a['meeting']==case['meeting'] and a['speaker']==person)
                    result={'id':key,'binding':evaluation_binding,'meeting':case['meeting'],'speaker':person,'inputAudioSha256':case['audioSha256'],'enrollmentAudioSha256':anchor['audioSha256'],'inputSamples':case['endSample']-case['startSample'],'probabilities':prob,'adaptedHeadOnly':True,'frozenOriginalAudioProfilesThresholdAndGrid':True};atomic_json(file,result);state['newNeuralCalls']+=1
                outputs.append(str(file));state['completedInputs']=len(outputs);save('EVALUATING_ADAPTED_HEAD_ON_UNCHANGED_OLD_CONTROLS')
        assert len(outputs)==67;atomic_json(C/'evaluation/short-manifest.json',{'binding':evaluation_binding,'outputs':outputs,'queryCount':len(outputs),'allOriginalProbabilitiesRetained':True});state.update(state='COMPLETE_ADAPTER_SHORT_EVALUATION_REVIEW_REQUIRED')
except BaseException as error:state.update(state='FAILED_ADAPTATION_STAGE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(state,ensure_ascii=False),flush=True)
