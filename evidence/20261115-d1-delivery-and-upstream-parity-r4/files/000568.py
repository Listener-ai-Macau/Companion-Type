import unittest
import numpy as np
from practical_nemotron_worker_20261107 import probability_segments,ModelConfig
import ctypes
class NativeBoundary(unittest.TestCase):
    def test_three_simultaneous_speakers_remain_three(self):
        probabilities=np.zeros((3,8),np.float32);probabilities[1,0:3]=.9
        rows=probability_segments(probabilities,3,.01,.03,.5)
        self.assertEqual(rows,[{'start':.01,'end':.02,'speaker':s} for s in range(3)])
    def test_padded_audio_tail_never_becomes_a_segment(self):
        probabilities=np.ones((5,8),np.float32)
        rows=probability_segments(probabilities,5,.01,.035,.5)
        self.assertEqual(len(rows),8)
        self.assertTrue(all(r['start']==0 and r['end']==.035 for r in rows))
    def test_native_config_windows64_size_and_threshold_boundary(self):
        self.assertEqual(ctypes.sizeof(ModelConfig),56)
        probabilities=np.full((3,8),.5,np.float32)
        self.assertEqual(probability_segments(probabilities,3,.01,.03,.5),[])
    def test_exact_threshold_keeps_native_active_state(self):
        probabilities=np.zeros((3,8),np.float32);probabilities[:,0]=[.6,.5,.4]
        self.assertEqual(probability_segments(probabilities,3,.01,.03,.5),[{'start':0.,'end':.02,'speaker':0}])
if __name__=='__main__':unittest.main()
