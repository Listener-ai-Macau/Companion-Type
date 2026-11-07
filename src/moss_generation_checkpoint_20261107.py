"""Bounded JSON token ledger for interrupted deterministic generation.

Checkpoint publication follows flushed/fsynced token bytes. An uncommitted
tail is ignored, never truncated. Full audio/prompt/model/generation identity
is bound; restoration does not claim KV-cache or resumed-output equivalence.
"""
from pathlib import Path
import hashlib, json, os


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf8')


def make_binding(case, protocol, *, prompt_sha256, prompt_tokens, generation_config_sha256):
    runtime = protocol['runtime']
    return {
        'meeting': case['meeting'], 'audioSha256': case['audioSha256'], 'audioSeconds': case['audioSeconds'],
        **{key: protocol[key] for key in ['modelRevision', 'officialSourceCommit', 'weightSha256']},
        'runtimeMath': {**{key: runtime[key] for key in ['torch', 'transformers', 'dtype', 'maxLength', 'queryBlock', 'keyBlock', 'encoderBatch', 'doSample', 'seed']}, 'dtype': case.get('dtype',runtime['dtype']), 'boundedMathAttention': bool(runtime.get('boundedMathAttention'))},
        'generationConfigSha256': generation_config_sha256,
        'promptSha256': prompt_sha256, 'promptTokens': prompt_tokens,
        'maximumGeneratedTokens': runtime['maxNewTokensSmoke' if case.get('smokeOnly') else 'maxNewTokensFull'],
        'preparedInputManifestSha256': runtime.get('preparedInputs', {}).get('sha256'),
        'scope': 'Original complete audio and prompt; no reference, speaker count, labels, hotwords or audio truncation.'
    }


def checked_tokens(values, vocab_size):
    if not isinstance(values, list) or any(type(value) is not int or not 0 <= value < vocab_size for value in values):
        raise ValueError('Invalid generated token IDs')
    return values


def append_retained_prefix(inputs, tokens, *, torch, vocab_size, audio_token_id):
    checked_tokens(tokens, vocab_size)
    if not tokens or audio_token_id in tokens:
        raise ValueError('A nonempty generated prefix without audio placeholders is required')
    ids, mask = inputs['input_ids'], inputs['attention_mask']
    if ids.ndim != 2 or ids.shape[0] != 1 or mask.shape != ids.shape or not bool((mask == 1).all().item()):
        raise ValueError('Original complete single unpadded prompt required')
    prefix = torch.tensor([tokens], dtype=ids.dtype, device=ids.device)
    # Audio fields retain the exact original tensor objects and full lengths.
    # No slice/reset/re-tokenization or mutation of the original input mapping.
    return {**inputs, 'input_ids': torch.cat([ids, prefix], dim=-1),
            'attention_mask': torch.cat([mask, torch.ones_like(prefix, dtype=mask.dtype)], dim=-1)}


class TokenLedger:
    def __init__(self, directory, *, binding, vocab_size, eos_ids):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.binding = binding
        self.vocab_size = vocab_size
        self.eos_ids = sorted(eos_ids)
        self.tokens = []
        self.offset = 0
        self.hash = hashlib.sha256()
        self.failed = False
        self.log = self.directory / 'generated-token-ids.jsonl'
        self.log.touch(exist_ok=False)

    def append(self, values, *, finished=False):
        if self.failed:
            raise RuntimeError('Prior checkpoint publication failed; start from a committed checkpoint in a new directory')
        checked_tokens(values, self.vocab_size)
        if self.tokens and self.tokens[-1] in self.eos_ids:
            raise ValueError('Cannot append after EOS')
        if any(value in self.eos_ids for value in values[:-1]):
            raise ValueError('Tokens after EOS')
        if len(self.tokens) + len(values) > self.binding['maximumGeneratedTokens']:
            raise ValueError('Declared generation budget exceeded')
        if not values:
            raise ValueError('Empty checkpoint')
        try:
            return self._commit(values, finished)
        except OSError as error:
            self.failed = True
            raise RuntimeError('Checkpoint I/O failed; committed prefix retained, no further appends in this writer') from error

    def _commit(self, values, finished):
        row = encode(values)
        # One append, flush and fsync before publishing any recoverable count.
        # A failed publication leaves earlier immutable checkpoints readable.
        with self.log.open('ab') as stream:
            stream.write(row)
            stream.flush()
            os.fsync(stream.fileno())
        self.hash.update(row)
        self.offset += len(row)
        self.tokens.extend(values)
        manifest = {
            'version': 1, 'binding': self.binding, 'bindingSha256': digest(encode(self.binding)),
            'tokenFile': self.log.name, 'committedByteLength': self.offset,
            'committedBytesSha256': self.hash.hexdigest(), 'tokenCount': len(self.tokens),
            'vocabSize': self.vocab_size, 'eosIds': self.eos_ids,
            'eosCompleted': self.tokens[-1] in self.eos_ids, 'finished': bool(finished),
            'tokenBytesFsyncedBeforePublication': True,
            'limits': 'Process-crash recovery of token prefix, not a KV cache or physical-power-loss qualification.'
        }
        content = encode(manifest)
        snapshot = self.directory / ('checkpoint-%010d.json' % len(self.tokens))
        with snapshot.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary = self.directory / 'latest.tmp'
        with temporary.open('wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.directory / 'latest.json')
        return snapshot, manifest


def restore(binding, *, expected_binding, vocab_size, eos_ids):
    path = Path(binding['manifest'])
    raw = path.read_bytes()
    if digest(raw) != binding['sha256']:
        raise ValueError('Generation checkpoint manifest changed')
    data = json.loads(raw)
    if data['version'] != 1 or data['binding'] != expected_binding or data['bindingSha256'] != digest(encode(expected_binding)):
        raise ValueError('Generation checkpoint belongs to different audio/prompt/model/decoding')
    if data['vocabSize'] != vocab_size or data['eosIds'] != sorted(eos_ids):
        raise ValueError('Generation checkpoint tokenizer configuration changed')
    if data['finished'] or data['eosCompleted'] or not data['tokenBytesFsyncedBeforePublication']:
        raise ValueError('Only an unfinished, published generation prefix can resume')
    if data['tokenFile'] != 'generated-token-ids.jsonl':
        raise ValueError('Unexpected checkpoint token file')
    size = data['committedByteLength']
    if type(size) is not int or not 0 < size <= 16 * 1024**2:
        raise ValueError('Invalid bounded token ledger size')
    with path.with_name(data['tokenFile']).open('rb') as stream:
        payload = stream.read(size)
        trailing = bool(stream.read(1))
    if len(payload) != size or digest(payload) != data['committedBytesSha256'] or not payload.endswith(b'\n'):
        raise ValueError('Committed token bytes changed or truncated')
    tokens = []
    for row in payload.splitlines():
        values = checked_tokens(json.loads(row), vocab_size)
        if not values:
            raise ValueError('Empty committed token row')
        tokens.extend(values)
    if len(tokens) != data['tokenCount'] or not 0 < len(tokens) < expected_binding['maximumGeneratedTokens'] or any(t in eos_ids for t in tokens):
        raise ValueError('Token count, budget or EOS does not describe an unfinished prefix')
    return tokens, {'manifest': str(path), 'manifestSha256': binding['sha256'], 'restoredTokens': len(tokens), 'uncommittedTailIgnored': trailing, 'fullOriginalAudioAndPromptRequired': True, 'kvCacheRestored': False, 'resumedModelOutputEquivalenceProven': False}
