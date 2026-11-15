"""Transport/content preservation tests. No mock result is an ASR quality pass."""
from pathlib import Path
import hashlib, json, subprocess, sys, tempfile, unittest, uuid, wave
from companion_local_pcm_session_20261114 import PcmSession, SessionConflict, exclusive_file, parse_generated_tokens

class LocalSessionChecks(unittest.TestCase):
    def setUp(self):
        scratch=Path('C:/Users/Billy/Documents/Codex/2026-11-14/xu-y/work')
        self.temp=tempfile.TemporaryDirectory(prefix='local-pcm-check-',dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def create(self,name='session',**kwargs):
        return PcmSession.create(self.root/name,recording_id=str(uuid.uuid4()),**kwargs)

    def feed(self,session,pcm,sizes):
        offset=0
        for size in sizes:
            part=pcm[offset:offset+size]
            if part:
                session.append(offset//2,part);offset+=len(part)
        if offset<len(pcm):session.append(offset//2,pcm[offset:])

    def test_arbitrary_packet_boundaries_match_offline_and_preserve_all_pcm(self):
        pcm=bytes(range(256))*512 #4.096s; includes quiet and non-speech samples
        stream=self.create('stream',block_seconds=2,draft_seconds=1)
        self.feed(stream,pcm,[318,16002,2020,28000,64000])
        stream.seal(len(pcm)//2)
        offline=self.create('offline',block_seconds=2,draft_seconds=1)
        offline.append(0,pcm);offline.seal(len(pcm)//2)
        a=stream.pending();b=offline.pending()
        self.assertEqual([(j['startFrame'],j['endFrame'],j['pcmSha256']) for j in a],
                         [(j['startFrame'],j['endFrame'],j['pcmSha256']) for j in b])
        self.assertEqual(stream.audio.read_bytes(),pcm)
        actual=b''
        for job in a:actual+=stream.read_request_pcm(job)
        self.assertEqual(actual,pcm)
        self.assertFalse(list(stream.root.rglob('*.wav')), 'Drafts must not duplicate growing audio windows')

    def test_duplicate_partial_overlap_gap_and_conflicting_retransmission(self):
        session=self.create();session.append(0,b'\x01\x02'*100)
        self.assertTrue(session.append(0,b'\x01\x02'*100)['duplicate'])
        self.assertEqual(session.append(50,b'\x01\x02'*100)['newFrames'],50)
        before=session.audio.read_bytes()
        with self.assertRaises(SessionConflict):session.append(151,b'\x01\x02')
        with self.assertRaises(SessionConflict):session.append(10,b'\xff\x00')
        self.assertEqual(before,session.audio.read_bytes())

    def test_fsynced_unconfirmed_and_odd_crash_tail_needs_matching_replay(self):
        session=self.create();session.append(0,b'\x01\x02'*100)
        with session.audio.open('ab') as file:file.write(b'\x03\x04\x05')
        self.assertEqual(session.reconcile()['unconfirmedTailBytes'],3)
        with self.assertRaises(SessionConflict):session.seal(100)
        with self.assertRaises(SessionConflict):session.append(100,b'\x09\x04\x05\x06')
        self.assertEqual(session.append(100,b'\x03\x04\x05\x06')['newFrames'],2)
        session.seal(102)
        self.assertTrue(session.state()['sealed'])

    def test_eos_rejects_missing_tail_and_new_audio_but_accepts_exact_duplicate(self):
        session=self.create();session.append(0,b'\0\0'*100)
        with self.assertRaises(SessionConflict):session.seal(101)
        self.assertFalse(session.state()['sealed'])
        session.seal(100)
        self.assertTrue(session.append(0,b'\0\0'*100)['duplicate'])
        with self.assertRaises(SessionConflict):session.append(100,b'\0\0')

    def test_drafts_replace_one_block_and_final_waits_for_every_accepted_block(self):
        session=self.create(block_seconds=3,draft_seconds=1)
        session.append(0,b'\x01\x00'*16000)
        first=session.pending()[0]
        def save(job,text,accepted=True):
            session.save_result(job,{'text':text,'rawGeneratedIds':[1,1,1],'language':'Chinese,English','accepted':accepted},inference_binding={'frozen':'same'})
        save(first,'对对对 English English')
        self.assertFalse(session.document()['isFinal'])
        session.append(16000,b'\x01\x00'*16000)
        save(session.pending()[0],'对对对 English English 中文')
        self.assertEqual(session.document()['text'],'对对对 English English 中文')
        self.assertEqual(len(session.document()['utterances']),1)
        session.append(32000,b'\x01\x00'*32000)
        jobs=session.pending();self.assertEqual(len(jobs),2)
        save(jobs[0],'对对对 English English 中文')
        save(jobs[1],'tail')
        session.seal(64000)
        self.assertFalse(session.document()['isFinal']) #tail still only a draft
        tail=session.pending()[0];self.assertTrue(tail['blockFinal']);save(tail,'tail',accepted=False)
        self.assertFalse(session.document()['isFinal'])
        self.assertIn('English English',session.document()['text'])

    def test_complete_contiguous_final_results_keep_repeated_content(self):
        session=self.create(block_seconds=1,draft_seconds=1)
        session.append(0,b'\x02\x00'*32000);session.seal(32000)
        for job in session.pending():
            session.save_result(job,{'text':'yes yes 对对对','rawGeneratedIds':[4]*3,'accepted':True},inference_binding={'weights':'pinned'})
        document=session.document();self.assertTrue(document['isFinal'])
        self.assertEqual(document['text'],'yes yes 对对对\nyes yes 对对对')
        self.assertEqual(document['finalDecodedFrames'],32000)
        self.assertFalse(document['speakerIdentityVerified'])

    def test_model_binding_mismatch_and_completed_result_overwrite_are_rejected(self):
        session=self.create(block_seconds=1,draft_seconds=1)
        session.append(0,b'\x02\x00'*32000);session.seal(32000)
        jobs=session.pending();result={'text':'unmodified','rawGeneratedIds':[2],'accepted':True}
        session.save_result(jobs[0],result,inference_binding={'model':'one'})
        with self.assertRaises(SessionConflict):session.save_result(jobs[0],{**result,'text':'replacement'},inference_binding={'model':'one'})
        session.save_result(jobs[1],result,inference_binding={'model':'two'})
        with self.assertRaises(SessionConflict):session.document()

    def test_intake_lock_is_released_by_os_after_process_exit(self):
        session=self.create()
        script='import sys,os;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from companion_local_pcm_session_20261114 import exclusive_file;\nwith exclusive_file(Path(sys.argv[2])): os._exit(0)'
        subprocess.run([sys.executable,'-c',script,str(Path(__file__).parent),str(session.root/'intake.lock')],check=True)
        session.append(0,b'\0\0')
        with exclusive_file(session.root/'intake.lock'):
            with self.assertRaises(SessionConflict):session.append(1,b'\0\0')

    def test_protocol_language_extraction_does_not_collapse_repeated_words(self):
        class Tokenizer:
            def convert_tokens_to_ids(self,value):return 99
            def decode(self,ids,**kwargs):
                mapping={1:'language English',2:'language None',99:'',3:'yes ',4:'对',5:'language English is spoken'}
                return ''.join(mapping[i] for i in ids)
        tokenizer=Tokenizer()
        parsed=parse_generated_tokens([1,99]+[3]*25+[4]*4,tokenizer)
        self.assertEqual(parsed['text'],'yes '*25+'对'*4)
        self.assertEqual(parsed['language'],'English')
        self.assertEqual(parse_generated_tokens([2,99,3],tokenizer)['text'],'yes ')
        self.assertEqual(parse_generated_tokens([5],tokenizer)['text'],'language English is spoken')
        self.assertEqual(parse_generated_tokens([3,3],tokenizer,language='English')['text'],'yes yes ')

if __name__=='__main__':unittest.main(verbosity=2)
