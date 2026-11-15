import unittest
from companion_word_journal_join_20261109 import provider_words,joined_words,refine_recovered_words

class WordConservationTests(unittest.TestCase):
    def word(self,start=0,end=1):
        return {'id':'0:0','text':'不是','start':start,'end':end,'speaker':'provider-1'}

    def test_missing_sentence_keeps_actual_word_tokens(self):
        document={'result':{'utterances':[{'words':[{'text':'不是','start_time':0,'end_time':1000}],'additions':{'speaker_id':'0'}}]}}
        words=provider_words(document,1)
        self.assertEqual([(x['text'],x['textSource'],x['speaker']) for x in words],[('不是','utterance.words','0')])

    def test_duplicate_spans_do_not_create_a_false_winner_or_duplicate_words(self):
        word=self.word();journal=[{'start':0,'end':1,'speaker':'a'},{'start':0,'end':1,'speaker':'a'},{'start':0,'end':1,'speaker':'b'}]
        rows=joined_words([word],journal,0)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['text'],'不是')
        self.assertEqual(rows[0]['speaker'],'unattributed:overlap')

    def test_gap_does_not_borrow_a_neighboring_person(self):
        rows=joined_words([self.word(1,2)],[{'start':0,'end':1,'speaker':'a'}],0)
        self.assertEqual(rows[0]['speaker'],'unattributed:no_voice')
        self.assertEqual(rows[0]['text'],'不是')

    def test_zero_duration_word_survives_as_unattributed(self):
        rows=joined_words([self.word(1,1)],[{'start':0,'end':2,'speaker':'a'}],0)
        self.assertEqual(rows[0]['speaker'],'unattributed:zero_duration')
        self.assertEqual(rows[0]['id'],'0:0')

    def test_refinement_changes_only_recovered_words_with_single_voice_evidence(self):
        words=[dict(self.word(),textSource='utterance.text'),
               dict(self.word(1,2),id='1:0',speaker='0',textSource='utterance.words'),
               dict(self.word(2,3),id='2:0',speaker='0',textSource='utterance.words')]
        journal=[{'start':0,'end':3,'speaker':'a'},{'start':2,'end':3,'speaker':'b'}]
        rows,proof=refine_recovered_words(words,joined_words(words,journal,0))
        self.assertEqual([x['speaker'] for x in rows],['provider-1','provider-1','0'])
        self.assertEqual([x['text'] for x in rows],['不是']*3)
        self.assertEqual(proof['aliases'],{'a':'provider-1'})

if __name__=='__main__':
    unittest.main()
