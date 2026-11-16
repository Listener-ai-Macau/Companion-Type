"""Non-neural regression checks for training masks, devices and recovery."""
from pathlib import Path
import json
import random
import struct
import sys
import tempfile
import unittest
from meeting_acoustic_contract_20261116 import (
    accepted_output, balanced_order, committed_checkpoint, padded_labels, select_gpu,
    tensor_header, write_float_checkpoint,
    sha,
)


class ContractTests(unittest.TestCase):
    def test_target_only_masks_for_unequal_left_and_right_padding(self):
        prefixes,targets = [[11,12],[11]], [[91,92],[93]]
        right = padded_labels(prefixes,targets,0,'right')
        left = padded_labels(prefixes,targets,0,'left')
        self.assertEqual(right['labels'],[[-100,-100,91,92],[-100,93,-100,-100]])
        self.assertEqual(left['labels'],[[-100,-100,91,92],[-100,-100,-100,93]])
        self.assertEqual(left['attention_mask'][1],[0,0,1,1])
        self.assertEqual(right['attention_mask'][1],[1,1,0,0])

    def test_eos_remains_supervised_even_if_pad_uses_same_id(self):
        result = padded_labels([[8,9],[8]],[[10,151645],[151645]],151645,'left')
        self.assertEqual(result['labels'][1],[-100,-100,-100,151645])
        self.assertEqual(result['attention_mask'][1],[0,0,1,1])
        with self.assertRaises(RuntimeError):
            padded_labels([[8]],[[]],0)

    def test_token_weighted_accumulation_uses_one_group_denominator(self):
        losses, gradients = [[1.,3.],[5.]], [[2.,6.],[10.]]
        total = sum(map(len,losses))
        accumulated_loss = sum(sum(x)/len(x)*(len(x)/total) for x in losses)
        accumulated_gradient = sum(sum(x)/len(x)*(len(x)/total) for x in gradients)
        self.assertAlmostEqual(accumulated_loss, sum(sum(x) for x in losses)/total)
        self.assertAlmostEqual(accumulated_gradient, sum(sum(x) for x in gradients)/total)
        self.assertNotEqual(accumulated_loss, sum(sum(x)/len(x) for x in losses)/2)

    def test_balanced_order_preserves_all_examples_and_global_rng(self):
        rows = [{'language':'English'} for _ in range(475)]+[{'language':'Chinese'} for _ in range(469)]
        state = random.getstate()
        order = balanced_order(rows,20261116)
        self.assertEqual(random.getstate(),state)
        self.assertEqual(order,balanced_order(rows,20261116))
        self.assertEqual(sorted(order),list(range(944)))
        self.assertTrue(all(rows[order[i]]['language'] != rows[order[i+1]]['language'] for i in range(0,938,2)))

    def test_gpu_selection_rejects_cpu_integrated_wrong_arch_and_duplicates(self):
        integrated = {'index':0,'name':'AMD Radeon780M','architecture':'gfx1103'}
        discrete = {'index':1,'name':'AMD Radeon RX 6800 XT','architecture':'gfx1030:sramecc-'}
        self.assertEqual(select_gpu([integrated,discrete])['index'],1)
        for devices in [[],[integrated],[dict(discrete,architecture='gfx1103')],[discrete,dict(discrete,index=2)]]:
            with self.assertRaises(RuntimeError):
                select_gpu(devices)

    def test_streamed_checkpoint_is_readable_by_independent_safetensors(self):
        from safetensors import safe_open
        with tempfile.TemporaryDirectory(prefix='companion-acoustic-contract-') as temp:
            root = Path(temp).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            path = root/'checkpoint.safetensors'
            data = {'weight/a':struct.pack('<4f',1.,2.,3.,4.),'exp_avg/a':struct.pack('<2f',.25,-.5)}
            receipt = write_float_checkpoint(path,[('weight/a',[2,2]),('exp_avg/a',[2])],
                                             lambda name,start,count:data[name][start*4:(start+count)*4])
            with safe_open(str(path),framework='numpy') as file:
                self.assertEqual(file.get_tensor('weight/a').tolist(),[[1.,2.],[3.,4.]])
                self.assertEqual(file.get_tensor('exp_avg/a').tolist(),[.25,-.5])
            header,offset = tensor_header(path)
            self.assertEqual(header['weight/a']['data_offsets'],[0,16])
            self.assertEqual(path.stat().st_size-offset,24)
            binding = {'packet':'fixed'}
            (root/'checkpoint.json').write_text(json.dumps(dict(receipt,file=path.name,binding=binding)))
            (root/'latest-checkpoint.json').write_text(json.dumps({'receipt':'checkpoint.json','binding':binding,
                                                                   'receiptSha256':sha(root/'checkpoint.json')}))
            self.assertEqual(committed_checkpoint(root,binding)[0],path)
            original_receipt = (root/'checkpoint.json').read_bytes()
            changed = json.loads(original_receipt); changed['completedExamples'] = 944
            (root/'checkpoint.json').write_text(json.dumps(changed))
            with self.assertRaises(RuntimeError):
                committed_checkpoint(root,binding)
            (root/'checkpoint.json').write_bytes(original_receipt)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(RuntimeError):
                committed_checkpoint(root,binding)

    def test_interrupted_checkpoint_is_never_a_committed_recovery(self):
        with tempfile.TemporaryDirectory(prefix='companion-acoustic-interrupted-') as temp:
            root = Path(temp).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            path = root/'interrupted.safetensors'
            def interrupted(*args):
                raise InterruptedError('controlled write interruption')
            with self.assertRaises(InterruptedError):
                write_float_checkpoint(path,[('weight/a',[2])],interrupted)
            self.assertFalse(path.exists())
            self.assertTrue(path.with_name(path.name+'.pending').exists())
            self.assertFalse((root/'latest-checkpoint.json').exists())

    def test_no_neural_runtime_needed_for_contract(self):
        self.assertNotIn('torch',sys.modules)

    def test_exact_zero_output_cannot_discard_recognized_words(self):
        zero = {'exactDigitalSilence':True,'text':'','generatedIds':[],
                'neuralInferencePerformed':False,'naturalEos':None}
        self.assertTrue(accepted_output(zero))
        self.assertFalse(accepted_output(dict(zero,text='quiet speech')))
        self.assertFalse(accepted_output(dict(zero,generatedIds=[10])))
        self.assertFalse(accepted_output({'naturalEos':False,'neuralInferencePerformed':True}))
        self.assertTrue(accepted_output({'naturalEos':True,'neuralInferencePerformed':True}))

    def test_large_checkpoint_is_split_into_bounded_host_chunks(self):
        with tempfile.TemporaryDirectory(prefix='companion-acoustic-chunks-') as temp:
            root = Path(temp).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            sizes = []
            def reader(name,start,count):
                sizes.append(count)
                return b'\x00'*(count*4)
            write_float_checkpoint(root/'large.safetensors',[('weight/a',[262145])],reader)
            self.assertEqual(sizes,[262144,1])

    def test_only_one_worker_can_hold_the_same_run(self):
        from meeting_acoustic_worker_20261116 import exclusive_run
        with tempfile.TemporaryDirectory(prefix='companion-acoustic-lock-') as temp:
            root = Path(temp).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            with exclusive_run(root):
                with self.assertRaises(OSError):
                    with exclusive_run(root):
                        self.fail('Second worker acquired the same run')
            with exclusive_run(root):
                pass


if __name__ == '__main__':
    unittest.main()
