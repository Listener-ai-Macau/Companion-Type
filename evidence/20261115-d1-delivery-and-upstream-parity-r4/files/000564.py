import copy, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from moss_generation_checkpoint_20261107 import TokenLedger, restore, digest

class GenerationCheckpoint(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.binding = {'audioSha256': 'a' * 64, 'promptSha256': 'b' * 64, 'modelRevision': 'fixed', 'maximumGeneratedTokens': 200}
        self.ledger = TokenLedger(self.base / 'ledger', binding=self.binding, vocab_size=256, eos_ids={255})
    def tearDown(self):
        self.temp.cleanup()
    def read(self, path, expected=None):
        return restore({'manifest': str(path), 'sha256': digest(path.read_bytes())}, expected_binding=expected or self.binding, vocab_size=256, eos_ids={255})
    def test_reopen_retains_full_prefix_and_later_checkpoint_does_not_invalidate_old(self):
        first, _ = self.ledger.append([1, 2, 3])
        second, _ = self.ledger.append([4, 5])
        self.assertEqual(self.read(first)[0], [1, 2, 3])
        self.assertTrue(self.read(first)[1]['uncommittedTailIgnored'])
        self.assertEqual(self.read(second)[0], [1, 2, 3, 4, 5])
    def test_crash_leaves_uncommitted_partial_tail_without_destroying_saved_prefix(self):
        first, _ = self.ledger.append([1, 2])
        with self.ledger.log.open('ab') as f: f.write(b'[3,')
        before = self.ledger.log.read_bytes()
        self.assertEqual(self.read(first)[0], [1, 2])
        self.assertEqual(self.ledger.log.read_bytes(), before)
    def test_failed_publication_preserves_previous_checkpoint(self):
        first, _ = self.ledger.append([1, 2])
        with patch('moss_generation_checkpoint_20261107.os.replace', side_effect=OSError('injected publication interruption')):
            with self.assertRaises(RuntimeError): self.ledger.append([3, 4])
        self.assertEqual(self.read(first)[0], [1, 2])
        with self.assertRaises(RuntimeError): self.ledger.append([3, 4])
    def test_wrong_audio_or_prompt_rejected(self):
        first, _ = self.ledger.append([1, 2])
        for field in ['audioSha256', 'promptSha256', 'modelRevision', 'maximumGeneratedTokens']:
            changed = copy.deepcopy(self.binding); changed[field] = 'changed'
            with self.assertRaises(ValueError): self.read(first, changed)
    def test_tampered_and_truncated_committed_bytes_rejected(self):
        first, _ = self.ledger.append([1, 2])
        old = self.ledger.log.read_bytes()
        for payload in [old[:-1], old.replace(b'1', b'9', 1)]:
            self.ledger.log.write_bytes(payload)
            with self.assertRaises(ValueError): self.read(first)
    def test_manifest_hash_and_path_tampering_rejected(self):
        first, _ = self.ledger.append([1, 2])
        with self.assertRaises(ValueError): restore({'manifest': str(first), 'sha256': '0' * 64}, expected_binding=self.binding, vocab_size=256, eos_ids={255})
        data = json.loads(first.read_text()); data['tokenFile'] = '../other.jsonl'
        first.write_text(json.dumps(data))
        with self.assertRaises(ValueError): self.read(first)
    def test_invalid_tokens_and_budget_rejected_before_append(self):
        for values in [[True], [-1], [256], ['1'], [255, 1], list(range(201))]:
            with self.assertRaises(ValueError): self.ledger.append(values)
        self.assertEqual(self.ledger.log.read_bytes(), b'')
    def test_completed_eos_prefix_cannot_resume(self):
        done, _ = self.ledger.append([1, 2, 255], finished=True)
        with self.assertRaises(ValueError): self.read(done)
        with self.assertRaises(ValueError): self.ledger.append([3])
    def test_existing_ledger_directory_not_overwritten(self):
        before = list(self.ledger.directory.iterdir())
        with self.assertRaises(FileExistsError): TokenLedger(self.ledger.directory, binding=self.binding, vocab_size=256, eos_ids={255})
        self.assertEqual(before, list(self.ledger.directory.iterdir()))

if __name__ == '__main__': unittest.main()
