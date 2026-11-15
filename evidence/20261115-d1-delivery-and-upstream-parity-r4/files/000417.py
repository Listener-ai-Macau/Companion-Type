"""One reference-free audio input, original processor only, no model weights."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,json,sys,traceback,time
from moss_windows_resource_limits_20261104 import WorkerLimits
from moss_prepared_inputs_20261106 import publish,file_sha

parser=argparse.ArgumentParser();parser.add_argument('--protocol',required=True);parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
protocol=json.loads(Path(args.protocol).read_text(encoding='utf8'));cases=json.loads(Path(args.inputs).read_text(encoding='utf8'));assert len(cases)==1;case=cases[0]
assert not any('reference' in k.lower() for k in case)
control=Path(args.protocol).parent
assert not (control/'stop.request').exists()
limits=WorkerLimits(cpu_percent=protocol['runtime']['workerCpuHardCapPercent'],memory_bytes=protocol['runtime']['systemPrivateMemoryBudgetBytes'])
state={'state':'IMPORTING_PROCESSOR_ONLY','startedAt':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'modelLoaded':False,'audioSha256':case['audioSha256'],'resourceLimits':limits.receipt}
def save():
    p=control/'input-preparation-state.tmp';p.write_text(json.dumps(state,indent=2),encoding='utf8');p.replace(control/'input-preparation-state.json')
save();start=time.perf_counter()
try:
    import numpy as np,torch,transformers,random
    assert torch.__version__==protocol['runtime']['torch'] and transformers.__version__==protocol['runtime']['transformers']
    torch.set_num_threads(2);torch.set_num_interop_threads(1);random.seed(0);np.random.seed(0);torch.manual_seed(0)
    from moss_gpu_identity_20261106 import enumerate_native_gpus,select_rx6800xt
    selected=select_rx6800xt(enumerate_native_gpus(torch),protocol['runtime'].get('gpuIndex'))
    torch.cuda.set_device(selected['index']);device=torch.device('cuda',selected['index'])
    assert file_sha(case['audio'])==case['audioSha256']
    assets=Path('E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104')
    sys.path.insert(0,str(assets/'official-source'))
    from moss_transcribe_diarize import MossTranscribeDiarizeProcessor,MossTranscribeDiarizeConfig,inference_utils
    from moss_pcm16_ram_20261104 import install_pcm16_loader
    for record in json.loads((assets/'prepare-state.json').read_text(encoding='utf8'))['files']:
        path=assets/('model' if record['source']=='hf' else 'official-source')/record['file'];assert file_sha(path)==record['sha256']
    state['pcm16RamLoader']=install_pcm16_loader(inference_utils)
    # Match the already validated model worker exactly. Passing its explicit
    # author config avoids AutoTokenizer's incompatible AutoConfig reparse.
    config=MossTranscribeDiarizeConfig.from_pretrained(assets/'model',local_files_only=True)
    processor=MossTranscribeDiarizeProcessor.from_pretrained(assets/'model',config=config,local_files_only=True)
    assert not getattr(processor.feature_extractor,'dither',0),'Do not stage stochastic preprocessing without matching original RNG position'
    state.update(state='PREPARING_COMPLETE_AUDIO_WITHOUT_MODEL',actualGpu=selected['name'],gpuIdentitySelection=selected);save()
    messages=inference_utils.build_transcription_messages(case['audio'])
    # Exact original function and batch shape; no feature/encoder microbatch change.
    prepared=inference_utils.prepare_inputs(processor,messages,max_length=protocol['runtime']['maxLength'],device=device).to(device)
    torch.cuda.synchronize(device)
    state.update(state='WRITING_EXACT_AUTHOR_INPUTS',inputTokens=int(prepared['attention_mask'][0].sum().item()),inputFeatureShape=list(prepared['input_features'].shape));save()
    path,manifest=publish(prepared,directory=args.output,case=case,protocol=protocol,torch=torch)
    state.update(state='COMPLETE_AUTHOR_INPUT_PREPARATION_NO_MODEL_LOADED',manifest=str(path),manifestSha256=file_sha(path),tensorFileSha256=manifest['tensorFileSha256'],roundtripAllTensorsBitwiseIdentical=True,seconds=time.perf_counter()-start);save()
except BaseException as error:
    state.update(state='INPUT_PREPARATION_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());save();raise
print(json.dumps(state),flush=True)
