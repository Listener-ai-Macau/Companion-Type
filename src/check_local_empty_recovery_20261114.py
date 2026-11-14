"""Verify generic recovery on the retained real native outputs; no new inference."""
from pathlib import Path
import ast, hashlib, json, unittest
from companion_local_decode_recovery_20261114 import recover_local_decode

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
CACHE=Path('E:/CodexData/Companion/.model-cache/local-bilingual-20261114/offline-session/decode')
read=lambda p:json.loads(p.read_text(encoding='utf-8'))

class RecoveryChecks(unittest.TestCase):
    def test_actual_chinese_english_nonempty_tokens_preserved_without_inference(self):
        for block in ['00000000-00480000-final','00000001-00480000-final']:
            raw=read(CACHE/block/'root.json')['raw']
            def forbidden(*args):raise AssertionError('Do not rerun or rewrite an already valid decode')
            leaves=recover_local_decode(raw['startSample'],raw['endSample'],infer=forbidden,
                        load=lambda key:raw,save=forbidden,language_mode='auto')
            self.assertEqual(leaves[0]['raw'],raw)
            self.assertFalse(leaves[0]['reviewRequired'])

    def test_actual_empty_parent_is_retained_and_each_sample_reexamined_once(self):
        raw=read(CACHE/'00000002-00480000-final/root.json')['raw']
        self.assertEqual(raw['text'],'');self.assertEqual(raw['language'],None)
        saved={};calls=[]
        def infer(start,end):
            calls.append((start,end))
            return {**raw,'startSample':start,'endSample':end,'text':'unchanged child words',
                    'language':'Chinese' if start==raw['startSample'] else 'English'}
        leaves=recover_local_decode(raw['startSample'],raw['endSample'],infer=infer,
                  load=lambda key:raw if key=='root' else saved.get(key),save=lambda key,value:saved.update({key:value}),language_mode='auto')
        self.assertEqual(calls,[(960000,1200000),(1200000,1440000)])
        self.assertEqual(raw['rawDecoded'],'language None<asr_text><|im_end|>')
        self.assertEqual([r['raw']['language'] for r in leaves],['Chinese','English'])
        self.assertEqual(sum(r['raw']['endSample']-r['raw']['startSample'] for r in leaves),480000)

    def test_ambiguous_background_is_explicit_at_original_bounds(self):
        calls=[]
        def infer(start,end):
            calls.append((start,end))
            return {'startSample':start,'endSample':end,'text':'','language':None,'generatedIds':[1],
                    'naturalEos':True,'exactDigitalSilence':False}
        leaves=recover_local_decode(0,480000,infer=infer,load=lambda key:None,save=lambda *args:None,language_mode='auto')
        self.assertEqual(len(calls),7)
        self.assertEqual(len(leaves),4)
        self.assertTrue(all(row['reviewRequired'] and row['raw']['text']=='' for row in leaves))
        self.assertEqual(sum(row['raw']['endSample']-row['raw']['startSample'] for row in leaves),480000)

    def test_zero_input_still_skips_without_relabeling_noise(self):
        raw={'startSample':0,'endSample':16000,'text':'','language':None,'generatedIds':[],
             'naturalEos':None,'exactDigitalSilence':True}
        leaves=recover_local_decode(0,16000,infer=lambda *args:raw,load=lambda key:None,save=lambda *args:None,language_mode='auto')
        self.assertFalse(leaves[0]['reviewRequired'])

    def test_native_infer_function_ast_unchanged_from_executed_r1(self):
        old=ROOT/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/r1-source/companion_local_qwen_worker_20261114.py'
        current=ROOT/'model-research/src/companion_local_qwen_worker_20261114.py'
        def infer(path):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            return next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='infer')
        self.assertEqual(ast.dump(infer(old)),ast.dump(infer(current)))

if __name__=='__main__':unittest.main(verbosity=2)
