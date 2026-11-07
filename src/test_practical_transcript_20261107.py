import unittest
from practical_transcript_20261107 import align_window,onset_attribution,token_text_spans

class PracticalAttribution(unittest.TestCase):
    def test_different_people_inside_one_wide_window(self):
        raw={'index':0,'startSample':0,'endSample':3*16000,'text':'甲乙','tokens':['甲','乙'],'timestamps':[.5,1.5]}
        out=align_window(raw,[{'start':0.,'end':1.,'speaker':0},{'start':1.,'end':3.,'speaker':1}],audio_seconds=3)
        self.assertEqual([r['speaker'] for r in out['utterances']],[0,1]);self.assertEqual(''.join(r['text'] for r in out['utterances']),'甲乙')
    def test_overlap_never_guesses_a_primary_person(self):
        out=onset_attribution(1.,[{'start':0.,'end':2.,'speaker':2},{'start':.5,'end':1.5,'speaker':8}],duration=2)
        self.assertIsNone(out['speaker']);self.assertEqual(out['candidateSpeakers'],[2,8]);self.assertTrue(out['overlapDetectedNearOnset'])
    def test_boundary_and_gap_are_unknown_without_claiming_overlap(self):
        journal=[{'start':0.,'end':1.,'speaker':0},{'start':1.,'end':2.,'speaker':1}]
        out=onset_attribution(1.,journal,duration=3)
        self.assertIsNone(out['speaker']);self.assertFalse(out['overlapDetectedNearOnset'])
        self.assertIsNone(onset_attribution(2.5,journal,duration=3)['speaker'])
    def test_whitespace_repetitions_and_numbers_preserved(self):
        text=' 001 很 很好  AB ';tokens=['0','0','1','▁很','▁很','好','▁AB']
        spans=token_text_spans(text,tokens);self.assertIsNotNone(spans);self.assertEqual(''.join(text[a:b] for a,b in spans),text)
    def test_mismatched_tokenization_preserves_whole_original_as_unknown(self):
        raw={'index':0,'startSample':16000,'endSample':32000,'text':'原话不能改','tokens':['错'],'timestamps':[.5]}
        out=align_window(raw,[],audio_seconds=3);self.assertFalse(out['alignmentAvailable']);self.assertEqual(out['utterances'][0]['text'],raw['text']);self.assertIsNone(out['utterances'][0]['speaker'])
    def test_window_offsets_applied_once_and_bad_timing_rejected(self):
        raw={'index':1,'startSample':16000,'endSample':32000,'text':'话','tokens':['话'],'timestamps':[.5]}
        out=align_window(raw,[{'start':1.,'end':2.,'speaker':4}],audio_seconds=3);self.assertEqual(out['tokenEstimates'][0]['estimatedOnsetSeconds'],1.5)
        for times in [[1.1],[float('nan')],[]]:
            with self.assertRaises(ValueError):align_window({**raw,'timestamps':times},[],audio_seconds=3)

if __name__=='__main__':unittest.main()
