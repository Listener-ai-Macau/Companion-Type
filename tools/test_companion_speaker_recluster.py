import unittest
import numpy as np
from companion_speaker_recluster import constrained_average_link

class ReclusterTests(unittest.TestCase):
 def test_matching_voices_merge_and_different_voices_remain_separate(self):
  labels=constrained_average_link(np.array([[1,0],[.99,.05],[0,1]],dtype=np.float32),np.zeros((3,3),bool))
  self.assertEqual(labels[0],labels[1]);self.assertNotEqual(labels[0],labels[2])
 def test_simultaneous_voices_cannot_be_rejoined_transitively(self):
  constraints=np.zeros((3,3),bool);constraints[0,2]=constraints[2,0]=True
  labels=constrained_average_link(np.array([[1,0],[1,0],[1,0]],dtype=np.float32),constraints)
  self.assertNotEqual(labels[0],labels[2])
 def test_zero_vector_is_not_assigned_a_person(self):
  with self.assertRaises(ValueError):constrained_average_link(np.zeros((1,2)),np.zeros((1,1)))

if __name__=='__main__':unittest.main()
