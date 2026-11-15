"""One fixed acoustic-only adaptation on public natural multi-turn contexts.

Uses the established checkpoint/loader and PEFT, not a new recognizer. Masked
teacher forcing follows the official Qwen ASR SFT collator, adapted to the
installed native Transformers request interface. Validation answers are never
read here. Training has no overlapping labels; original overlapping diagnostic
clips remain unchanged. This is not SOT or a repeat of the rejected LM adapter.
No output word cleanup or reference-conditioned generation.
https://github.com/QwenLM/Qwen3-ASR/blob/main/finetuning/qwen3_asr_sft.py
"""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import os
import random
import sys
import time
import traceback
import wave

os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                  HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
from companion_local_qwen_worker_20261114 import NativeDecoder
from companion_local_pcm_session_20261114 import parse_generated_tokens
from practical_qwen_bounded_decode_20261107 import repeated_block

read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', required=True, type=Path)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    control, run = args.control.resolve(), args.run.resolve()
    assert run.exists() and not (run / 'trial-state.json').exists()
    for phase in ['baseline-validation', 'baseline-controls', 'candidate-validation', 'candidate-controls']:
        (run / phase).mkdir(exist_ok=False)
    limits = WorkerLimits(cpu_percent=5, memory_bytes=2*1024**3)
    protocol = read(control / 'protocol.json')
    dependency = read(control / 'isolated-peft.json')
    binding = read(control / 'worker-binding.json')
    assert binding['workerSha256'] == sha(__file__)
    assert binding['protocolSha256'] == sha(control / 'protocol.json')
    for path, expected in binding['helpers'].items():
        assert sha(path) == expected
    assert sha(protocol['nativeProtocol']) == protocol['nativeProtocolSha256']
    assert sha(protocol['baselineChineseControl']) == binding['baselineControlSha256']
    assert sha(Path(protocol['baselineNativeRun'])/'baseline-state.json') == protocol['baselineNativeStateSha256']
    for path, expected in binding['baselineDocumentBindings'].items():
        assert sha(path) == expected
    sys.path.insert(0, dependency['target'])
    assert protocol['training'] == {
        'method': 'PEFT LoRA, last8 audio encoder layers only; frozen language model and original weights', 'rank': 8, 'alpha': 16,
        'targetModules': 'Only last8 audio-tower self-attention q_proj/v_proj', 'dropout': 0.,
        'learningRate': 2e-5, 'epochs': 1, 'batchSize': 1, 'gradientAccumulation': 2,
        'optimizer': 'AdamW betas(0.9,0.999), weight_decay0', 'gradientClip': 1., 'seed': 20261114,
        'savedCheckpoints': 'Every optimizer update recoverable; final adapter only for validation, no epoch/lr selection'}
    assert sha(control / 'train.json') == protocol['trainManifestSha256']
    assert sha(control / 'validation-audio-only.json') == protocol['validationAudioManifestSha256']
    training = read(control / 'train.json')
    validation = read(control / 'validation-audio-only.json')
    controls = read(control / 'capability-controls-audio-only.json')
    assert not any('text' in row or any('reference' in key.lower() for key in row) for row in validation+controls)
    assert len(training) >= 20 and len(validation) == 32
    assert all(not row['overlappingReferenceSpeech'] and row['atLeastTwoAnnotatedSpeakers'] for row in training)
    state = {'state': 'STARTING_BOUNDED_ASR_ADAPTER_PILOT', 'startedAt': now(), 'pid': os.getpid(),
             'workerSourceSha256': sha(__file__), 'binding': binding, 'trainingSteps': 0, 'optimizerUpdates': 0,
             'generationCalls': 0, 'generationSeconds': 0., 'validationReferenceRead': False,
             'qualityQualified': False, 'automaticRetries': 0}
    began = time.perf_counter()

    def save(**values):
        state.update(values, observedAt=now(), limits=limits.query())
        atomic_json(run / 'trial-state.json', state, progress=True)

    def check_stop():
        if (run / 'stop.request').exists():
            raise InterruptedError('Owned resource/stop request; original model and completed raw outputs retained')

    class Session:
        def state(self):
            return {'config': {'language': 'Chinese'}}

    try:
        save()
        base_protocol = Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-runtime-r2/source/native-protocol.json')
        from companion_community1_adapter_20261115 import pin_rocm_blas
        state['blas'] = pin_rocm_blas()
        decoder = NativeDecoder(base_protocol, args.inventory, Session(), run)
        decoder.load()
        torch, processor = decoder.torch, decoder.processor
        import numpy as np
        import peft
        from peft import LoraConfig, get_peft_model
        assert peft.__version__ == dependency['version']
        torch.manual_seed(20261114)
        random.seed(20261114)
        np.random.seed(20261114)
        model = decoder.model
        assert model.config._attn_implementation == 'eager'
        model.eval().requires_grad_(False)
        save(state='VERIFYING_INITIAL_MODEL_INTERFACE', modelLoaded=True,
             peftVersion=peft.__version__, modelLoadSeconds=decoder.state['modelLoadSeconds'])

        def audio(row):
            check_stop()
            assert sha(row['audio']) == row['audioSha256']
            with wave.open(row['audio'], 'rb') as stream:
                assert (stream.getnchannels(), stream.getframerate(), stream.getsampwidth()) == (1, 16000, 2)
                samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(np.float32)/32768
            assert abs(len(samples)/16000-row['audioSeconds']) < 1/16000
            return samples

        def prefix(row, language):
            samples = audio(row)
            options = {'audio': samples, 'processor_kwargs': {'audio_kwargs': {'sampling_rate': 16000, 'device': 'cuda:0'}}}
            if language != 'auto':
                options['language'] = language
            inputs = processor.apply_transcription_request(**options).to('cuda:0', model.dtype)
            assert int(inputs['input_features_mask'].sum().item()) >= len(samples)//160
            return inputs

        def generate(row, language='Chinese'):
            from transformers import StoppingCriteria, StoppingCriteriaList
            model.eval()
            inputs = prefix(row, language)
            size = inputs['input_ids'].shape[1]

            class Stop(StoppingCriteria):
                def __call__(self, input_ids, scores, **kwargs):
                    check_stop()
                    return repeated_block(input_ids[0, size:].tolist(), suffix_only=True) is not None

            torch.cuda.synchronize()
            at = time.perf_counter()
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=512, do_sample=False,
                                        stopping_criteria=StoppingCriteriaList([Stop()]))
            torch.cuda.synchronize()
            elapsed = time.perf_counter()-at
            ids = output[0, size:].cpu().tolist()
            parsed = parse_generated_tokens(ids, processor.tokenizer, language=language)
            eos = model.generation_config.eos_token_id
            eos = [eos] if isinstance(eos, int) else eos
            packet = {'id': row['id'], 'audioSha256': row['audioSha256'], 'languagePolicy': language,
                      'generatedIds': ids, 'rawDecoded': processor.tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False),
                      'text': parsed['text'], 'language': parsed['language'], 'naturalEos': bool(ids and ids[-1] in eos),
                      'repeatBlock': repeated_block(ids), 'seconds': elapsed,
                      'referenceUsed': False, 'wordsPostEdited': False, 'inputNotTruncated': True}
            state['generationCalls'] += 1
            state['generationSeconds'] += elapsed
            del output, inputs
            check_stop()
            assert packet['naturalEos'] and packet['repeatBlock'] is None, 'Invalid generation retained; no new training after a broken baseline'
            time.sleep(1)
            return packet

        test_row = validation[0]
        initial = generate(test_row)
        atomic_json(run / 'before-adapter-control.json', initial)
        original_control = read(protocol['baselineChineseControl'])
        assert initial['generatedIds'] == original_control['raw']['generatedIds'], 'Original native prefix must remain exact before any updates'
        last_layers = set(range(model.config.audio_config.encoder_layers-8, model.config.audio_config.encoder_layers))
        targets = [name for name, module in model.named_modules()
                   if name.startswith('model.audio_tower.layers.') and int(name.split('.')[3]) in last_layers
                   and name.endswith(('.self_attn.q_proj', '.self_attn.v_proj'))
                   and isinstance(module, torch.nn.Linear)]
        assert len(targets) == 16
        config = LoraConfig(r=8, lora_alpha=16, target_modules=targets, lora_dropout=0., bias='none')
        model = get_peft_model(model, config)
        no_op = generate(test_row)
        atomic_json(run / 'initial-adapter-control.json', no_op)
        assert no_op['generatedIds'] == initial['generatedIds'], 'Initial adapter changed baseline decoding'
        trainable = [(name, value) for name, value in model.named_parameters() if value.requires_grad]
        assert trainable and all('lora_' in name and 'audio_tower.layers.' in name for name, _ in trainable)
        assert all(not value.requires_grad for name, value in model.named_parameters() if 'language_model' in name)
        save(state='INITIAL_ADAPTER_EXACT_BASELINE_PASSED', trainableParameters=sum(p.numel() for _, p in trainable),
             frozenParameters=sum(p.numel() for p in model.parameters() if not p.requires_grad), targetModules=targets)

        def frozen_digest():
            digest = hashlib.sha256()
            count = 0
            for name, parameter in model.named_parameters():
                if parameter.requires_grad:
                    continue
                check_stop()
                digest.update((name+str(parameter.dtype)+str(tuple(parameter.shape))).encode())
                raw = parameter.detach().view(torch.uint8).reshape(-1)
                for start in range(0, raw.numel(), 16*1024**2):
                    block = raw[start:start+16*1024**2].cpu().numpy()
                    digest.update(memoryview(block))
                count += 1
            return {'sha256': digest.hexdigest(), 'parameterTensors': count}

        frozen_before = frozen_digest()
        atomic_json(run / 'frozen-before.json', frozen_before)
        # Baseline generation is audio-only. Validation labels are held by the
        # independent scorer, which is never imported in this worker.
        # Reuse frozen original32 native outputs; no additional baseline sweep.
        for row in validation:
            original = read(Path(protocol['baselineNativeRun'])/'sessions'/row['id']/'document.json')
            atomic_json(run/'baseline-validation'/(row['id']+'.json'),
                        {'id':row['id'],'audioSha256':row['audioSha256'],'text':original['text'],
                         'baselineReused':True,'referenceUsed':False})
        for phase, rows in [('baseline-controls', controls)]:
            for index, row in enumerate(rows):
                result = generate(row, row.get('language', 'Chinese'))
                atomic_json(run / phase / (row['id']+'.json'), result)
                save(state=phase.upper().replace('-', '_'), completedCases=index+1, totalCases=len(rows))

        def training_inputs(row):
            inputs = prefix(row, 'Chinese')
            assert set(inputs) <= {'input_ids', 'attention_mask', 'input_features', 'input_features_mask'}
            suffix = processor.tokenizer.decode(inputs['input_ids'][0, -12:].tolist(), skip_special_tokens=False, clean_up_tokenization_spaces=False)
            assert suffix.endswith('language Chinese<asr_text>'), 'Training prefix differs from forced-Chinese inference'
            target = processor.tokenizer.encode(row['text']+processor.tokenizer.eos_token, add_special_tokens=False)
            assert target and len(target) <= 512
            target_ids = torch.tensor([target], dtype=torch.long, device='cuda:0')
            prefix_size = inputs['input_ids'].shape[1]
            inputs['input_ids'] = torch.cat([inputs['input_ids'], target_ids], dim=1)
            inputs['attention_mask'] = torch.cat([inputs['attention_mask'], torch.ones_like(target_ids)], dim=1)
            labels = inputs['input_ids'].clone()
            labels[:, :prefix_size] = -100
            assert torch.equal(labels[:, prefix_size:], target_ids) and bool((labels[:, :prefix_size] == -100).all())
            inputs['labels'] = labels
            return inputs, {'maskedPrefixTokens': prefix_size, 'supervisedTargetTokens': len(target), 'originalTextSha256': hashlib.sha256(row['text'].encode()).hexdigest()}

        model.train()
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        proof_row = max(training, key=lambda r:r['audioSeconds'])
        proof_inputs, mask_proof = training_inputs(proof_row)
        proof = model(**proof_inputs, use_cache=False)
        assert proof.loss is not None and bool(torch.isfinite(proof.loss))
        proof.loss.backward()
        parameters = [parameter for _, parameter in trainable]
        nonzero = sum(int(p.grad is not None and bool((p.grad != 0).any())) for p in parameters)
        assert nonzero and all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in parameters)
        assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
        atomic_json(run / 'gradient-proof.json', {'state': 'PASS_REAL_COMPLETE_TRAIN_UTTERANCE_MASKED_LOSS_AND_FINITE_ADAPTER_GRADIENTS',
                                                   'trainingId': proof_row['id'], 'loss': float(proof.loss.detach()),
                                                   'nonzeroGradientTensors': nonzero, 'optimizerStepPerformedForProof': False,
                                                   'frozenParameterGradsAbsent': True, **mask_proof})
        model.zero_grad(set_to_none=True)
        del proof_inputs, proof
        optimizer = torch.optim.AdamW(parameters, lr=2e-5, betas=(.9, .999), weight_decay=0.)
        assert {id(p) for group in optimizer.param_groups for p in group['params']} == {id(p) for p in parameters}
        order = list(range(len(training)))
        random.Random(20261114).shuffle(order)
        save(state='TRAINING_ONE_FIXED_ADAPTER_EPOCH', completedTrainingExamples=0)
        for step, index in enumerate(order):
            check_stop()
            inputs, mask = training_inputs(training[index])
            torch.cuda.synchronize()
            at = time.perf_counter()
            output = model(**inputs, use_cache=False)
            assert bool(torch.isfinite(output.loss))
            loss = float(output.loss.detach())
            group_size = min(2,len(order)-(step//2)*2)
            (output.loss/group_size).backward()
            if (step+1) % 2 == 0 or step+1 == len(order):
                grad_norm = torch.nn.utils.clip_grad_norm_(parameters, 1., error_if_nonfinite=True)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                state['optimizerUpdates'] += 1
                recovery = run/'recovery'/('update-'+str(state['optimizerUpdates']).zfill(2))
                assert not recovery.exists()
                model.save_pretrained(str(recovery), safe_serialization=True, save_embedding_layers=False)
                torch.save({'optimizer':optimizer.state_dict(),'torchRng':torch.get_rng_state(),
                            'cudaRng':torch.cuda.get_rng_state_all(),'pythonRng':random.getstate(),
                            'numpyRng':np.random.get_state(),'nextTrainingStep':step+1,'order':order},
                           recovery/'training-state.pt')
                atomic_json(recovery/'receipt.json',{'optimizerUpdates':state['optimizerUpdates'],
                            'completedTrainingSteps':step+1,'adapterSha256':sha(recovery/'adapter_model.safetensors'),
                            'selectedForValidation':False})
            torch.cuda.synchronize()
            elapsed = time.perf_counter()-at
            state['trainingSteps'] += 1
            with (run / 'training-history.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'at': now(), 'step': step+1, 'id': training[index]['id'], 'loss': loss,
                                         'optimizerUpdates': state['optimizerUpdates'], 'seconds': elapsed})+'\n')
            del inputs, output
            save(state='TRAINING_ONE_FIXED_ADAPTER_EPOCH', completedTrainingExamples=step+1)
            time.sleep(1)
        assert state['trainingSteps'] == len(training) and state['optimizerUpdates'] == (len(training)+1)//2
        model.gradient_checkpointing_disable()
        model.eval()
        frozen_after = frozen_digest()
        atomic_json(run / 'frozen-after.json', frozen_after)
        assert frozen_after == frozen_before, 'Frozen backbone bytes changed; candidate rejected'
        save(state='SAVING_FINAL_ADAPTER_ONLY_BACKBONE_BYTES_UNCHANGED')
        adapter = run / 'final-adapter'
        assert not adapter.exists()
        model.save_pretrained(str(adapter), safe_serialization=True, save_embedding_layers=False)
        assert (adapter / 'adapter_model.safetensors').stat().st_size < 64*1024**2
        state['adapterSha256'] = sha(adapter / 'adapter_model.safetensors')
        from safetensors.torch import load_file
        from peft import get_peft_model_state_dict, set_peft_model_state_dict
        saved = load_file(str(adapter/'adapter_model.safetensors'))
        live = get_peft_model_state_dict(model)
        assert set(saved)==set(live) and all(torch.equal(saved[n],live[n].detach().cpu()) for n in saved)
        set_peft_model_state_dict(model,saved)
        state['adapterSavedReloadedExactTensors'] = len(saved)
        del saved,live
        for phase, rows in [('candidate-validation', validation), ('candidate-controls', controls)]:
            for index, row in enumerate(rows):
                result = generate(row, row.get('language', 'Chinese'))
                atomic_json(run / phase / (row['id']+'.json'), result)
                save(state=phase.upper().replace('-', '_'), completedCases=index+1, totalCases=len(rows))
        with model.disable_adapter():
            preserved = generate(controls[0], controls[0]['language'])
        atomic_json(run / 'after-training-disabled-English-control.json', preserved)
        original = read(run / 'baseline-controls' / (controls[0]['id']+'.json'))
        assert preserved['generatedIds'] == original['generatedIds'], 'Disabled adapter no longer reproduces baseline'
        save(state='COMPLETE_ONE_ADAPTER_TRIAL_INDEPENDENT_SCORING_PENDING',
             allFrozenParameterBytesUnchanged=True, exactDisabledAdapterEnglishBaselinePreserved=True)
    except BaseException as error:
        save(state='FAILED_BOUNDED_ADAPTER_TRIAL_RETAINED', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        state.pop('pid', None)
        state.update(finishedAt=now(), seconds=time.perf_counter()-began, limits=limits.query())
        atomic_json(run / 'trial-state.json', state)
        print(json.dumps({k: state.get(k) for k in ['state', 'error', 'trainingSteps', 'optimizerUpdates', 'generationCalls', 'seconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
