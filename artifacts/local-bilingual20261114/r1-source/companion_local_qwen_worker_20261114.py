"""Resident native AMD decoder for the local PCM session boundary.

Uses the already pinned1.7B checkpoint, loader and bounded recovery. Language
selection is explicit per session; auto decoding keeps raw words and token IDs.
This is an incremental window adapter, not a claimed vLLM streaming port.
"""
from pathlib import Path
import argparse, hashlib, json, os, time
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                  HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from companion_local_pcm_session_20261114 import PcmSession, atomic_json, digest, exclusive_file, parse_generated_tokens, read_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_qwen_bounded_decode_20261107 import accepted, recover, repeated_block

def sha(path):
    with Path(path).open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()

class NativeDecoder:
    def __init__(self,protocol,inventory,session,run):
        self.protocol_path=Path(protocol);self.N=read_json(protocol);self.run=Path(run);self.session=session
        selected=read_json(inventory)['selected'];self.N['selectedGpu']=selected
        self.language=session.state()['config']['language']
        self.torch=self.processor=self.model=None
        self.base_binding={'workerSourceSha256':sha(__file__),'sessionParserSourceSha256':sha(Path(__file__).with_name('companion_local_pcm_session_20261114.py')),
                           'nativeProtocolSha256':sha(protocol),'weightsSha256':next(x['sha256'] for x in self.N['files'] if Path(x['file']).name=='model.safetensors'),
                           'languagePolicy':self.language,'generation':{'maxNewTokens':512,'doSample':False},
                           'inference':'pinned-native-transformers-incremental-window-adapter'}
        self.state={'state':'WAITING_LOCAL_AUDIO','modelLoaded':False,'neuralCalls':0,'completedJobs':0,
                    'freshInferenceSeconds':0.,'binding':self.base_binding,'localOnly':True,'qualityQualified':False}
        self.save()

    def save(self):atomic_json(self.run/'worker-state.json',self.state)

    def load(self):
        if self.model is not None:return
        if (self.run/'stop.request').exists():raise InterruptedError('Owned stop before model loading')
        N=self.N
        assert N['dtype']=='bfloat16' and N['attnImplementation']=='eager' and N['maxNewTokens']==512 and N['doSample'] is False
        assert read_json(N['supportedGpuFeatureNumericProof'])['state']=='PASS_SUPPORTED_GPU_FEATURES_INDEPENDENT_NUMPY_REFERENCE'
        proof=read_json(N['streamedLoaderControl'])
        assert proof['state']=='PASS_STANDARD_AND_STREAMED_TINY_QWEN_EXACT_LOGITS_AND_GENERATION'
        assert proof['weightRoundtrip']['loaderSourceSha256']==sha(Path(__file__).with_name('practical_qwen_streamed_loader_20261107.py'))
        for item in N['files']:
            assert Path(item['file']).stat().st_size==item['bytes']
            if Path(item['file']).name!='model.safetensors':assert sha(item['file'])==item['sha256']
        self.state['state']='LOADING_PINNED_NATIVE_LOCAL_MODEL';self.save();began=time.perf_counter()
        import torch
        import transformers
        from transformers import AutoProcessor
        assert transformers.__version__=='5.22.1' and torch.version.hip and torch.cuda.device_count()==1
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        gpu=torch.cuda.get_device_properties(0)
        assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
        torch.cuda.set_device(0)
        from practical_qwen_streamed_loader_20261107 import load_model
        weight=next(x for x in N['files'] if Path(x['file']).name=='model.safetensors')
        self.processor=AutoProcessor.from_pretrained(N['modelRoot'],local_files_only=True)
        self.model,receipt=load_model(N['modelRoot'],torch=torch,device='cuda:0',expected_sha256=weight['sha256'])
        self.torch=torch
        atomic_json(self.run/'weight-roundtrip.json',receipt)
        self.state.update(modelLoaded=True,modelLoadSeconds=time.perf_counter()-began,gpu=gpu.name,
                          transformersVersion=transformers.__version__,torchVersion=torch.__version__)
        self.save()

    def transcribe(self,job):
        pcm=self.session.read_request_pcm(job)
        nodes=self.session.root/'decode'/job['jobId'];nodes.mkdir(parents=True,exist_ok=True)
        binding={**self.base_binding,'jobId':job['jobId'],'pcmSha256':job['pcmSha256'],'configSha256':job['configSha256']}
        def infer(lo,hi):
            part=pcm[(lo-job['startFrame'])*2:(hi-job['startFrame'])*2]
            if part==b'\0'*len(part):
                return {'startSample':lo,'endSample':hi,'text':'','generatedIds':[],'rawDecoded':'','naturalEos':None,
                        'language':None,'exactDigitalSilence':True,'neuralInferencePerformed':False,'inferenceSeconds':0.}
            self.load()
            import numpy as np
            from transformers import StoppingCriteria,StoppingCriteriaList
            samples=np.frombuffer(part,dtype='<i2').astype(np.float32)/32768
            options={'audio':samples,'processor_kwargs':{'audio_kwargs':{'sampling_rate':16000,'device':'cuda:0'}}}
            if self.language!='auto':options['language']=self.language
            inputs=self.processor.apply_transcription_request(**options).to('cuda:0',self.model.dtype)
            length=inputs['input_ids'].shape[1];run=self.run
            class StopOwnedDecode(StoppingCriteria):
                def __call__(self,input_ids,scores,**kwargs):
                    if (run/'stop.request').exists():raise InterruptedError('Owned stop; source and completed raw nodes retained')
                    return repeated_block(input_ids[0,length:].tolist(),suffix_only=True) is not None
            self.torch.cuda.synchronize();began=time.perf_counter()
            with self.torch.inference_mode():
                ids=self.model.generate(**inputs,max_new_tokens=512,do_sample=False,
                      stopping_criteria=StoppingCriteriaList([StopOwnedDecode()]))
            self.torch.cuda.synchronize();elapsed=time.perf_counter()-began
            generated=ids[0,length:].cpu().tolist()
            parsed=parse_generated_tokens(generated,self.processor.tokenizer,language=self.language)
            eos=self.model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
            raw={'startSample':lo,'endSample':hi,'text':parsed['text'],'language':parsed['language'],
                 'languageHeaderPresent':parsed['languageHeaderPresent'],'generatedIds':generated,
                 'rawDecoded':self.processor.tokenizer.decode(generated,skip_special_tokens=False,clean_up_tokenization_spaces=False),
                 'naturalEos':bool(generated and generated[-1] in eos),'repeatBlock':repeated_block(generated),
                 'neuralInferencePerformed':True,'inferenceSeconds':elapsed}
            self.state['neuralCalls']+=1;self.state['freshInferenceSeconds']+=elapsed;self.save()
            time.sleep(self.N['cooperativePauseSeconds'])
            return raw
        def load(key):
            path=nodes/(key+'.json')
            if not path.exists():return None
            packet=read_json(path)
            assert packet['binding']==binding and digest(json.dumps(packet['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())==packet['rawSha256']
            return packet['raw']
        def save(key,raw):
            atomic_json(nodes/(key+'.json'),{'binding':binding,'raw':raw,
              'rawSha256':digest(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())})
        self.state.update(state='RUNNING_LOCAL_PCM_REQUEST',activeJob=job['jobId']);self.save();began=time.perf_counter()
        leaves=recover(job['startFrame'],job['endFrame'],infer=infer,load=load,save=save)
        assert all(accepted(row['raw']) for row in leaves)
        result={'text':'\n'.join(row['raw']['text'] for row in leaves),
                'rawGeneratedIds':[row['raw']['generatedIds'] for row in leaves],
                'language':','.join(dict.fromkeys(row['raw'].get('language') for row in leaves if row['raw'].get('language'))),
                'accepted':True,'seconds':time.perf_counter()-began,
                'acceptedLeafInferenceSeconds':sum(row['raw']['inferenceSeconds'] for row in leaves),
                'allKnownDecodeSecondsIncludingFailedParents':sum(read_json(p)['raw']['inferenceSeconds'] for p in nodes.glob('*.json')),
                'leaves':[{'node':row['key'],'startFrame':row['raw']['startSample'],'endFrame':row['raw']['endSample']} for row in leaves],
                'referenceUsed':False,'sourcePcmUnchanged':True,'wordsPostEdited':False,'qualityQualified':False}
        self.session.save_result(job,result,inference_binding=self.base_binding)
        self.state['completedJobs']+=1;self.state.pop('activeJob',None);self.state['state']='WAITING_LOCAL_AUDIO';self.save()
        return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--session',required=True,type=Path)
    parser.add_argument('--protocol',required=True,type=Path);parser.add_argument('--inventory',required=True,type=Path)
    parser.add_argument('--run',required=True,type=Path);parser.add_argument('--follow-seconds',type=float,default=0)
    args=parser.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    session=PcmSession(args.session);session.reconcile()
    with exclusive_file(session.root/'inference.lock'):
        decoder=NativeDecoder(args.protocol,args.inventory,session,args.run);deadline=time.monotonic()+args.follow_seconds
        try:
            while True:
                if (args.run/'stop.request').exists():raise InterruptedError('Owned stop requested')
                jobs=session.pending()
                if jobs:
                    job=jobs[0];decoder.transcribe(job)
                    document=session.document();atomic_json(session.root/'document.json',document)
                    with (args.run/'events.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps({'jobId':job['jobId'],'operation':'replace-block',
                             'block':job['block'],'blockFinal':job['blockFinal'],'recordingFinal':document['isFinal'],
                             'eventAtUnix':time.time(),'text':next(r['text'] for r in document['utterances'] if r['block']==job['block'])},ensure_ascii=False)+'\n')
                    continue
                document=session.document();atomic_json(session.root/'document.json',document)
                if document['isFinal'] or time.monotonic()>=deadline:break
                time.sleep(.25)
            decoder.state['state']='LOCAL_RECORDING_DECODE_COMPLETE_UNQUALIFIED' if document['isFinal'] else 'LOCAL_DECODER_IDLE_SOURCE_OR_EOS_PENDING'
        except BaseException as error:
            decoder.state.update(state='LOCAL_DECODER_STOPPED_RAW_RETAINED',errorType=type(error).__name__,error=str(error));raise
        finally:
            decoder.state['limits']=limits.query();decoder.save()
        print(json.dumps({'state':decoder.state['state'],'neuralCalls':decoder.state['neuralCalls'],
                          'completedJobs':decoder.state['completedJobs'],'recordingFinal':document['isFinal']},ensure_ascii=False))

if __name__=='__main__':main()
