import unittest
from full_meeting_transcript_metrics_20261103 import speaker_cer

def segment(speaker,text,start=0,end=1):return {'speaker':speaker,'text':text,'start':start,'end':end}
class FullMeetingMetrics(unittest.TestCase):
 def test_anonymous_permutation_handles_simultaneous_voices(self):
  r=[segment('a','保留方案'),segment('b','不要实施')];h=[segment(8,'不要实施'),segment(5,'保留方案')]
  self.assertEqual(speaker_cer(r,h,2)['totalEdits'],0)
 def test_fragmented_one_person_is_not_free(self):
  r=[segment('a','甲乙丙丁',0,2)];h=[segment(1,'甲乙',0,1),segment(2,'丙丁',1,2)]
  self.assertGreater(speaker_cer(r,h,2)['totalEdits'],0)
 def test_extra_stream_and_missing_person_count(self):
  r=[segment('a','甲乙'),segment('b','丙丁')]
  self.assertEqual(speaker_cer(r,[],2)['edits']['delete'],4)
  h=[segment('x','甲乙'),segment('y','丙丁'),segment('z','戊己')]
  self.assertEqual(speaker_cer(r,h,2)['edits']['insert'],2)
 def test_crossing_reference_is_rejected(self):
  with self.assertRaises(ValueError):speaker_cer([segment('a','末句',0,2.1)],[],2)
 def test_many_false_speakers_are_counted_without_factorial_search(self):
  r=[segment('a','甲乙')];h=[segment(i,'甲乙') for i in range(103)]
  self.assertEqual(speaker_cer(r,h,2)['totalEdits'],204)

if __name__=='__main__':unittest.main()
