import tempfile,unittest
from pathlib import Path
import numpy as np
from bounded_speaker_20261107 import bounded_votes,checked_cache,publish_cache,speaker_intervals,windows

class BoundedSpeaker(unittest.TestCase):
    def test_direct_votes_equal_dense_author_relabel_including_local_merge(self):
        meta={'window_size':10,'window_shift':2,'receptive_field_shift':2}
        labels=np.array([[[1,1,0],[1,0,0],[0,1,0],[0,0,1],[0,0,0]],[[1,0,0],[1,1,0],[0,1,0],[0,0,1],[0,0,1]],[[0,0,1],[1,0,0],[1,0,0],[0,1,0],[0,0,0]]],dtype=np.uint8)
        pairs=[[w,s] for w in range(3) for s in range(3)];groups=np.array([0,0,1,0,2,1,2,0,1])
        actual,expected,receipt=bounded_votes(labels,pairs,groups,meta,13)
        dense=[]
        for window in range(3):
            expanded=np.zeros((5,3),dtype=np.int32)
            for speaker in range(3):expanded[:,groups[window*3+speaker]]|=labels[window,:,speaker]
            dense.append(expanded)
        votes=np.zeros((8,3),dtype=np.int32);counts=np.zeros(8);weights=np.zeros(8)
        for i,value in enumerate(dense):votes[i:i+5]+=value;counts[i:i+5]+=labels[i].sum(axis=1);weights[i:i+5]+=1
        np.testing.assert_array_equal(actual,votes[:7]);np.testing.assert_array_equal(expected,((counts/(weights+1e-12))+.5).astype(np.int32)[:7])
        self.assertFalse(receipt['expandedWindowMatricesAllocated']);self.assertEqual(actual.dtype,np.uint8)
    def test_clean_frames_and_last_frame_sample_rule_are_preserved(self):
        labels=np.zeros((1,12,3),dtype=np.uint8);labels[0,:,0]=1
        meta={'window_size':120,'window_shift':12}
        pairs,runs=speaker_intervals(labels,meta);self.assertEqual(pairs,[[0,0]]);self.assertEqual(runs,[[[0,110]]])
        labels[0,:3,1]=1
        self.assertEqual(speaker_intervals(labels,meta),([],[]))
    def test_complete_input_window_schedule_includes_padded_tail(self):
        self.assertEqual(windows(10,10,1),[0]);self.assertEqual(windows(13,10,2),[0,2,4]);self.assertEqual(windows(14,10,2),[0,2,4])
    def test_resume_ignores_uncommitted_tail_but_refuses_changed_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'segment.json';array=np.lib.format.open_memmap(path.with_suffix('.npy'),mode='w+',dtype=np.float32,shape=(3,2));array[0]=[1,2]
            publish_cache(path,array,1,{'input':'frozen'},{'state':'PARTIAL'})
            array[2]=[99,98];array.flush();loaded,record=checked_cache(path,{'input':'frozen'});self.assertEqual(record['done'],1)
            array[0,0]=3;array.flush()
            with self.assertRaises(AssertionError):checked_cache(path,{'input':'frozen'})
            del loaded,array

if __name__=='__main__':unittest.main()
