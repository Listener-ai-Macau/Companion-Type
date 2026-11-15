"""Same original speaker model, read-only real cache and counterfactual audio."""
from pathlib import Path
from datetime import datetime
import argparse,importlib.util,json,os,tarfile,time,traceback
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_local_pcm_session_20261114 import atomic_json
from public_nemotron_adaptation_20261115 import read,sha,pin_rocm_blas,load_original
from contextual_speaker_binding_20261115 import raw_slice,feature_block,active_slots,blocks_for_mask,associate_case

def main():
    p=argparse.ArgumentParser()
    for key in ['control','run','inventory']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--phase',choices=['control','baseline'],required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    P=read(a.control/'protocol.json');binding=read(a.control/'worker-binding.json')
    assert sha(__file__)==binding['workerSha256'] and sha(a.control/'protocol.json')==binding['protocolSha256']
    for file,digest in binding['helpers'].items():assert sha(file)==digest
    state=dict(state='STARTING_CONTEXTUAL_SOURCE_QUERY',phase=a.phase,startedAt=datetime.now().astimezone().isoformat(),
        newEncoderCalls=0,newProjectionCalls=0,optimizerUpdates=0,referenceRead=False,qualityQualified=False,
        protocolSha256=binding['protocolSha256'])
    began=time.perf_counter()
    def save(**values):
        state.update(values,limits=limits.query(),observedAt=datetime.now().astimezone().isoformat());atomic_json(a.run/'state.json',state)
    def stop():
        if (a.run/'stop.request').exists():raise InterruptedError('Owned contextual query stopped; completed outputs retained')
    save()
    try:
        inv=read(a.inventory);assert inv['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
        assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inv['finishedAt'])).total_seconds()<1800
        import torch,numpy as np,yaml
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        assert torch.__version__=='2.11.0+rocm10.0.0' and torch.cuda.device_count()==1
        torch.cuda.set_device(0);gpu=torch.cuda.get_device_properties(0)
        assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        pin_rocm_blas(P['rocmBlasLibrary'],P['rocmBlasLibrarySha256'])
        model,activity,weights=load_original(P)
        spec=importlib.util.spec_from_file_location('binding_original_converter',P['converter'])
        up=importlib.util.module_from_spec(spec);spec.loader.exec_module(up)
        with tarfile.open(P['checkpoint']) as archive:config=yaml.safe_load(archive.extractfile('model_config.yaml').read())
        extractor=up.build_feature_extractor(config)
        assert config['preprocessor']['normalize']=='NA' and extractor.preemphasis==.97
        assert sha(a.control/'meetings-audio-only.json')==P['meetingInputSha256']
        assert sha(a.control/'cases-audio-only.json')==P['caseInputSha256']
        meetings=read(a.control/'meetings-audio-only.json');cases=read(a.control/'cases-audio-only.json')
        if a.phase=='baseline':
            proof=read(Path(P['controlRun'])/'state.json')
            assert proof['state']=='PASS_CONTEXTUAL_QUERY_ORIGINAL_FEATURE_EMBEDDING_AND_POSTERIOR_CONTROLS'
            assert proof['protocolSha256']==binding['protocolSha256']
        save(state='ORIGINAL_FROZEN_CONTEXT_QUERY_MODEL_LOADED',weights=weights,gpu=gpu.name)
        control_records=[];associations=[];query_results=[]
        for meeting in meetings:
            stop()
            for file,digest in [(meeting['audio'],meeting['audioSha256']),(meeting['features'],meeting['featuresSha256']),
                (meeting['probabilities'],meeting['probabilitiesSha256']),(meeting['legacyOverlap']['file'],meeting['legacyOverlap']['sha256']),
                (meeting['cacheRoutes'],meeting['cacheRoutesSha256'])]:assert sha(file)==digest
            features=np.load(meeting['features'],mmap_mode='r');probabilities=np.load(meeting['probabilities'],mmap_mode='r')
            legacy=np.load(meeting['legacyOverlap']['file'],allow_pickle=False);slots=active_slots(probabilities,np)
            assert np.array_equal(legacy,slots.sum(axis=1)>=2)
            routes=read(meeting['cacheRoutes'])['routes'];source_cases=[c for c in cases if c['meeting']==meeting['meeting']]
            queries=[c for c in source_cases if c['overlapRoute']]
            if a.phase=='control':queries=queries[:1]
            with torch.inference_mode():
                base_features=torch.from_numpy(np.array(features,copy=True))[None].to('cuda:0')
                original_embeds=model.model.audio_tower.embedder(base_features);state['newProjectionCalls']+=1
            checked_blocks=set();computed_cases={}
            def route_forward(row,embeds,*,check_original=False):
                stop();assert sha(row['file'])==row['sha256']
                cached=torch.from_numpy(np.load(row['file'],allow_pickle=False)).to('cuda:0')
                offset=row['offset'];cached_length=offset//8;assert offset%8==0
                first_embed=row['first']//8;last_embed=min(first_embed+340+40,embeds.shape[1])
                query=embeds[:,first_embed:last_embed]
                if check_original:assert torch.equal(query,cached[:,cached_length:]),'Original embedding query differs from real cache route'
                inputs=torch.cat([cached[:,:cached_length],query],dim=1);assert inputs.shape==cached.shape
                positions=torch.arange(inputs.shape[1],device='cuda:0')[None,:]
                with torch.inference_mode():
                    hidden=model.model(inputs_embeds=inputs,position_ids=positions).last_hidden_state
                    z=model.classifier(hidden);aux=activity(hidden)
                state['newEncoderCalls']+=1
                length=row['last']-row['first']
                z=z[0,offset:offset+length].cpu().numpy();aux=aux[0,offset:offset+length].cpu().numpy()
                result=torch.from_numpy(z).sigmoid().numpy()
                if check_original:assert np.array_equal(result,probabilities[row['first']:row['last']]),'Original cached posterior query differs'
                return result,aux
            for case in queries:
                stop();low,high=case['sourceStartFrame'],case['sourceEndFrame']
                assert sha(case['wav'])==case['wavSha256']
                whole,n=raw_slice(meeting['audio'],low,high,np);clip,clip_n=raw_slice(case['wav'],0,high-low,np)
                assert clip_n==high-low and np.array_equal(whole,clip),'Clip and original whole microphone differ'
                indices=np.arange(low,high,dtype=np.int64)//160;mask=legacy[indices]
                assert mask.any()
                blocks=blocks_for_mask(low,mask,len(features),np)
                for first,last in blocks:
                    if (first,last) in checked_blocks:continue
                    observed=feature_block(meeting['audio'],first,last,extractor,torch,np)
                    expected=np.array(features[first:last],copy=True)
                    assert np.array_equal(observed.numpy(),expected),'Original frontend patch differs from cached whole frontend'
                    checked_blocks.add((first,last));control_records.append(dict(meeting=meeting['meeting'],first=first,last=last,frontendMaximumDifference=0.))
                first_frame=low//160;last_frame=(high+159)//160
                needed=[row for row in routes if max(first_frame,row['first'])<min(last_frame,row['last']) and legacy[max(first_frame,row['first']):min(last_frame,row['last'])].any()]
                if a.phase=='control':
                    for row in needed:
                        route_forward(row,original_embeds,check_original=True)
                        control_records.append(dict(meeting=meeting['meeting'],routeFirst=row['first'],originalEmbeddingExact=True,originalPosteriorsExact=True))
                    continue
                sources=[]
                for stream in case['streams']:
                    assert sha(stream['file'])==stream['sha256'];samples=np.load(stream['file'],allow_pickle=False)
                    assert samples.shape==(high-low,) and samples.dtype==np.float32
                    with torch.inference_mode():counter_features=base_features.clone()
                    for first,last in blocks:
                        value=feature_block(meeting['audio'],first,last,extractor,torch,np,replacement=(low,high,mask,samples))
                        with torch.inference_mode():counter_features[:,first:last].copy_(value[None].to('cuda:0'))
                    with torch.inference_mode():counter_embeds=model.model.audio_tower.embedder(counter_features)
                    state['newProjectionCalls']+=1;del counter_features
                    out=np.zeros((last_frame-first_frame,8),np.float32);auxiliary=np.zeros((len(out),3),np.float32);computed=np.zeros(len(out),np.bool_)
                    for row in needed:
                        result,aux=route_forward(row,counter_embeds)
                        lo=max(first_frame,row['first']);hi=min(last_frame,row['last']);selected=legacy[lo:hi]
                        target=np.arange(lo,hi)-first_frame;source=np.arange(lo,hi)-row['first']
                        out[target[selected]]=result[source[selected]];auxiliary[target[selected]]=aux[source[selected]];computed[target[selected]]=True
                    assert np.array_equal(computed,legacy[first_frame:last_frame])
                    folder=a.run/'queries'/case['id'];folder.mkdir(parents=True,exist_ok=True);items={}
                    for name,array in [('probabilities',out),('activity',auxiliary),('computed',computed)]:
                        file=folder/('stream-'+str(stream['index'])+'-'+name+'.npy')
                        with file.open('wb') as f:np.save(f,array,allow_pickle=False);f.flush();os.fsync(f.fileno())
                        items[name]=dict(file=str(file),sha256=sha(file))
                    sources.append(dict(probabilities=out,activity=auxiliary,computed=computed))
                    query_results.append(dict(id=case['id'],stream=stream['index'],globalFirstFeatureFrame=first_frame,
                        outputs=items,sourceFloatSha256=stream['sha256'],readOnlyOriginalCache=True,referenceRead=False))
                    del counter_embeds;save(state='QUERYING_SEPARATED_AUDIO_WITH_ORIGINAL_SPEAKER_CONTEXT',completedQueryStreams=len(query_results))
                computed_cases[case['id']]=sources
            if a.phase=='baseline':
                for case in source_cases:
                    result=associate_case(case,slots,legacy,computed_cases.get(case['id']),np)
                    folder=a.run/'associations';folder.mkdir(exist_ok=True)
                    atomic_json(folder/(case['id']+'.json'),result);associations.append(result)
            del base_features,original_embeds,features,probabilities,legacy,slots
        if a.phase=='control':
            save(state='PASS_CONTEXTUAL_QUERY_ORIGINAL_FEATURE_EMBEDDING_AND_POSTERIOR_CONTROLS',controls=control_records,
                originalAudioPcmExact=True,originalFrontendExact=True,originalEmbeddingExact=True,originalPosteriorsExact=True)
        else:
            assert len(associations)==32
            resolved=sum(r['overlapResolvedFrames'] for r in associations);unconfirmed=sum(r['overlapUnconfirmedFrames'] for r in associations)
            atomic_json(a.run/'query-results.json',query_results)
            atomic_json(a.run/'associations.json',dict(cases=associations,sourceAudioOrWordsChanged=False,
                speakerIdentityVerified=False,wordSpeakerAlignmentImplemented=False,qualityQualified=False))
            save(state='COMPLETE_CONTEXTUAL_AUDIO_SPEAKER_ASSOCIATION_UNQUALIFIED',cases=32,queryStreams=len(query_results),
                overlapResolvedSeconds=resolved/16000,overlapUnconfirmedSeconds=unconfirmed/16000,
                speakerIdentityVerified=False,wordSpeakerAlignmentImplemented=False,queryResults=str(a.run/'query-results.json'))
    except BaseException as error:
        save(state='FAILED_CONTEXTUAL_SPEAKER_QUERY_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        save(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began)
        print(json.dumps({k:state.get(k) for k in ['state','newEncoderCalls','newProjectionCalls','error','seconds']},ensure_ascii=False))

if __name__=='__main__':main()
