"""Verify and adopt R24's original unfinished public token prefix, CPU only."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, psutil, sys
from moss_generation_checkpoint_20261107 import TokenLedger, make_binding, digest, restore

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
C = R / 'docs/handoffs/20261105-model-resume/full-L-retired-acoustic-20261106-r24'
A = Path('E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104')
read = lambda p: json.loads(Path(p).read_text(encoding='utf8'))
sha = lambda p: hashlib.file_digest(Path(p).open('rb'), 'sha256').hexdigest()
run = read(C / 'full-L-owner-resume.json')
assert run['finishedAt'] and not run.get('activePid') and run['results'][0]['exitCode'] != 0
folder = Path(run['results'][0]['receipt']).parent
state_raw = (folder / 'state.json').read_bytes()
state = json.loads(state_raw)
assert not psutil.pid_exists(state['pid']), 'Original worker PID is still live; do not adopt'
case = read(C / 'audio-only.json')[0]
protocol = read(C / 'frozen-protocol.json')
assert state['audioSha256'] == case['audioSha256'] and state['generatedTokens'] > 0
assert not any('reference' in key.lower() for key in case)
prepared_binding = protocol['runtime']['preparedInputs']
assert sha(prepared_binding['manifest']) == prepared_binding['sha256']
prepared = read(prepared_binding['manifest'])
assert prepared['audioSha256'] == case['audioSha256'] and prepared['roundtripAllTensorsBitwiseIdentical']
assert prepared['tensors']['input_ids']['shape'] == [1, state['inputTokens']]
assert prepared['tensors']['input_ids']['dtype'] == 'torch.int64'
generation = read(A / 'model/generation_config.json')
vocab = read(A / 'model/config.json')['text_config']['vocab_size']
eos = generation['eos_token_id']
eos_ids = {eos} if type(eos) is int else set(eos)
payload = (folder / 'generated-token-ids.jsonl').read_bytes()
tokens = []
for line in payload.splitlines(keepends=True):
    if not line.endswith(b'\n'):
        break
    values = json.loads(line)
    assert isinstance(values, list) and all(type(value) is int and 0 <= value < vocab for value in values)
    tokens.extend(values)
count = state['generatedTokens']
assert len(tokens) >= count
tokens = tokens[:count]
assert not any(value in eos_ids for value in tokens)
from tokenizers import Tokenizer
tokenizer = Tokenizer.from_file(str(A / 'model/tokenizer.json'))
decoded = tokenizer.decode(tokens, skip_special_tokens=True)
original_text = (folder / 'partial-transcript.txt').read_text(encoding='utf8')
assert decoded == original_text, 'Saved token prefix does not exactly reproduce original partial transcript'
binding = make_binding(case, protocol, prompt_sha256=prepared['tensors']['input_ids']['sha256'], prompt_tokens=state['inputTokens'], generation_config_sha256=sha(A / 'model/generation_config.json'))
dest = C / 'generation-recovery-bound-20261107'
ledger = TokenLedger(dest, binding=binding, vocab_size=vocab, eos_ids=eos_ids)
manifest, data = ledger.append(tokens)
loaded, check = restore({'manifest': str(manifest), 'sha256': sha(manifest)}, expected_binding=binding, vocab_size=vocab, eos_ids=eos_ids)
assert loaded == tokens and (folder / 'state.json').read_bytes() == state_raw
report = {'at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'), 'state': 'RETAINED_PREFIX_ADOPTED_AND_VERBATIM_TEXT_VERIFIED_NO_MODEL_RUN', 'sourceControl': str(C), 'sourceStateSha256': digest(state_raw), 'sourceProtocolSha256': sha(C / 'frozen-protocol.json'), 'sourceTokenFileSha256': digest(payload), 'sourcePartialTextSha256': sha(folder / 'partial-transcript.txt'), 'tokenizerSha256': sha(A / 'model/tokenizer.json'), 'retainedGeneratedTokens': len(tokens), 'completedSegmentsBeforeCrash': state['completedSegments'], 'lastCompletedSegmentEndSeconds': state['lastCompletedSegmentEndSeconds'], 'recoveryManifest': str(manifest), 'recoveryManifestSha256': sha(manifest), 'decodedTextExactlyMatchesOriginal': True, 'recoveryReadbackAllTokenIdsIdentical': True, 'originalArtifactsUnchanged': True, 'torchImported': 'torch' in sys.modules, 'gpuUsed': False, 'newWholeMeetingQuality': None, 'wholeMeetingComplete': False, 'actualResumedModelOutputVerified': False, 'limits': 'Token prefix only, not KV cache. Re-prefill still required; native resumed-output control must pass before continuing the full meeting. No reference opened or partial CER reported.'}
report.update(sourceRunSha256=sha(C/'full-L-owner-resume.json'),priorInferenceAttemptProcessFamilySeconds=run['results'][0]['wholeProcessFamilySeconds']+state.get('priorInferenceAttemptProcessFamilySeconds',0))
assert not report['torchImported']
(dest / 'adoption-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps(report, ensure_ascii=False), flush=True)
