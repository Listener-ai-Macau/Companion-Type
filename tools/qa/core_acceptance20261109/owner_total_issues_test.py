import json,unittest
from owner_total_issues import REPORT,reported_issues

class Reports(unittest.TestCase):
 def test_individual_reports_preserve_step_version_and_exact_text(self):
  steps=[('连接',''),('回听','')];seen=set()
  def event(index,text,at):return dict(event='action_button|'+REPORT,processId=12,at=at,text=text,context=dict(version='0.1.114',stepIndex=index,stepTitle=steps[index][0]))
  events=[event(0,'连接有点慢\r\n但可以用','2026-11-12T13:10:10Z'),event(1,'播放按钮不好找','2026-11-12T13:12:10Z')];raw='\n'.join(map(json.dumps,events));rows=reported_issues(raw,12,0,'0.1.114',steps,seen)
  self.assertEqual([x['stepIndex']for x in rows],[0,1]);self.assertEqual(rows[0]['ownerQuote'],events[0]['text']);self.assertNotEqual(rows[0]['eventId'],rows[1]['eventId']);self.assertEqual(reported_issues(raw,12,0,'0.1.114',steps,seen),[])
 def test_wrong_window_version_step_and_stale_events_are_not_imported(self):
  steps=[('连接','')];good=dict(event='action_button|'+REPORT,processId=12,at='2026-11-12T13:10:10Z',text='一条问题',context=dict(version='0.1.114',stepIndex=0,stepTitle='连接'))
  for field,value in [('processId',13),('event','action_button|下一步')]:
   bad={**good,field:value};self.assertEqual(reported_issues(json.dumps(bad),12,0,'0.1.114',steps,set()),[])
  for field,value in [('version','0.1.113'),('stepIndex',True),('stepIndex',-1),('stepTitle','其它步骤')]:
   bad={**good,'context':{**good['context'],field:value}};self.assertEqual(reported_issues(json.dumps(bad),12,0,'0.1.114',steps,set()),[])
  self.assertEqual(reported_issues(json.dumps(good),12,9999999999,'0.1.114',steps,set()),[])
if __name__=='__main__':unittest.main()
