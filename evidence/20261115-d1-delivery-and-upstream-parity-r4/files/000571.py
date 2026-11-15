"""Test the frozen original encoder on all disjoint known-speaker components."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import argparse,json,os,time,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read,sha,load_models,load_pair
from companion_tse_source_data_20261108 import pcm_read
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();C=Path(args.control);P=read(args.protocol);out=C/args.run_id;out.mkdir(exist_ok=False);assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();state={'state':'LOADING_FROZEN_ORIGINAL_SPEAKER_ENCODER','pid':os.getpid(),'newWeightUpdates':0,'completedInputs':0,'qualityQualified':False};save=lambda:atomic_json(out/'state.json',{**state,'limits':limits.query()},progress=True);save()
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);assert torch.version.hip and torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0);base,_,_=load_models(P,out,torch=torch,with_teacher=False);base.eval();assert base.joint_training and not base.spk_feat and base.feat_type=='consistent';profiles=read(C/'profiles.json');components=read(C/'components.json')
    assert isinstance(base.spk_transform,torch.nn.Identity),'Frozen transform must be identical in original and adapted trials'
    def embedding(wave):
        x=base.preEmphasis(wave);x=base.spk_encoder(x)+1e-8;x=x.log();x=x-torch.mean(x,dim=-1,keepdim=True);x=x.permute(0,2,1);x=base.spk_model(x);x=x[-1] if isinstance(x,tuple) else x;return base.spk_transform(x)
    def waveform(packet):
        assert sha(packet['audio'])==packet['audioSha256'];value=pcm_read(packet['audio'],packet['channels'])[:,0].astype(np.float32)/32768;peak=float(np.max(np.abs(value)));assert peak>0;return torch.from_numpy(value/peak).unsqueeze(0).cuda()
    first=components[0];profile=next(p for p in profiles if p['id']==first['profileId']);pair,enroll,_=load_pair({'audio':first['audio'],'audioSha256':first['audioSha256'],'profileAudio':profile['audio'],'profileAudioSha256':profile['audioSha256']},torch=torch,device='cuda:0');captured=[];hook=base.spk_transform.register_forward_hook(lambda module,inputs,output:captured.append(output.detach().clone()))
    with torch.inference_mode():base(pair[:,0],enroll)
    hook.remove()
    with torch.inference_mode():assert len(captured)==1 and torch.equal(captured[0],embedding(enroll))
    vectors=[]
    with torch.inference_mode():
        for packet in profiles:vector=embedding(waveform(packet));assert torch.isfinite(vector).all();vectors.append(vector[0]);state['completedInputs']+=1;state['state']='ENCODING_FIXED_PROFILES';save()
        enrolled=torch.nn.functional.normalize(torch.stack(vectors),dim=-1);rows=[]
        for packet in components:
            vector=embedding(waveform(packet));scores=(torch.nn.functional.normalize(vector,dim=-1)@enrolled.T)[0];indices=[i for i,p in enumerate(profiles) if p['meeting']==packet['meeting']];own=next(i for i in indices if profiles[i]['id']==packet['profileId']);best=max(indices,key=lambda i:float(scores[i]));other=max(float(scores[i]) for i in indices if i!=own);rows.append({'componentId':packet['id'],'meeting':packet['meeting'],'personForEvaluationOnly':packet['personForTrainingOrScoringOnly'],'correctProfileId':packet['profileId'],'predictedProfileId':profiles[best]['id'],'correct':best==own,'ownCosine':float(scores[own]),'maximumOtherCosine':other,'ownMinusBestOtherMargin':float(scores[own])-other,'seconds':packet['audioSeconds']});state['completedInputs']+=1;state['state']='MATCHING_DISJOINT_COMPONENT_VOICES';save()
    per_meeting={m:{'components':len(g),'correct':sum(x['correct'] for x in g),'top1Accuracy':sum(x['correct'] for x in g)/len(g),'meanOwnMinusOtherMargin':sum(x['ownMinusBestOtherMargin'] for x in g)/len(g)} for m in sorted({x['meeting'] for x in rows}) if (g:=[x for x in rows if x['meeting']==m])};result={'state':'COMPLETE_FROZEN_SPEAKER_ENCODER_DISJOINT_SOURCE_DIAGNOSTIC','actualAuthorForwardHookMatchedBitExactly':True,'profileCount':len(profiles),'componentCount':len(rows),'correctComponents':sum(x['correct'] for x in rows),'top1Accuracy':sum(x['correct'] for x in rows)/len(rows),'perMeeting':per_meeting,'perComponent':rows,'metric':'Choose nearest of known profiles within the same source meeting, on independent pure-annotated utterances. Not automatic diarization DER, natural overlap identity accuracy, or pretraining-independent generalization.','encoderWeightsFrozenAndSameAsBothTrialConditions':True,'newWeightUpdates':0,'qualityQualified':False};atomic_json(C/'speaker-encoder-diagnostic.json',result);state.update(state=result['state'],diagnostic=result)
except BaseException as error:state.update(state='FROZEN_SPEAKER_ENCODER_DIAGNOSTIC_FAILED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps({k:v for k,v in state.items() if k!='diagnostic'}),flush=True)
