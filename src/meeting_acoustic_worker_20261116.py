"""One fixed GPU-only native acoustic+bridge meeting adaptation pilot.

audit: tokenizer/PCM/header/label checks only, imports no torch.
preflight: actual dedicated-GPU forward/backward/update/checkpoint proof.
train: one fresh fixed epoch, admitted only by the matching GPU preflight.
No validation references, CPU/iGPU training, automatic retries or deployment.
"""
from pathlib import Path
from datetime import datetime
import argparse
import gc
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import wave
from contextlib import contextmanager

os.environ.update(OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='4',
                  HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
from meeting_acoustic_contract_20261116 import (
    PREFIXES, TRAINABLE_PARAMETERS, balanced_order, committed_checkpoint,
    padded_labels, read, require, select_gpu, sha, tensor_header,
    training_rows, verify_bindings, write_float_checkpoint,
)
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure, CpuRate

now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')


def own_limits(cpu_percent):
    """Reuse the already validated owner25% override, leaving shared defaults."""
    require(cpu_percent in (5,25),'Unsupported worker CPU budget')
    limits = WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    if cpu_percent == 25:
        import ctypes
        rate = CpuRate(5,2500)
        limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
    applied = limits.query()
    require(applied['cpuRate'] == cpu_percent*100 and applied['jobPrivateCommitLimitBytes'] == 2*1024**3,
            'Owner CPU/private-memory guard was not applied')
    return limits


@contextmanager
def exclusive_run(run):
    import msvcrt
    with (run/'worker.lock').open('a+b') as stream:
        if stream.seek(0,2) == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        try:
            yield
        finally:
            stream.seek(0); msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)


def inspect_inputs(packet, rows):
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(Path(packet['modelRoot'])/'tokenizer.json'))
    eos = tokenizer.token_to_id('<|im_end|>')
    require(eos == 151645, 'Unexpected target EOS')
    targets, counts = {}, {}
    for row in rows:
        ids = tokenizer.encode(row['text'], add_special_tokens=False).ids+[eos]
        require(1 < len(ids) <= 512, 'Target would be truncated: '+row['id'])
        targets[row['id']] = ids
        with wave.open(row['audio'], 'rb') as stream:
            require((stream.getnchannels(),stream.getframerate(),stream.getsampwidth()) == (1,16000,2), 'Unexpected PCM format')
            require(stream.getnframes() == row['endFrame']-row['startFrame'], 'Incomplete training audio')
        counts[row['language']] = counts.get(row['language'],0)+1
    order = balanced_order(rows,packet['training']['seed'])
    report = {'state':'PASS_OFFLINE_FROZEN_INPUT_TOKENIZER_AND_MASK_CONTRACT',
              'at':now(), 'examples':len(rows), 'languages':counts,
              'targetTokens':sum(map(len,targets.values())),
              'maxTargetTokens':max(map(len,targets.values())),
              'orderSha256':hashlib.sha256(json.dumps(order).encode()).hexdigest(),
              'torchImported': 'torch' in sys.modules, 'modelLoaded':False,
              'newNeuralCalls':0, 'parameterUpdates':0,
              'actualGpuPreflightPassed':False, 'trainingStarted':False}
    require(not report['torchImported'], 'Offline audit imported a neural runtime')
    return targets,report


def available_ram():
    import ctypes
    class Status(ctypes.Structure):
        _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
                    ['totalPhysical','availablePhysical','totalPage','availablePage','totalVirtual','availableVirtual','extended']]
    status = Status(); status.length = ctypes.sizeof(status)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)), 'RAM query failed')
    return status.availablePhysical


def present_discrete_gpu():
    command = "Get-PnpDevice -Class Display -PresentOnly | Select-Object FriendlyName,Status | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
                            capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    require(result.returncode == 0, 'Cannot establish currently present display devices')
    devices = json.loads(result.stdout)
    devices = devices if isinstance(devices,list) else [devices]
    require(any('RX 6800 XT' in d.get('FriendlyName','') and d.get('Status') == 'OK' for d in devices),
            'RX6800XT is not currently present/ready; stop before importing torch')
    return devices


def gpu_run(packet, rows, targets, run, mode, resume, binding, limits):
    pressure = SystemRamPressure()
    state = {'state':'WAITING_FOR_ACTUAL_GPU_AND_STABLE_RAM', 'at':now(),
             'mode':mode, 'pid':os.getpid(), 'binding':binding, 'optimizerUpdates':0,
             'completedExamples':0, 'newNeuralCalls':0, 'qualityQualified':False,
             'saleQualified':False, 'validationReferencesRead':False}
    def save(**values):
        state.update(values, observedAt=now(), limits=limits.query())
        atomic_json(run/'state.json',state,progress=True)
    def check_stop():
        if (run/'stop.request').exists() or pressure.low():
            raise InterruptedError('Owned stop/Windows low-memory signal; latest committed checkpoint retained')
    try:
        save()
        state['presentDevices'] = present_discrete_gpu()
        stable_since = time.monotonic()
        while time.monotonic()-stable_since < packet['resources']['stableRamSeconds']:
            check_stop()
            require(available_ram() >= packet['resources']['minimumAvailableBytes'],
                    'Available RAM below original3.18GiB start/recovery threshold; no training started')
            time.sleep(1)
        import torch
        import transformers
        require(torch.__version__ == packet['runtime']['torch'] and transformers.__version__ == packet['runtime']['transformers'], 'Runtime changed')
        require(bool(torch.version.hip), 'ROCm runtime required; no CPU/CUDA substitution')
        torch.set_num_threads(4); torch.set_num_interop_threads(1)
        descriptions = []
        for index in range(torch.cuda.device_count()):
            prop = torch.cuda.get_device_properties(index)
            descriptions.append({'index':index,'name':prop.name,
                                 'architecture':getattr(prop,'gcnArchName',''),
                                 'totalMemory':prop.total_memory})
        chosen = select_gpu(descriptions); device = 'cuda:'+str(chosen['index'])
        torch.cuda.set_device(chosen['index'])
        from companion_community1_adapter_20261115 import pin_rocm_blas
        state['blas'] = pin_rocm_blas(packet['blas']['file'],packet['blas']['sha256'])
        torch.manual_seed(packet['training']['seed'])
        save(state='LOADING_PINNED_NATIVE_MODEL_ON_VERIFIED_DISCRETE_GPU', device=chosen)
        from transformers import AutoProcessor
        from practical_qwen_streamed_loader_20261107 import load_model
        processor = AutoProcessor.from_pretrained(packet['modelRoot'],local_files_only=True)
        model, loading = load_model(packet['modelRoot'],torch=torch,device=device,
                                    expected_sha256=packet['modelSha256'])
        atomic_json(run/'model-load.json',loading)
        model.requires_grad_(False)
        trainable = []
        for name, parameter in model.named_parameters():
            require(parameter.device.type == 'cuda', 'A model parameter is on CPU')
            if name.startswith(PREFIXES):
                parameter.data = parameter.data.float()
                parameter.requires_grad_(True)
                trainable.append((name,parameter))
        require(sum(p.numel() for _,p in trainable) == TRAINABLE_PARAMETERS, 'Acoustic/bridge coverage changed')
        parameters = [p for _,p in trainable]
        require(all(p.dtype == torch.float32 and p.device == torch.device(device) for p in parameters), 'FP32 trainable masters must remain on selected GPU')
        require(all(not p.requires_grad for n,p in model.named_parameters() if n not in dict(trainable)), 'Unexpected trainable parameter')
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        model.train()
        optimizer = torch.optim.AdamW(parameters, lr=packet['training']['learningRate'],
                                     betas=(.9,.999), eps=1e-8, weight_decay=0.,
                                     capturable=True, foreach=False, fused=False)
        require({id(p) for g in optimizer.param_groups for p in g['params']} == {id(p) for p in parameters}, 'Optimizer scope mismatch')
        torch.cuda.reset_peak_memory_stats()
        def frozen_digest():
            result = hashlib.sha256()
            for name,p in model.named_parameters():
                if p.requires_grad:
                    continue
                result.update((name+str(p.dtype)+str(tuple(p.shape))).encode())
                view = p.detach().view(torch.uint8).reshape(-1)
                for pos in range(0,view.numel(),1024**2):
                    check_stop(); result.update(view[pos:pos+1024**2].cpu().numpy().tobytes())
            return result.hexdigest()
        frozen_before = frozen_digest()

        def inputs_for(row):
            check_stop(); require(sha(row['audio']) == row['audioSha256'], 'Training PCM changed')
            import numpy as np
            with wave.open(row['audio'],'rb') as stream:
                samples = np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32)/32768
            values = processor.apply_transcription_request(audio=samples, language=row['language'],
                       processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':device}}).to(device,torch.bfloat16)
            require(set(values) <= {'input_ids','attention_mask','input_features','input_features_mask'}, 'Unexpected native training interface')
            require(int(values['input_features_mask'].sum().item()) >= len(samples)//160, 'Audio features were truncated')
            prefix = values['input_ids'][0].tolist()
            suffix = processor.tokenizer.decode(prefix[-12:],skip_special_tokens=False,clean_up_tokenization_spaces=False)
            require(suffix.endswith('language '+row['language']+'<asr_text>'), 'Training/inference language prefix differs')
            actual = processor.tokenizer.encode(row['text'],add_special_tokens=False)+[processor.tokenizer.eos_token_id]
            require(actual == targets[row['id']], 'Tokenizer target differs from offline binding')
            batch = padded_labels([prefix],[actual],processor.tokenizer.pad_token_id)
            for name in ['input_ids','attention_mask','labels']:
                values[name] = torch.tensor(batch[name],dtype=torch.long,device=device)
            require(int((values['labels'] != -100).sum().item()) == len(actual), 'Prompt/padding contaminated supervised labels')
            return values,len(actual)

        def checkpoint(label):
            check_stop()
            tensors = {}
            for name,p in trainable:
                slot = optimizer.state[p]
                require(set(slot) == {'step','exp_avg','exp_avg_sq'}, 'Unexpected Adam checkpoint state')
                require(float(slot['step'].item()) == state['optimizerUpdates'], 'Adam step disagrees with checkpoint')
                tensors['weight/'+name] = p
                for key in ['exp_avg','exp_avg_sq']:
                    require(slot[key].dtype == torch.float32 and slot[key].device == p.device, 'Adam moments are not FP32 on GPU')
                    tensors[key+'/'+name] = slot[key]
            required_bytes = sum(t.numel()*4 for t in tensors.values())
            require(shutil.disk_usage(run).free >= required_bytes+5*1024**3, 'Insufficient disk for complete recovery checkpoint')
            stem = label+'-'+str(state['optimizerUpdates']).zfill(6)+'-'+uuid.uuid4().hex[:8]
            file = run/(stem+'.safetensors')
            def reader(name,start,count):
                return tensors[name].detach().reshape(-1)[start:start+count].cpu().numpy().tobytes()
            receipt = write_float_checkpoint(file,[(n,list(t.shape)) for n,t in tensors.items()],reader,check_stop)
            receipt.update(binding=binding,file=file.name,mode=mode,optimizerUpdates=state['optimizerUpdates'],
                           completedExamples=state['completedExamples'],frozenDigest=frozen_before,
                           torchRng=torch.get_rng_state().tolist(),
                           gpuRng=torch.cuda.get_rng_state(chosen['index']).tolist())
            atomic_json(run/(stem+'.json'),receipt)
            atomic_json(run/'latest-checkpoint.json',{'binding':binding,'receipt':stem+'.json',
                                                    'receiptSha256':sha(run/(stem+'.json'))})
            save(lastCommittedCheckpoint=stem+'.json')
            return file,receipt

        def restore(file, receipt):
            require(receipt['mode'] == mode, 'Preflight weights cannot resume the actual training batch')
            require(0 < receipt['completedExamples'] <= (944 if mode == 'train' else 4), 'Invalid recovery progress')
            require(receipt['optimizerUpdates'] == (receipt['completedExamples']+1)//2, 'Recovery step/example counts disagree')
            header,offset = tensor_header(file)
            expected = {kind+'/'+name for name,_ in trainable for kind in ['weight','exp_avg','exp_avg_sq']}
            require(set(header) == expected, 'Incomplete recovery tensors')
            with torch.no_grad(), Path(file).open('rb') as stream:
                for name,p in trainable:
                    slot = optimizer.state[p]
                    slot['step'] = torch.tensor(float(receipt['optimizerUpdates']),dtype=torch.float32,device=device)
                    for kind in ['weight','exp_avg','exp_avg_sq']:
                        if kind != 'weight' and kind not in slot:
                            slot[kind] = torch.empty_like(p)
                        target = p if kind == 'weight' else slot[kind]
                        meta = header[kind+'/'+name]
                        require(meta['dtype'] == 'F32' and meta['shape'] == list(target.shape), 'Checkpoint dtype/shape mismatch')
                        stream.seek(offset+meta['data_offsets'][0])
                        flat = target.reshape(-1)
                        for pos in range(0,flat.numel(),262144):
                            check_stop(); count = min(262144,flat.numel()-pos)
                            raw = bytearray(stream.read(count*4))
                            require(len(raw) == count*4, 'Truncated recovery payload')
                            source = torch.frombuffer(raw,dtype=torch.float32)
                            flat[pos:pos+count].copy_(source.to(device))
            require(receipt['frozenDigest'] == frozen_before, 'Frozen backbone differs from recovery')
            state.update(optimizerUpdates=receipt['optimizerUpdates'],completedExamples=receipt['completedExamples'])
            torch.set_rng_state(torch.tensor(receipt['torchRng'],dtype=torch.uint8))
            torch.cuda.set_rng_state(torch.tensor(receipt['gpuRng'],dtype=torch.uint8),chosen['index'])

        def actual_gradient_parity():
            """Compare two unequal microbatches with one right-padded batch."""
            import torch.nn.functional as functional
            indices = [min([i for i,r in enumerate(rows) if r['language'] == language],
                           key=lambda i: rows[i]['audioSeconds']) for language in ['English','Chinese']]
            require(len(targets[rows[indices[0]]['id']]) != len(targets[rows[indices[1]]['id']]),
                    'Gradient parity requires unequal target lengths')
            samples = [inputs_for(rows[i])[0] for i in indices]
            probes = [next((n,p) for n,p in trainable if n.startswith(prefix) and p.numel() <= 4096)
                      for prefix in PREFIXES]
            denominator = sum(int((v['labels'] != -100).sum()) for v in samples)
            optimizer.zero_grad(set_to_none=True); accumulated_loss = 0.
            for values in samples:
                count = int((values['labels'] != -100).sum())
                with torch.autocast('cuda',dtype=torch.bfloat16):
                    output = model(**values,use_cache=False)
                    weighted = output.loss*(count/denominator)
                weighted.backward(); state['newNeuralCalls'] += 1
                accumulated_loss += float(weighted.detach())
                del output,weighted
            accumulated = {name:p.grad.detach().clone() for name,p in probes}
            optimizer.zero_grad(set_to_none=True)
            width = max(v['input_ids'].shape[-1] for v in samples)
            feature_width = max(v['input_features'].shape[-1] for v in samples)
            combined = {}
            for key in ['input_ids','attention_mask','labels']:
                fill = processor.tokenizer.pad_token_id if key == 'input_ids' else (-100 if key == 'labels' else 0)
                combined[key] = torch.cat([functional.pad(v[key],(0,width-v[key].shape[-1]),value=fill) for v in samples])
            for key in ['input_features','input_features_mask']:
                combined[key] = torch.cat([functional.pad(v[key],(0,feature_width-v[key].shape[-1]),value=0) for v in samples])
            with torch.autocast('cuda',dtype=torch.bfloat16):
                output = model(**combined,use_cache=False)
            output.loss.backward(); state['newNeuralCalls'] += 1
            differences = {}
            for name,p in probes:
                diff = torch.linalg.vector_norm(p.grad-accumulated[name])
                scale = torch.linalg.vector_norm(p.grad)+torch.linalg.vector_norm(accumulated[name])
                require(float(scale) > 0, 'Gradient-parity probe is zero')
                differences[name] = float(diff/scale)
            require(abs(float(output.loss)-accumulated_loss) <= .02, 'Batch/accumulated loss differs')
            require(all(v <= .05 for v in differences.values()), 'Batch/accumulated gradients differ')
            result = {'examples':[rows[i]['id'] for i in indices], 'targetTokens':denominator,
                      'lossDifference':abs(float(output.loss)-accumulated_loss),
                      'gradientRelativeL2Difference':differences,'optimizerUpdates':0,
                      'normalization':'Token-weighted masked CE,one denominator across the accumulated group'}
            optimizer.zero_grad(set_to_none=True)
            del samples,combined,output,accumulated
            return result

        order = balanced_order(rows,packet['training']['seed'])
        if resume:
            require(mode == 'train', 'Only the fixed training batch can resume')
            file,receipt = committed_checkpoint(run,binding)
            restore(file,receipt)
        if mode == 'preflight':
            state['gradientParity'] = actual_gradient_parity()
            selected = []
            for language in ['English','Chinese']:
                items = [i for i,r in enumerate(rows) if r['language'] == language]
                selected.append(max(items,key=lambda i: rows[i]['audioSeconds']*12.5+len(targets[rows[i]['id']])))
                selected.append(max(items,key=lambda i: rows[i]['audioSeconds']))
            order = list(dict.fromkeys(selected))
        completed = state['completedExamples']; started = time.perf_counter()
        save(state='ACTUAL_GPU_PREFLIGHT' if mode == 'preflight' else 'TRAINING_FIXED_ONE_EPOCH',
             trainableParameters=TRAINABLE_PARAMETERS,trainingPrecision='FP32 acoustic/bridge and Adam moments; BF16 autocast; frozen BF16 LM',
             frozenDigestBefore=frozen_before,totalExamples=len(order))
        last_checkpoint_update = state['optimizerUpdates']
        while completed < len(order):
            group = order[completed:completed+packet['training']['gradientAccumulation']]
            total_tokens = sum(len(targets[rows[i]['id']]) for i in group)
            optimizer.zero_grad(set_to_none=True)
            record = []
            for index in group:
                row = rows[index]; values,count = inputs_for(row)
                torch.cuda.synchronize(); began = time.perf_counter()
                with torch.autocast('cuda',dtype=torch.bfloat16):
                    output = model(**values,use_cache=False)
                    require(bool(torch.isfinite(output.loss)), 'Nonfinite masked loss')
                    loss = output.loss*(count/total_tokens)
                if mode == 'preflight':
                    with torch.no_grad():
                        explicit = torch.nn.functional.cross_entropy(
                            output.logits[:,:-1,:].detach().float().reshape(-1,output.logits.shape[-1]),
                            values['labels'][:,1:].reshape(-1),ignore_index=-100)
                        require(torch.allclose(explicit,output.loss.detach().float(),atol=1e-5,rtol=1e-5),
                                'Native masked loss differs from explicit target-only CE')
                    del explicit
                loss.backward(); state['newNeuralCalls'] += 1
                require(all(p.grad is None for p in model.parameters() if not p.requires_grad), 'Frozen backbone acquired gradients')
                record.append({'id':row['id'],'targetTokens':count,'loss':float(output.loss.detach()),'seconds':time.perf_counter()-began})
                del output,loss,values
            norm = torch.nn.utils.clip_grad_norm_(parameters,1.,error_if_nonfinite=True,foreach=False)
            if mode == 'preflight':
                require(all(p.grad is not None and p.grad.device == p.device for p in parameters), 'Missing/off-device acoustic gradients')
                require(float(norm) > 0, 'No nonzero acoustic gradient')
                probe = next(p for _,p in trainable if p.numel() < 100000 and bool((p.grad != 0).any()))
                probe_before = probe.detach().clone()
            check_stop(); optimizer.step(); optimizer.zero_grad(set_to_none=True)
            completed += len(group)
            state['optimizerUpdates'] += 1; state['completedExamples'] = completed
            if mode == 'preflight':
                require(not torch.equal(probe,probe_before), 'FP32 acoustic parameters did not update')
                del probe_before
            with (run/'training-history.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'at':now(),'optimizerUpdate':state['optimizerUpdates'],'examples':record,
                                         'gradNorm':float(norm),'completedExamples':completed})+'\n')
            save(gpuPeakAllocated=torch.cuda.max_memory_allocated(),gpuPeakReserved=torch.cuda.max_memory_reserved())
            should_checkpoint = ((mode == 'preflight' and completed == len(order)) or
                                 (mode == 'train' and (state['optimizerUpdates'] == 1 or state['optimizerUpdates'] % packet['training']['checkpointEveryUpdates'] == 0 or completed == len(order))))
            if should_checkpoint:
                file,receipt = checkpoint('preflight' if mode == 'preflight' else 'checkpoint')
                last_checkpoint_update = state['optimizerUpdates']
        require(frozen_digest() == frozen_before, 'Frozen language model changed')
        if mode == 'preflight':
            file,receipt = committed_checkpoint(run,binding)
            before = sha(file)
            with torch.no_grad():
                parameters[0].reshape(-1)[0].add_(1)
            restore(file,receipt)
            # Re-serialize after restore to prove exact weight+Adam state bytes.
            copy_file,copy_receipt = checkpoint('reload-proof')
            require(copy_receipt['sha256'] == before, 'Recovery changed weight/optimizer tensor bytes')
            proof = {'state':'PASS_ACTUAL_DISCRETE_GPU_ACOUSTIC_TRAINING_PREFLIGHT',
                     'at':now(),'binding':binding,'device':chosen,
                     'optimizerUpdatesPerformed':state['optimizerUpdates'],
                     'completedTrainingExamples':completed,'gpuPeakAllocated':torch.cuda.max_memory_allocated(),
                     'gpuPeakReserved':torch.cuda.max_memory_reserved(),'limits':limits.query(),
                     'targetOnlyLabelsVerified':True,'frozenBackboneBytesUnchanged':True,
                     'actualBatchGradientParity':state['gradientParity'],
                     'checkpointRestoreWeightAndAdamBytesExact':True,
                     'temporaryPreflightWeightsEligibleForCandidateTraining':False,
                     'seconds':time.perf_counter()-started,'qualityQualified':False}
            atomic_json(run/'preflight.json',proof)
            save(state='PASS_ACTUAL_GPU_PREFLIGHT_NOT_A_TRAINED_CANDIDATE')
        else:
            require(completed == 944 and state['optimizerUpdates'] == 472, 'Fixed epoch did not complete')
            save(state='COMPLETE_FIXED_ACOUSTIC_DOMAIN_PILOT_PENDING_INDEPENDENT_EVALUATION',
                 frozenLanguageBytesUnchanged=True,trainingSeconds=time.perf_counter()-started)
            atomic_json(run/'training-complete.json',state)
    except BaseException as error:
        import traceback
        save(state='STOPPED_OR_FAILED_RETAIN_LATEST_COMMITTED_CHECKPOINT', error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        save(finishedAt=now())
        pressure.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet',required=True,type=Path)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--mode',required=True,choices=['audit','preflight','train'])
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args(); packet = read(args.packet)
    limits = own_limits(5 if args.mode == 'audit' else 25)
    verify_bindings(packet); rows = training_rows(packet)
    targets,audit = inspect_inputs(packet,rows)
    binding = {'packetSha256':sha(args.packet),'workerSha256':sha(__file__)}
    run = args.run.resolve()
    if args.mode == 'audit':
        require(not args.resume,'Audit cannot resume neural work')
        run.mkdir(parents=True,exist_ok=True)
        atomic_json(run/'offline-audit.json',dict(audit,binding=binding,limits=limits.query()))
        print(json.dumps(audit)); return
    if args.mode == 'train':
        proof = read(packet['preflightReceipt'])
        require(proof['state'] == 'PASS_ACTUAL_DISCRETE_GPU_ACOUSTIC_TRAINING_PREFLIGHT' and proof['binding'] == binding,
                'Matching actual GPU preflight must complete before training')
    if args.resume:
        require(run.is_dir(), 'Resume run does not exist')
    else:
        run.mkdir(parents=True,exist_ok=False)
    require(not (run/'training-complete.json').exists(), 'Completed batch must not retrain')
    with exclusive_run(run):
        if args.resume:
            old = read(run/'state.json')
            require(old['mode'] == 'train' and old['binding'] == binding, 'Resume run identity changed')
            archive = run/('previous-state-'+sha(run/'state.json')[:16]+'.json')
            if not archive.exists():
                archive.write_bytes((run/'state.json').read_bytes())
        gpu_run(packet,rows,targets,run,args.mode,args.resume,binding,limits)


if __name__ == '__main__':
    main()
