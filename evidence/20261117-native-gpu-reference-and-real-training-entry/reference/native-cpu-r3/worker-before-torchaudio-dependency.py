"""One native BF16 English reference using standard Accelerate disk offload."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, copy, ctypes, gc, hashlib, json, os, re, struct, sys, threading, time, traceback, wave
os.environ.update(OMP_NUM_THREADS='4', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                  HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
import psutil
from moss_windows_resource_limits_20261104 import WorkerLimits, CpuRate, SystemRamPressure
from durable_model_state_20261117 import atomic_json
from companion_local_pcm_session_20261114 import exclusive_file

parser = argparse.ArgumentParser()
parser.add_argument('--protocol', type=Path, required=True)
a = parser.parse_args()
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
P = read(a.protocol)
out = Path(P['run'])
out.mkdir(exist_ok=False)
limits = WorkerLimits(cpu_percent=5, memory_bytes=P['privateLimitBytes'])
rate = CpuRate(5, 2500)
limits._check(limits.kernel.SetInformationJobObject(limits.job, 15, ctypes.byref(rate), ctypes.sizeof(rate)))
pressure = SystemRamPressure()
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
start = time.monotonic()
closing = threading.Event()
mutex = threading.RLock()
state = {'state': 'PREPARING_ONE_NATIVE_GRANITE_REFERENCE', 'startedAt': now(), 'pid': os.getpid(),
         'createdAt': psutil.Process().create_time(), 'completed': [], 'newNeuralCalls': 0,
         'newTrainingUpdates': 0, 'referenceRead': False, 'qualityQualified': False, 'saleQualified': False}

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(**values):
    with mutex:
        state.update(values, observedAt=now(), elapsedSeconds=time.monotonic()-start, limits=limits.query())
        atomic_json(out/'state.json', state, progress=True)

def stop_reason():
    if (out/'stop.request').exists(): return 'Owned stop request'
    if time.monotonic()-start > P['maximumSeconds']: return 'Bounded reference deadline'
    if pressure.low() or psutil.virtual_memory().available < P['minimumAvailableBytes']: return 'Original realRAM floor'
    if psutil.Process().memory_info().private > P['privateLimitBytes']: return 'Original private-memory budget'
    return None

def check():
    why = stop_reason()
    if why: raise InterruptedError(why)

def watch():
    while not closing.wait(.5):
        why = stop_reason()
        if why:
            atomic_json(out/'stop-observed.json', {'at': now(), 'reason': why, 'state': state, 'limits': limits.query()})
            # This process/job belongs only to this task. No other program is touched.
            os._exit(76)
        if int(time.monotonic()-start) % 5 == 0: save()

try:
    with exclusive_file(Path(P['neuralLock'])):
        save(protocolSha256=sha(a.protocol))
        assert sha(__file__) == P['workerSha256']
        for item in P['files']: assert sha(item['file']) == item['sha256'], item['file']
        assert len(P['cases']) == 12 and all(set(c) == {'id','audio','audioSha256','pcmSha256','frames'} for c in P['cases'])
        for c in P['cases']:
            assert c['id'].startswith(('ES2003b-', 'EN2001a-')) and sha(c['audio']) == c['audioSha256']
        assert read(P['assets'])['state'] == 'COMPLETE_PINNED_GRANITE_REFERENCE_ASSETS_NO_MODEL_EXECUTION'
        threading.Thread(target=watch, daemon=True).start()
        admit = time.monotonic()
        while time.monotonic()-admit < 60: check(); time.sleep(1)
        import numpy as np
        import torch
        from accelerate import init_empty_weights, disk_offload
        from accelerate.utils import set_module_tensor_to_device
        from transformers import AutoConfig, AutoProcessor, GraniteSpeechForConditionalGeneration, StoppingCriteria, StoppingCriteriaList
        from transformers.conversion_mapping import get_checkpoint_conversion_mapping
        from transformers.core_model_loading import WeightRenaming, rename_source_key
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        assert not torch.cuda.is_initialized()
        save(state='VERIFYING_STANDARD_DISK_OFFLOAD_AND_NATIVE_METADATA', torch=torch.__version__)
        torch.manual_seed(20261117)
        tiny = torch.nn.Sequential(torch.nn.Linear(8,16), torch.nn.GELU(), torch.nn.Linear(16,8)).to(dtype=torch.bfloat16).eval().requires_grad_(False)
        tiny_disk = copy.deepcopy(tiny)
        x = torch.randn(2,8,dtype=torch.bfloat16)
        with torch.inference_mode(): expected = tiny(x)
        disk_offload(tiny_disk, out/'tiny-offload', execution_device=torch.device('cpu'))
        with torch.inference_mode(): actual = tiny_disk(x)
        assert torch.equal(expected, actual), 'Standard disk-offload changed BF16 calculation'
        atomic_json(out/'offload-control.json', {'state': 'PASS_IDENTICAL_BF16_TINY_STANDARD_DISK_OFFLOAD',
                    'maxAbsDifference': float((actual-expected).abs().max()), 'trainingUpdates': 0,
                    'doesNotProveFullModelQuality': True})
        del tiny, tiny_disk, x, expected, actual
        gc.collect()
        config = AutoConfig.from_pretrained(P['modelRoot'], local_files_only=True, trust_remote_code=False)
        assert config.model_type == 'granite_speech' and not config.has_lora_adapter
        config._attn_implementation = 'eager'
        config.text_config._attn_implementation = 'eager'
        old_dtype = torch.get_default_dtype()
        try:
            torch.set_default_dtype(torch.bfloat16)
            with init_empty_weights(include_buffers=False): model = GraniteSpeechForConditionalGeneration(config)
        finally:
            torch.set_default_dtype(old_dtype)
        model.eval().requires_grad_(False)
        assert all(v.is_meta and v.dtype == torch.bfloat16 for v in model.parameters())
        meta = model.state_dict()
        transforms = get_checkpoint_conversion_mapping('granite_speech')
        assert len(transforms) == 4 and all(isinstance(t, WeightRenaming) for t in transforms)
        source_index = read(Path(P['modelRoot'])/'model.safetensors.index.json')
        tensors = {}
        for shard in sorted(set(source_index['weight_map'].values())):
            path = Path(P['modelRoot'])/shard
            with path.open('rb') as f:
                header_len = struct.unpack('<Q', f.read(8))[0]
                assert header_len < 4*1024**2
                header = json.loads(f.read(header_len))
            for key, item in header.items():
                if key == '__metadata__': continue
                target, converter = rename_source_key(key, transforms, [])
                assert converter is None and target not in tensors and target in meta, target
                assert re.fullmatch(r'[a-zA-Z0-9_.]+', target)
                assert list(meta[target].shape) == item['shape']
                assert source_index['weight_map'][key] == shard
                tensors[target] = {'sourceName': key, 'shard': str(path), 'headerBytes': header_len+8, **item}
        assert set(tensors) == set(meta), {'missing': sorted(set(meta)-set(tensors))[:8]}
        assert sum(v['data_offsets'][1]-v['data_offsets'][0] for v in tensors.values()) == source_index['metadata']['total_size']
        atomic_json(out/'native-state-contract.json', {'state': 'PASS_ALL_NATIVE_KEYS_SHAPES_AND_OFFICIAL_RENAMINGS',
                    'keys': len(tensors), 'parameterCount': sum(p.numel() for p in model.parameters()),
                    'rawTensorBytes': source_index['metadata']['total_size'],
                    'conversion': [{'sources': t.source_patterns, 'targets': t.target_patterns} for t in transforms],
                    'publishedWeightsChanged': False, 'trainingUpdates': 0})
        # Standard Accelerate .dat files avoid mapping a whole safetensors shard
        # copy-on-write on Windows. Copy bounded raw bytes; no numeric conversion.
        disk = out/'published-bf16-offload'
        disk.mkdir()
        disk_index, receipts = {}, []
        for i, (name,item) in enumerate(tensors.items()):
            check()
            size = item['data_offsets'][1]-item['data_offsets'][0]
            assert item['dtype'] in ['BF16','I64']
            dtype = 'bfloat16' if item['dtype'] == 'BF16' else 'int64'
            dst = disk/(name+'.dat')
            digest = hashlib.sha256()
            with Path(item['shard']).open('rb') as src, dst.open('xb') as f:
                src.seek(item['headerBytes']+item['data_offsets'][0])
                remaining = size
                while remaining:
                    chunk = src.read(min(1024**2, remaining))
                    assert chunk
                    f.write(chunk); digest.update(chunk); remaining -= len(chunk)
                    check()
            disk_index[name] = {'dtype': dtype, 'shape': item['shape']}
            receipts.append({'name': name, 'bytes': size, 'sha256': digest.hexdigest()})
            if name in dict(model.named_buffers()):
                assert size <= 1024**2
                raw = np.fromfile(dst, dtype=np.uint16 if item['dtype']=='BF16' else np.int64)
                value = torch.from_numpy(raw)
                if item['dtype']=='BF16': value = value.view(torch.bfloat16)
                value = value.reshape(item['shape'])
                set_module_tensor_to_device(model, name, 'cpu', value=value)
            if i % 40 == 0: save(state='PREPARING_STANDARD_OFFLOAD_FILES', tensorsPrepared=i+1, tensorCount=len(tensors))
        atomic_json(disk/'index.json', disk_index)
        atomic_json(out/'offload-byte-binding.json', {'state': 'COMPLETE_RAW_PUBLISHED_TENSOR_COPY_NO_DTYPE_CHANGE', 'tensors': receipts})
        del meta, tensors
        gc.collect()
        disk_offload(model, disk, execution_device=torch.device('cpu'), offload_buffers=False)
        processor = AutoProcessor.from_pretrained(P['modelRoot'], local_files_only=True, trust_remote_code=False)
        prompt = processor.tokenizer.apply_chat_template([{'role':'user','content':P['prompt']}], tokenize=False, add_generation_prompt=True)
        hooks = []
        last_check = [0.0]
        def hook(module, args):
            if time.monotonic()-last_check[0] >= .25: check(); last_check[0] = time.monotonic()
        for module in model.modules(): hooks.append(module.register_forward_pre_hook(hook))
        for c in P['cases']:
            check()
            with wave.open(c['audio'],'rb') as w:
                assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1,2,16000,c['frames'])
                pcm = w.readframes(w.getnframes())
            assert hashlib.sha256(pcm).hexdigest() == c['pcmSha256']
            samples = np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
            inputs = processor(prompt, samples, device='cpu', return_tensors='pt')
            assert inputs['input_features'].device.type == 'cpu'
            began = time.perf_counter()
            save(state='DECODING_ONE_NATIVE_GRANITE_ENGLISH_REFERENCE', activeCase=c['id'], inputFrames=c['frames'],
                 featureShape=list(inputs['input_features'].shape), promptTokens=inputs['input_ids'].shape[-1])
            class BoundedStop(StoppingCriteria):
                def __call__(self, input_ids, scores, **kwargs):
                    check()
                    if time.perf_counter()-began > P['maximumCaseSeconds']: raise InterruptedError('Bounded per-case reference deadline')
                    return False
            with torch.inference_mode():
                output = model.generate(**inputs, do_sample=False, num_beams=1, max_new_tokens=P['maxNewTokens'],
                                        use_cache=True, disable_compile=True,
                                        stopping_criteria=StoppingCriteriaList([BoundedStop()]))
            generated = output[0, inputs['input_ids'].shape[-1]:].cpu().tolist()
            eos = model.generation_config.eos_token_id
            eos = [eos] if isinstance(eos,int) else eos or []
            natural = bool(generated and generated[-1] in eos)
            text = processor.tokenizer.decode(generated, skip_special_tokens=True)
            packet = {'id': c['id'], 'text': text, 'generatedIds': generated, 'naturalTermination': natural,
                      'seconds': time.perf_counter()-began, 'audioSha256': c['audioSha256'], 'pcmSha256': c['pcmSha256'],
                      'frames': c['frames'], 'protocolSha256': sha(a.protocol), 'referenceUsed': False,
                      'wordsPostEdited': False, 'trainingUpdates': 0, 'actualDevice': 'cpu', 'actualDtype': 'published bfloat16',
                      'standardAccelerateDiskOffload': True, 'qualityQualified': False}
            path = out/(c['id']+'.json')
            atomic_json(path, packet)
            state['newNeuralCalls'] += 1
            state['completed'].append({'id': c['id'], 'file': str(path), 'sha256': sha(path)})
            save()
            assert natural and text.strip(), 'Incomplete native generation; no changed-parameter retry'
            del inputs, output, samples, pcm
            gc.collect()
        assert not torch.cuda.is_initialized()
        save(state='COMPLETE_NATIVE_GRANITE_12_CLIPS_PENDING_INDEPENDENT_SCORE', activeCase=None, gpuInitialized=False)
        atomic_json(out/'completed.json', state)
        print(json.dumps({'state': state['state'], 'clips': len(state['completed']), 'seconds': time.monotonic()-start,
                          'privatePeakBytes': limits.query()['jobPeakPrivateCommitBytes']}), flush=True)
except BaseException as error:
    save(state='FAILED_NATIVE_GRANITE_REFERENCE_RETAINED_NO_AUTOMATIC_RETRY', error=repr(error), traceback=traceback.format_exc())
    atomic_json(out/'completed.json', state)
    raise
finally:
    closing.set()
    pressure.close()
