"""Same frozen speaker model: single enrollment vs fixed disjoint reference mean."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import argparse,json,os,time,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read,sha,load_models,load_pair,tensor_hash
from companion_tse_source_data_20261108 import pcm_read
from companion_tse_reference_bank_20261108 import SpeakerReferenceBank,make_reference_embedding_extractor
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();C=Path(args.control);B=C/'reference-bank-r1';P=read(args.protocol);out=C/args.run_id;out.mkdir(exist_ok=False);assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();state={'state':'LOADING_ORIGINAL_FROZEN_REFERENCE_BANK_ENCODER','pid':os.getpid(),'completedInputs':0,'newWeightUpdates':0,'qualityQualified':False};save=lambda:atomic_json(out/'state.json',{**state,'limits':limits.query()},progress=True);save()
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);assert torch.version.hip and torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0);base,_,_=load_models(P,out,torch=torch,with_teacher=False);base.eval();before=tensor_hash(base.named_parameters());plan=read(B/'reference-plan.json');profiles=read(C/'profiles.json');components=read(C/'components.json');bank=SpeakerReferenceBank(base,torch=torch);vectors={};original={};cache=[]
    def waveform(packet):
        assert sha(packet['audio'])==packet['audioSha256'];v=pcm_read(packet['audio'],packet['channels'])[:,0].astype(np.float32)/32768;peak=float(np.max(np.abs(v)));assert peak>0;return torch.from_numpy(v/peak).unsqueeze(0).cuda()
    for ref in plan['references']:
        segment=ref['id']+'--reference-'+str(ref['referenceOrdinal']);value=bank.add(ref['id'],segment,waveform(ref));cache.append({'kind':'reference','id':segment,'profileId':ref['id'],'audioSha256':ref['audioSha256'],'vector':value[0].cpu().tolist()})
        if ref['referenceOrdinal']==0:original[ref['id']]=value
        state['completedInputs']+=1;state['state']='ENCODING_ALL_FIXED_REFERENCES';save()
    first=components[0];profile=next(x for x in profiles if x['id']==first['profileId']);pair,enroll,_=load_pair({'audio':first['audio'],'audioSha256':first['audioSha256'],'profileAudio':profile['audio'],'profileAudioSha256':profile['audioSha256']},torch=torch,device='cuda:0')
    with torch.inference_mode():expected=base(pair[:,0],enroll)[0].detach().clone()
    cached=original[profile['id']];extractor=make_reference_embedding_extractor(base,torch=torch).cuda()
    with torch.inference_mode():actual=extractor(pair,cached)
    assert torch.equal(actual,expected),'Single-reference cached-vector interface changed original output';state['singleReferenceCachedInferenceBitIdentical']=True;state['state']='MATCHING_ALL223_COMPONENTS_BOTH_REFERENCE_RULES';save()
    ids=[p['id'] for p in profiles];single=torch.cat([original[x] for x in ids]);multiple=torch.cat([bank.prototype(x) for x in ids]);single=torch.nn.functional.normalize(single,dim=-1);multiple=torch.nn.functional.normalize(multiple,dim=-1);rows=[]
    # Reuse the exact frozen encoder. The extractor's direct-vector mode does
    # not affect bank.add(), which calls the unchanged speaker path directly.
    for component in components:
        segment='query--'+component['id'];value=bank.add('__DIAGNOSTIC_QUERY_ONLY__',segment,waveform(component));cache.append({'kind':'query','id':component['id'],'profileId':component['profileId'],'audioSha256':component['audioSha256'],'vector':value[0].cpu().tolist()});v=torch.nn.functional.normalize(value,dim=-1);indices=[i for i,p in enumerate(profiles) if p['meeting']==component['meeting']];own=ids.index(component['profileId']);conditions={}
        for name,reference in [('single',single),('multiple',multiple)]:
            scores=(v@reference.T)[0];best=max(indices,key=lambda i:float(scores[i]));other=max(float(scores[i]) for i in indices if i!=own);conditions[name]={'predictedProfileId':ids[best],'correct':best==own,'ownCosine':float(scores[own]),'ownMinusOtherMargin':float(scores[own])-other}
        rows.append({'componentId':component['id'],'meeting':component['meeting'],'personForEvaluationOnly':component['personForTrainingOrScoringOnly'],'conditions':conditions});state['completedInputs']+=1;save()
    assert tensor_hash(base.named_parameters())==before;old=read(C/'speaker-encoder-diagnostic.json');assert sum(r['conditions']['single']['correct'] for r in rows)==old['correctComponents']
    def aggregate(group):return {arm:{'examples':len(group),'correct':sum(r['conditions'][arm]['correct'] for r in group),'top1Accuracy':sum(r['conditions'][arm]['correct'] for r in group)/len(group)} for arm in ['single','multiple']}
    per_meeting={m:aggregate([r for r in rows if r['meeting']==m]) for m in sorted({r['meeting'] for r in rows})};per_person={p:aggregate([r for r in rows if r['meeting']+'--'+r['personForEvaluationOnly']==p]) for p in ids};totals=aggregate(rows);nonregress=all(v['multiple']['correct']>=v['single']['correct'] for v in per_meeting.values());gain=totals['multiple']['correct']>totals['single']['correct'];result={'state':'MULTI_REFERENCE_KNOWN_PROFILE_GAIN_REQUIRES_WORD_AND_UNSEEN_MEETING_VALIDATION' if gain and nonregress else 'MULTI_REFERENCE_NOT_RETAINED_KNOWN_PROFILE_REGRESSION','totals':totals,'perMeeting':per_meeting,'perPerson':per_person,'perComponent':rows,'referenceCountDistribution':plan['countDistribution'],'references':len(plan['references']),'fixedRawEmbeddingMeanNoWeightsTuned':True,'singleReferenceCachedInferenceBitIdentical':True,'allOriginalModelParameterBytesUnchanged':True,'everyMeetingNonregression':nonregress,'retainedForNextValidationOnly':gain and nonregress,'scope':'Known identity references from annotation, all query audio excluded. Same four previously observed source sessions; no claim of unseen meeting, automatic diarization or word accuracy.','newWeightUpdates':0,'qualityQualified':False,'saleQualified':False};atomic_json(B/'embedding-vectors.json',{'modelReadySha256':P['extractorReadySha256'],'vectors':cache,'voiceReferencesFromPublicDatasetOnly':True});atomic_json(B/'review.json',result);state.update(state='COMPLETE_MULTI_REFERENCE_DIAGNOSTIC',resultState=result['state'])
except BaseException as error:state.update(state='MULTI_REFERENCE_DIAGNOSTIC_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps(state),flush=True)
