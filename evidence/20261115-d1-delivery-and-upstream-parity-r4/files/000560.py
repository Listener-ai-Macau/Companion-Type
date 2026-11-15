import unittest
import numpy as np
from companion_local_overlap_regions_20261109 import local_overlap_regions, posterior_overlap_regions

META={'sample_rate':16000,'window_size':1600,'window_shift':160,'receptive_field_shift':160,'receptive_field_size':160,'num_speakers':3,'powerset_max_classes':2}
class MarginalTests(unittest.TestCase):
    def test_distributed_pair_probability_survives_single_argmax(self):
        value=np.array([1e-8,.4,1e-8,1e-8,.2,.2,.2],dtype=np.float32);value/=value.sum()
        logits=np.log(np.tile(value,(1,10,1)))
        hard,_=local_overlap_regions(logits,META,source_frames=1600)
        soft,metadata,probability=posterior_overlap_regions(logits,META,source_frames=1600)
        self.assertFalse(hard)
        self.assertTrue(soft)
        self.assertTrue(np.allclose(probability[:10],.6))
        self.assertEqual(metadata['cutoff'],.5)
    def test_most_likely_pair_alone_does_not_override_larger_solo_mass(self):
        value=np.array([1e-8,.2,.2,.2,.4,1e-8,1e-8],dtype=np.float32);value/=value.sum()
        logits=np.log(np.tile(value,(1,10,1)))
        hard,_=local_overlap_regions(logits,META,source_frames=1600)
        soft,_,_=posterior_overlap_regions(logits,META,source_frames=1600)
        self.assertTrue(hard)
        self.assertFalse(soft)
    def test_independent_sigmoid_or_unnormalized_outputs_are_rejected(self):
        with self.assertRaises(ValueError):posterior_overlap_regions(np.zeros((1,10,7),dtype=np.float32),META,source_frames=1600)
if __name__=='__main__':unittest.main()
