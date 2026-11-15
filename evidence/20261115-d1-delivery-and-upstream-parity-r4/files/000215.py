"""Staged CPU port of the pinned sherpa recipe with bounded vote accumulation.

Neural results are durable before clustering. Avoid expanding every local
window into all global speakers (upstream ReLabel); accumulate byte votes
directly on the recording timeline. No participant count or reference input.
Based on k2-fsa/sherpa-onnx v1.13.4, Apache-2.0 (Xiaomi Corporation).
"""
from pathlib import Path
import argparse,hashlib,inspect,json,math,os,time,traceback,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from practical_io_20261107 import atomic_json

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def windows(n,window,shift):
    if n<=window:return [0]
    ans=list(range(0,n-window+1,shift))
    if ans[-1]+window<n:ans.append(ans[-1]+shift)
    return ans

def frame_start(index,meta):
    return int(float(np.float32(np.float32(index)*meta['window_shift'])/np.float32(meta['receptive_field_shift']))+.5)

def powerset_labels(logits):
    mapping=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,1,0],[1,0,1],[0,1,1]],dtype=np.uint8)
    assert logits.shape[-1]==7
    return mapping[np.argmax(logits,axis=-1)]

def speaker_intervals(labels,meta):
    """The exact published10-clean-frame filter and float32 sample offsets."""
    pairs=[];intervals=[];frames=labels.shape[1];window=meta['window_size']
    for index,label in enumerate(labels):
        clean=label.copy();clean[label.sum(axis=1)>=2]=0
        offset=index*meta['window_shift']
        for speaker in range(3):
            active=clean[:,speaker]
            if int(active.sum())<10:continue
            edges=np.diff(np.r_[0,active,0].astype(np.int8));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
            runs=[]
            for start,end in zip(starts,ends):
                if end==frames:end=frames-1
                sample=lambda frame:int(np.float32(np.float32(np.float32(frame)/np.float32(frames))*np.float32(window)+np.float32(offset)))
                runs.append([sample(start),sample(end)])
            pairs.append([index,speaker]);intervals.append(runs)
    return pairs,intervals

def audio_float(path):
    with wave.open(str(path),'rb') as source:
        assert source.getnchannels()==1 and source.getsampwidth()==2 and source.getframerate()==16000
        count=source.getnframes();audio=np.empty(count,dtype=np.float32)
        for start in range(0,count,65536):
            block=np.frombuffer(source.readframes(min(65536,count-start)),dtype='<i2');np.divide(block,32768.,out=audio[start:start+len(block)],casting='unsafe')
    return audio

def segment_one(session,audio,start,window,input_name):
    samples=np.zeros(window,dtype=np.float32);block=audio[start:start+window];samples[:len(block)]=block
    return session.run(None,{input_name:samples.reshape(1,1,window)})[0][0]

def extract_one(extractor,audio,runs):
    stream=extractor.create_stream()
    for start,end in runs:
        stop=min(end,len(audio))
        if stop>start:stream.accept_waveform(16000,audio[start:stop])
    stream.input_finished();assert extractor.is_ready(stream),'Published clean-frame admission produced no ready embedding'
    return np.asarray(extractor.compute(stream),dtype=np.float32)

def prefix_sha(array,done):
    return hashlib.sha256(memoryview(np.asarray(array[:done])).cast('B')).hexdigest()

def publish_cache(path,array,done,binding,extra):
    array.flush()
    with Path(array.filename).open('r+b') as stream:os.fsync(stream.fileno())
    atomic_json(path,{'binding':binding,'done':done,'shape':list(array.shape),'dtype':str(array.dtype),'committedPrefixSha256':prefix_sha(array,done),**extra})

def checked_cache(path,binding):
    value=json.loads(path.read_text(encoding='utf8'));assert value['binding']==binding,'Neural cache belongs to another input/model/recipe'
    array=np.load(path.with_suffix('.npy'),mmap_mode='r+',allow_pickle=False)
    assert list(array.shape)==value['shape'] and str(array.dtype)==value['dtype'] and prefix_sha(array,value['done'])==value['committedPrefixSha256'],'Durable neural prefix changed'
    return array,value

def cluster_vectors(vectors,threshold):
    from scipy.cluster.hierarchy import linkage,fcluster
    values=vectors.astype(np.float32,copy=True);norm=np.sqrt(np.sum(values*values,axis=1,dtype=np.float32));assert np.isfinite(norm).all() and (norm>0).all();values/=norm[:,None]
    if len(values)==1:return np.zeros(1,dtype=np.int32)
    # Same normalized cosine dissimilarity / complete linkage / threshold.
    # FP32 reduction/tie order differs from Eigen; native30s comparison is
    # required. Never advertise this port as byte-identical unseen speech.
    distance=np.empty(len(values)*(len(values)-1)//2,dtype=np.float64);offset=0
    for i in range(len(values)-1):
        block=np.einsum('ij,j->i',values[i+1:],values[i],dtype=np.float32)
        n=len(block);distance[offset:offset+n]=np.maximum(0.,1.-block.astype(np.float64));offset+=n
    # cutree_cdist stops at height >= threshold (strictly below), and names
    # clusters in first-observation order. Numeric IDs matter at vote ties.
    result=fcluster(linkage(distance,method='complete'),np.nextafter(float(threshold),-np.inf),criterion='distance')
    order={value:i for i,value in enumerate(dict.fromkeys(result.tolist()))}
    return np.asarray([order[value] for value in result],dtype=np.int32)

def bounded_votes(labels,pairs,clusters,meta,num_samples):
    """OR within a local window, then sum across windows; no dense ReLabel."""
    full_frames=(meta['window_size']+(len(labels)-1)*meta['window_shift'])//meta['receptive_field_shift']+1
    groups=int(clusters.max())+1;assert math.ceil(meta['window_size']/meta['window_shift'])+1<256
    counts=np.zeros((full_frames,groups),dtype=np.uint8)
    weights=np.zeros(full_frames,dtype=np.float32);local_count=np.zeros(full_frames,dtype=np.float32)
    mapping={tuple(pair):int(group) for pair,group in zip(pairs,clusters)}
    for i,label in enumerate(labels):
        start=frame_start(i,meta);end=start+len(label);assert end<=full_frames
        weights[start:end]+=1;local_count[start:end]+=label.sum(axis=1,dtype=np.uint8)
        merged={}
        for speaker in range(3):
            group=mapping.get((i,speaker))
            if group is None:continue
            if group in merged:merged[group]|=label[:,speaker]
            else:merged[group]=label[:,speaker].copy()
        for group,mask in merged.items():counts[start:end,group]+=mask
    assert counts.max()<=math.ceil(meta['window_size']/meta['window_shift'])+1
    expected=(local_count/(weights+np.float32(1e-12))+np.float32(.5)).astype(np.int32)
    keep=full_frames
    if (num_samples-meta['window_size'])%meta['window_shift']>0:keep=min(num_samples//meta['receptive_field_shift']+1,full_frames)
    return counts[:keep],expected[:keep],{'expandedWindowMatricesAllocated':False,'voteDtype':'uint8','voteBytes':counts.nbytes,'avoidedDenseRelabelBytes':len(labels)*labels.shape[1]*groups*4,'globalSpeakerClusters':groups,'voteUpperBound':math.ceil(meta['window_size']/meta['window_shift'])+1}

def vote_segments(counts,expected,meta,min_on,min_off):
    # A frame has <=2 local active people. Stable lowest-ID tie breaking is
    # explicit; no guessed reference speaker count or forced group cap.
    final=np.zeros(counts.shape,dtype=np.uint8)
    for start in range(0,len(counts),2048):
        end=min(len(counts),start+2048);tile=counts[start:end].astype(np.int16)
        for rank in range(int(expected[start:end].max(initial=0))):
            indices=np.argmax(tile,axis=1);admit=np.flatnonzero(expected[start:end]>rank)
            final[start+admit,indices[admit]]=1;tile[np.arange(len(tile)),indices]=-1
    scale=np.float32(meta['receptive_field_shift']/meta['sample_rate']);offset=np.float32(.5*meta['receptive_field_size']/meta['sample_rate'])
    time_at=lambda index:float(np.float32(np.float32(index)*scale+offset))
    rows=[]
    for speaker in range(final.shape[1]):
        edge=np.diff(np.r_[0,final[:,speaker],0].astype(np.int8));starts=np.flatnonzero(edge==1);ends=np.flatnonzero(edge==-1);merged=[]
        for start,end in zip(starts,ends):
            if end==len(final):end-=1
            a,b=time_at(start),time_at(end)
            if merged and np.float32(a-merged[-1][1])<np.float32(min_off):merged[-1][1]=b
            else:merged.append([a,b])
        rows.extend({'start':a,'end':b,'speaker':speaker} for a,b in merged if np.float32(b-a)>np.float32(min_on))
    return sorted(rows,key=lambda row:(row['start'],row['end'],row['speaker']))

def main():
    from moss_windows_resource_limits_20261104 import WorkerLimits
    p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--index',required=True,type=int);p.add_argument('--stage',choices=['segment','embed','reconstruct'],required=True);args=p.parse_args()
    C=Path(args.control);read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));P=read(C/'protocol.json');case=read(C/'audio-only.json')[args.index]
    assert not any('reference' in key.lower() for key in case)
    limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    cache=Path(P['boundedCacheRoot'])/case['meeting'];cache.mkdir(parents=True,exist_ok=True);out=C/'results'/case['meeting'];out.mkdir(parents=True,exist_ok=True)
    target=out/(args.stage+'-state.json');tick=time.perf_counter();state={'state':'STARTING','stage':args.stage,'pid':os.getpid(),'audioSha256':case['audioSha256'],'referenceRead':False,'gpuUsed':False,'sourceSha256':sha(__file__),'newNeuralItems':0}
    def progress(**fields):
        state.update(fields);state['limits']=limits.query()
        if not atomic_json(target,state,progress=True):state['progressWriteDeferrals']=state.get('progressWriteDeferrals',0)+1
        if (C/'stop.request').exists():raise InterruptedError('Explicit stop')
    try:
        assert sha(case['audio'])==case['audioSha256']
        for key in ['segmentation','embedding']:assert sha(P[key]['model'])==P[key]['sha256']
        binding={'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'segmentationSha256':P['segmentation']['sha256'],'embeddingSha256':P['embedding']['sha256'],'recipe':'published-v1.13.4-10s-step1s-clean10frames-full-timeline-v1'}
        if args.stage=='segment':
            import onnxruntime as ort
            options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
            session=ort.InferenceSession(P['segmentation']['model'],sess_options=options,providers=['CPUExecutionProvider']);assert session.get_providers()==['CPUExecutionProvider']
            meta={k:int(v) for k,v in session.get_modelmeta().custom_metadata_map.items() if k in ['sample_rate','window_size','receptive_field_shift','receptive_field_size','num_speakers','num_classes','powerset_max_classes']};meta['window_shift']=int(.1*meta['window_size'])
            assert meta['sample_rate']==16000 and meta['num_speakers']==3 and meta['num_classes']==7 and meta['powerset_max_classes']==2
            audio=audio_float(case['audio']);assert abs(len(audio)/16000-case['audioSeconds'])<1/16000
            starts=windows(len(audio),meta['window_size'],meta['window_shift']);name=session.get_inputs()[0].name
            assert len(starts)>1,'This long-meeting port requires more than one author window; short audio keeps the existing native path'
            binding.update(runtime=ort.__version__,neuralFunctionSha256=hashlib.sha256(inspect.getsource(segment_one).encode()).hexdigest())
            manifest=cache/'segment.json'
            if manifest.exists():array,info=checked_cache(manifest,binding);done=info['done'];assert info['meta']==meta
            else:
                value=segment_one(session,audio,starts[0],meta['window_size'],name);assert value.dtype==np.float32
                array=np.lib.format.open_memmap(cache/'segment.npy',mode='w+',dtype=np.float32,shape=(len(starts),*value.shape));array[0]=value;done=1;state['newNeuralItems']=1
                publish_cache(manifest,array,done,binding,{'meta':meta,'total':len(starts),'state':'COMPLETE_SEGMENTATION_CACHE' if done==len(starts) else 'PARTIAL_SEGMENTATION_CACHE'})
            state['reusedCachedPrefix']=done-state['newNeuralItems']
            for index in range(done,len(starts)):
                value=segment_one(session,audio,starts[index],meta['window_size'],name);assert np.isfinite(value).all();array[index]=value
                state['newNeuralItems']+=1
                if (index+1)%32==0 or index+1==len(starts):
                    publish_cache(manifest,array,index+1,binding,{'meta':meta,'total':len(starts),'state':'COMPLETE_SEGMENTATION_CACHE' if index+1==len(starts) else 'PARTIAL_SEGMENTATION_CACHE'});progress(state='SEGMENTING',completed=index+1,total=len(starts))
            state.update(state='COMPLETE_SEGMENTATION_CACHE',completed=len(starts),total=len(starts),manifest=str(manifest),manifestSha256=sha(manifest))
        elif args.stage=='embed':
            import sherpa_onnx
            seg=read(cache/'segment.json');assert seg['state']=='COMPLETE_SEGMENTATION_CACHE' and all(seg['binding'][k]==v for k,v in binding.items())
            logits,checked=checked_cache(cache/'segment.json',seg['binding']);labels=powerset_labels(logits);meta=seg['meta'];pairs,runs=speaker_intervals(labels,meta);assert pairs
            audio=audio_float(case['audio']);config=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=P['embedding']['model'],num_threads=1,provider='cpu');assert config.validate();extractor=sherpa_onnx.SpeakerEmbeddingExtractor(config)
            binding.update(runtime=sherpa_onnx.__version__,segmentationManifestSha256=sha(cache/'segment.json'),pairsSha256=hashlib.sha256(json.dumps([pairs,runs],separators=(',',':')).encode()).hexdigest(),neuralFunctionSha256=hashlib.sha256((inspect.getsource(extract_one)+inspect.getsource(speaker_intervals)).encode()).hexdigest())
            manifest=cache/'embed.json'
            if manifest.exists():array,info=checked_cache(manifest,binding);done=info['done']
            else:
                value=extract_one(extractor,audio,runs[0]);array=np.lib.format.open_memmap(cache/'embed.npy',mode='w+',dtype=np.float32,shape=(len(pairs),len(value)));array[0]=value;done=1;state['newNeuralItems']=1
                publish_cache(manifest,array,done,binding,{'total':len(pairs),'state':'COMPLETE_EMBEDDING_CACHE' if done==len(pairs) else 'PARTIAL_EMBEDDING_CACHE'})
            state['reusedCachedPrefix']=done-state['newNeuralItems']
            for index in range(done,len(pairs)):
                array[index]=extract_one(extractor,audio,runs[index])
                state['newNeuralItems']+=1
                if (index+1)%16==0 or index+1==len(pairs):
                    publish_cache(manifest,array,index+1,binding,{'total':len(pairs),'state':'COMPLETE_EMBEDDING_CACHE' if index+1==len(pairs) else 'PARTIAL_EMBEDDING_CACHE'});progress(state='EMBEDDING',completed=index+1,total=len(pairs))
            atomic_json(cache/'pairs.json',{'pairs':pairs,'runs':runs,'pairsSha256':binding['pairsSha256']});state.update(state='COMPLETE_EMBEDDING_CACHE',completed=len(pairs),total=len(pairs),manifest=str(manifest),manifestSha256=sha(manifest))
        else:
            seg=read(cache/'segment.json');emb=read(cache/'embed.json');assert seg['state']=='COMPLETE_SEGMENTATION_CACHE' and emb['state']=='COMPLETE_EMBEDDING_CACHE'
            assert all(seg['binding'][k]==v and emb['binding'][k]==v for k,v in binding.items())
            logits,_=checked_cache(cache/'segment.json',seg['binding']);embeddings,_=checked_cache(cache/'embed.json',emb['binding']);assert emb['binding']['segmentationManifestSha256']==sha(cache/'segment.json')
            labels=powerset_labels(logits);pairs,runs=speaker_intervals(labels,seg['meta']);assert hashlib.sha256(json.dumps([pairs,runs],separators=(',',':')).encode()).hexdigest()==emb['binding']['pairsSha256']
            valid=~np.isnan(embeddings).any(axis=1);assert valid.any() and np.isfinite(embeddings[valid]).all()
            clusters=cluster_vectors(embeddings[valid],P['clustering']['threshold']);selected=[pair for pair,keep in zip(pairs,valid) if keep]
            atomic_json(out/'cluster-summary.json',{'candidatePairs':len(pairs),'validEmbeddings':int(valid.sum()),'predictedClusters':int(clusters.max())+1,'threshold':P['clustering']['threshold'],'participantCountProvided':False})
            counts,expected,receipt=bounded_votes(labels,selected,clusters,seg['meta'],round(case['audioSeconds']*16000));progress(state='RECONSTRUCTING',memoryLayout=receipt)
            rows=vote_segments(counts,expected,seg['meta'],P['minDurationOn'],P['minDurationOff']);assert rows and all(0<=r['start']<r['end']<=case['audioSeconds']+.1 for r in rows)
            atomic_json(out/'speaker-journal.json',{'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'segments':rows,'scope':'Bounded CPU port, numerical/native short control only. Anonymous model activity; no ASR/real names/roles or qualified overlap word recovery.'})
            rttm=out/'predicted.rttm';rttm.write_text(''.join(f"SPEAKER {case['meeting']} 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> speaker_{r['speaker']} <NA> <NA>\n" for r in rows),encoding='utf8')
            state.update(state='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED',meeting=case['meeting'],audioSeconds=case['audioSeconds'],predictedSpeakers=len({r['speaker'] for r in rows}),segments=len(rows),rttmSha256=sha(rttm),memoryLayout=receipt)
    except BaseException as error:
        state.update(state='FAILED_RETAINED_NEURAL_CACHE_RESUMABLE',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        from datetime import datetime
        state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state)
        if args.stage=='reconstruct':atomic_json(out/'completed-state.json',state)
        print(json.dumps(state,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
