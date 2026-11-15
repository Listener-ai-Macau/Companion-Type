import unittest
import numpy as np
from companion_sedicow_conditioning_20261109 import stno_from_activity,project_stno
class ConditioningTests(unittest.TestCase):
    def test_four_physical_states(self):
        activity=np.array([[0,0],[1,0],[0,1],[1,1]],dtype=np.float32)
        self.assertTrue(np.array_equal(stno_from_activity(activity,0),np.eye(4,dtype=np.float32)))
    def test_soft_target_mass_and_probability_are_preserved(self):
        result=stno_from_activity(np.array([[.8,.6]],dtype=np.float32),0)
        self.assertTrue(np.allclose(result[:,0],[.08,.32,.12,.48]))
        self.assertAlmostEqual(float((result[1]+result[3])[0]),.8,places=6)
    def test_time_projection_keeps_partial_audio_and_silence_padding(self):
        source=np.array([[1,0],[0,1],[0,0],[0,0]],dtype=np.float32)
        result=project_stno(source,source_step_seconds=.01,source_start_seconds=0,audio_samples=320,frames=3)
        self.assertTrue(np.allclose(result[:,0],[.5,.5,0,0]))
        self.assertTrue(np.array_equal(result[:,1:],np.array([[1,1],[0,0],[0,0],[0,0]],dtype=np.float32)))
    def test_missing_clock_and_bad_probabilities_are_rejected(self):
        with self.assertRaises(ValueError):stno_from_activity(np.array([[1.1,.2]]),0)
        with self.assertRaises(ValueError):project_stno(np.eye(4),source_step_seconds=.01,source_start_seconds=1,audio_samples=320)
if __name__=='__main__':unittest.main()
