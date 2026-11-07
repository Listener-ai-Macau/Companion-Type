"""Data preservation at the future alignment boundary, not neural QA."""
import unittest
from practical_alignment_text_20261107 import source_text_spans

class OriginalTextBoundary(unittest.TestCase):
    def test_chinese_english_amount_and_surrogate_pair(self):
        original='🔊A区：价格3.14元，OK！'
        spans=source_text_spans(original,['A','区','价','格','314','元','OK'])
        self.assertEqual(''.join(row['text'] for row in spans),original)
        self.assertEqual(next(row['text'] for row in spans if row['alignmentUnit']=='314'),'3.14')
        self.assertEqual(spans[0]['textEndCodepoint'],2)
        self.assertEqual(spans[0]['textEndUtf16'],3)
        self.assertEqual(spans[-1]['text'],'OK！')
    def test_no_filler_er_or_negation_disappears(self):
        original=' 嗯，不是这儿。别改！ '
        spans=source_text_spans(original,['嗯','不','是','这','儿','别','改'])
        self.assertEqual(''.join(row['text'] for row in spans),original)
    def test_lexical_changes_duplicates_and_missing_tail_refuse(self):
        for original,units in [('各个区的',['哥','哥','去','掉']),('不批准',['批','准']),('嗯嗯',['嗯']),('APP',['app'])]:
            self.assertIsNone(source_text_spans(original,units))
    def test_empty_and_punctuation_only_keep_unavailable_explicit(self):
        self.assertEqual(source_text_spans('',[]),[])
        self.assertIsNone(source_text_spans('……',[]))
        with self.assertRaises(ValueError):source_text_spans('原文',[''])

if __name__=='__main__':unittest.main()
