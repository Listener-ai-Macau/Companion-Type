import unittest
from overlap_context_text_metrics_20261106 import attributed_text_metrics

def row(person, text, start, end):
    return {'speaker': person, 'text': text, 'start': start, 'end': end}

class ContextTextMetrics(unittest.TestCase):
    def test_perfect_activity_does_not_hide_wrong_overlapping_words(self):
        refs = [row('a', '甲乙', 0, 2), row('b', '丙丁', 1, 3), row('a', '尾巴', 4, 7)]
        hyps = [row('x', '甲乙', 0, 2), row('y', '丙错', 1, 3), row('x', '尾巴', 4, 7)]
        score = attributed_text_metrics(refs, hyps, 8)
        self.assertEqual(score['referenceOverlapSeconds'], 1)
        self.assertEqual(score['overlapContextUtterances']['characterErrorRate'], .25)
        self.assertEqual(score['singleSpeakerOnlyUtterances']['characterErrorRate'], 0)
        self.assertEqual(score['shortUtterances']['referenceCharacters'], 4)
        self.assertEqual(score['primaryCpCer']['totalEdits'], 1)
        self.assertFalse(score['pureOverlapWordsMeasured'])

    def test_extra_stream_is_not_discarded_or_oracle_filtered(self):
        refs = [row('a', '甲乙', 0, 2), row('b', '丙丁', 1, 3)]
        hyps = [row('x', '甲乙', 0, 2), row('y', '丙丁', 1, 3), row('z', '额外', 5, 6)]
        score = attributed_text_metrics(refs, hyps, 8)
        self.assertEqual(score['unassignedExtraStreamTotalEdits'], 2)
        self.assertEqual(score['primaryCpCer']['totalEdits'], 2)
        self.assertTrue(score['allPrimaryEditsAccountedFor'])

    def test_missing_speaker_all_words_still_count(self):
        refs = [row('a', '甲乙', 0, 2), row('b', '丙丁', 1, 3)]
        score = attributed_text_metrics(refs, [row('x', '甲乙', 0, 2)], 4)
        self.assertEqual(score['overlapContextUtterances']['edits']['delete'], 2)
        self.assertEqual(score['primaryCpCer']['referenceSpeakers'], 2)

    def test_same_speaker_overlap_is_not_two_people(self):
        refs = [row('a', '甲乙', 0, 2), row('a', '丙丁', 1, 4)]
        score = attributed_text_metrics(refs, refs, 5)
        self.assertEqual(score['referenceOverlapSeconds'], 0)
        self.assertIsNone(score['overlapContextUtterances']['characterErrorRate'])
        self.assertEqual(score['singleSpeakerOnlyUtterances']['referenceCharacters'], 4)

    def test_abutting_speech_and_empty_short_category(self):
        refs = [row('a', '甲乙', 0, 3), row('b', '丙丁', 3, 6)]
        score = attributed_text_metrics(refs, refs, 7)
        self.assertEqual(score['referenceOverlapSeconds'], 0)
        self.assertIsNone(score['shortUtterances']['characterErrorRate'])

    def test_insertions_at_stream_ends_remain_counted(self):
        refs = [row('a', '甲乙', 0, 3)]
        hyps = [row('x', '头甲乙尾', 0, 3)]
        score = attributed_text_metrics(refs, hyps, 4)
        self.assertEqual(score['singleSpeakerOnlyUtterances']['edits']['insert'], 2)
        self.assertEqual(score['primaryCpCer']['totalEdits'], 2)

if __name__ == '__main__':
    unittest.main()
