"""One official native Transformers ASR control. No refs, export, or training."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',HF_ENABLE_PARALLEL_LOADING='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--inventory-only',action='store_true');a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);tick=time.perf_counter()
target=C/('hip-inventory.json' if a.inventory_only else 'short-native-state.json');assert not target.exists()
state={'startedAt':now(),'state':'IMPORTING_EXISTING_NATIVE_TORCH','pid':os.getpid(),'sourceSha256':sha(__file__),'referenceOpened':False,'trainingPerformed':False,'modelLoaded':False,'results':[]}
def save():
    state['limits']=limits.query();atomic_json(target,state)
save()
try:
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.version.hip,'Require the pre-existing native AMD runtime; no DirectML/iGPU fallback'
    inventory=[{'ordinal':i,'name':torch.cuda.get_device_properties(i).name,'architecture':torch.cuda.get_device_properties(i).gcnArchName,'totalMemory':torch.cuda.get_device_properties(i).total_memory} for i in range(torch.cuda.device_count())]
    state.update(torchVersion=torch.__version__,devices=inventory)
    matches=[d for d in inventory if 'RX 6800 XT' in d['name'] and d['architecture'].startswith('gfx1030')]
    assert len(matches)==1,'Need one currently attached external RX6800XT; refuse unknown device'
    if a.inventory_only:
        state.update(state='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL',selected=matches[0])
    else:
        assert len(inventory)==1 and matches[0]['ordinal']==0,'Launcher must expose only freshly identified dedicated GPU'
        device='cuda:0';torch.cuda.set_device(0);P=read(C/'protocol.json')
        assert P['featureDevice']=='selected_gpu' and P['textPostprocessing']=='direct_tokenizer_skip_special_tokens_only_no_cleanup_no_repetition_fix'
        assert read(P['supportedGpuFeatureNumericProof'])['state']=='PASS_SUPPORTED_GPU_FEATURES_INDEPENDENT_NUMPY_REFERENCE'
        loader_proof=read(P['streamedLoaderControl'])
        assert loader_proof['state']=='PASS_STANDARD_AND_STREAMED_TINY_QWEN_EXACT_LOGITS_AND_GENERATION'
        assert loader_proof['weightRoundtrip']['loaderSourceSha256']==sha(Path(__file__).with_name('practical_qwen_streamed_loader_20261107.py'))
        assert P['backend']=='official_native_transformers' and P['prompt'] is None and P['dtype']=='bfloat16' and P['attnImplementation']=='eager' and P['maxNewTokens']==512 and not P['doSample']
        for file in P['files']:assert sha(file['file'])==file['sha256']
        import transformers
        from transformers import AutoProcessor,AutoModelForMultimodalLM
        assert transformers.__version__=='5.22.1'
        state.update(state='LOADING_OFFICIAL_NATIVE_QWEN_ASR',transformersVersion=transformers.__version__,modelRevision=P['revision'],selectedGpu=matches[0]);save()
        started=time.perf_counter();processor=AutoProcessor.from_pretrained(P['modelRoot'],local_files_only=True)
        from practical_qwen_streamed_loader_20261107 import load_model
        weight=next(file for file in P['files'] if Path(file['file']).name=='model.safetensors')
        model,weight_receipt=load_model(P['modelRoot'],torch=torch,device=device,expected_sha256=weight['sha256'])
        atomic_json(C/'short-weight-roundtrip.json',weight_receipt)
        state.update(modelLoaded=True,modelLoadSeconds=time.perf_counter()-started,state='RUNNING_FROZEN_NATIVE_SHORT_CASES');save()
        from transformers import StoppingCriteria,StoppingCriteriaList
        class StopOnlyThisTask(StoppingCriteria):
            def __call__(self,input_ids,scores,**kwargs):
                if (C/'stop.request').exists():raise InterruptedError('Explicit stop; original audio/raw output retained')
                return False
        import numpy as np
        from practical_qwen_input_20261107 import is_exact_digital_silence
        assert P['digitalSilencePolicy']=='skip_only_exact_zero_no_threshold_no_nonzero_cut'
        assert sha(Path(__file__).with_name('practical_qwen_input_20261107.py'))==P['digitalSilenceGuardSourceSha256']
        for case in read(C/'short-audio-only.json'):
            assert not any('reference' in k.lower() for k in case)
            assert sha(case['audio'])==case['audioSha256']
            with wave.open(case['audio'],'rb') as f:
                assert f.getframerate()==16000 and f.getsampwidth()==2 and f.getnchannels()==1
                samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
            assert len(samples)/16000==case['audioSeconds']
            if is_exact_digital_silence(samples):
                result={'case':case['id'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'inputTokenCount':0,'generatedIds':[],'naturalEos':None,'loops20OrMore':[],'text':'','rawDecoded':'','inferenceSeconds':0.,'sourceAudioUnchanged':True,'exactDigitalSilence':True,'neuralInferencePerformed':False,'scope':'Every original PCM sample is exactly0; no energy threshold or text cleanup; not a bare-model silence pass.'}
                atomic_json(C/(case['id']+'-output.json'),result);state['results'].append(result);save();continue
            inputs=processor.apply_transcription_request(audio=samples,language='Chinese',processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':device}}).to(device,model.dtype)
            input_length=inputs['input_ids'].shape[1];torch.cuda.synchronize();started=time.perf_counter()
            with torch.inference_mode():ids=model.generate(**inputs,max_new_tokens=512,do_sample=False,stopping_criteria=StoppingCriteriaList([StopOnlyThisTask()]))
            torch.cuda.synchronize();seconds=time.perf_counter()-started;generated=ids[0,input_length:].cpu().tolist()
            eos=model.generation_config.eos_token_id;eos_ids=[eos] if isinstance(eos,int) else eos
            natural_eos=bool(generated and generated[-1] in eos_ids)
            # The high-level parsed decoder silently collapses repeats. Keep
            # every generated word; failed decoding must remain measurable.
            text=processor.tokenizer.decode(generated,skip_special_tokens=True,clean_up_tokenization_spaces=False)
            raw=processor.decode(generated,skip_special_tokens=False)
            loops=[]
            for size in range(1,9):
                for offset in range(len(generated)-20*size+1):
                    block=generated[offset:offset+size]
                    if generated[offset:offset+size*20]==block*20:loops.append({'offset':offset,'blockTokens':size});break
            result={'case':case['id'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'inputTokenCount':input_length,'generatedIds':generated,'naturalEos':natural_eos,'loops20OrMore':loops,'text':text,'rawDecoded':raw,'inferenceSeconds':seconds,'sourceAudioUnchanged':sha(case['audio'])==case['audioSha256'],'qualityQualified':False}
            previous=read(P['speechControlBeforeGuard']);assert case['audioSha256']==previous['audioSha256'] and generated==previous['generatedIds'] and text==previous['text'],'Nonzero speech must remain identical after an exact-zero-only input guard'
            atomic_json(C/(case['id']+'-output.json'),result);state['results'].append(result);save()
            assert natural_eos and not loops,'Short execution control failed; preserve raw IDs, do not remove repeats or launch whole meetings'
            if case['id']!='synthetic-silence3s':assert text.strip(),'No text for original public speech control'
            else:assert not text.strip(),'Synthetic silence hallucinated words; full-meeting adoption gate stays closed'
            time.sleep(1.)
        state.update(state='PASS_OFFICIAL_NATIVE_SHORT_EXECUTION_FULL_QUALITY_UNMEASURED')
except BaseException as error:
    state.update(state='FAILED_OFFICIAL_NATIVE_CONTROL_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-tick);save();print(json.dumps(state,ensure_ascii=False),flush=True)
