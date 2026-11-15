import unittest
from companion_meeting_route_plan_20261109 import plan_routes

class RoutePlanTests(unittest.TestCase):
    def test_unknown_audio_is_retained_for_asr(self):
        rows=plan_routes([],source_frames=100,sample_rate=10)
        self.assertEqual(rows[0]['route'],'raw_asr_unattributed')
        self.assertEqual((rows[0]['startSample'],rows[0]['endSample']),(0,100))
    def test_all_frames_once_and_only_true_predicted_overlap_is_candidate(self):
        rows=plan_routes([{'start':1,'end':5,'speaker':'a'},{'start':3,'end':7,'speaker':'b'}],source_frames=100,sample_rate=10)
        self.assertEqual([(r['startSample'],r['endSample'],r['predictedPeople']) for r in rows],[(0,10,[]),(10,30,['a']),(30,50,['a','b']),(50,70,['b']),(70,100,[])])
        self.assertEqual([r['route'] for r in rows].count('candidate_target_extraction'),1)
        self.assertTrue(all(r['retainRawSource'] and not r['candidateCanReplaceRawByDefault'] for r in rows))
    def test_duplicate_same_person_and_touching_turns_do_not_create_overlap(self):
        rows=plan_routes([{'start':0,'end':4,'speaker':0},{'start':2,'end':5,'speaker':0},{'start':5,'end':10,'speaker':1}],source_frames=100,sample_rate=10)
        self.assertEqual([(r['startSample'],r['endSample'],r['predictedPeople']) for r in rows],[(0,50,['0']),(50,100,['1'])])
        self.assertTrue(all(r['route']=='raw_asr' for r in rows))
    def test_bad_activity_fails_without_silently_clipping(self):
        for row in [{'start':0,'end':11,'speaker':0},{'start':0,'end':float('nan'),'speaker':0},{'start':1,'end':1,'speaker':0}]:
            with self.assertRaises(ValueError):plan_routes([row],source_frames=100,sample_rate=10)
    def test_independent_overlap_does_not_invent_a_second_identity(self):
        rows=plan_routes([{'start':0,'end':10,'speaker':'a'}],source_frames=100,sample_rate=10,overlap_regions=[{'start':3,'end':5}])
        self.assertEqual([(r['startSample'],r['endSample'],r['route']) for r in rows],[(0,30,'raw_asr'),(30,50,'candidate_overlap_identity_pending'),(50,100,'raw_asr')])
        self.assertEqual(rows[1]['predictedPeople'],['a'])
        self.assertTrue(rows[1]['targetIdentityPending'])
        self.assertTrue(rows[1]['retainRawSource'])
        self.assertFalse(rows[1]['candidateCanReplaceRawByDefault'])
    def test_independent_overlap_without_a_journal_keeps_audio(self):
        rows=plan_routes([],source_frames=100,sample_rate=10,overlap_regions=[{'start':1,'end':6},{'start':4,'end':8}])
        self.assertEqual(sum(r['endSample']-r['startSample'] for r in rows),100)
        candidate=[r for r in rows if r['targetIdentityPending']]
        self.assertTrue(candidate)
        self.assertTrue(all(not r['predictedPeople'] for r in candidate))

if __name__=='__main__':unittest.main()
