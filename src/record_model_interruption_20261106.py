"""Retain a real system interruption; never turn stale RUNNING into success."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,psutil,subprocess,xml.etree.ElementTree as ET,shutil
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');m=r/'docs/handoffs/20261105-model-resume';control=m/'full-L-run'
target=control/'interruption-observed-20261106.json';assert not target.exists()
run=json.loads((control/'full-L-native-20261105.json').read_text(encoding='utf8'))
assert not psutil.pid_exists(20220) and not psutil.pid_exists(30608)
q='*[System[(EventID=41 or EventID=6005 or EventID=6006 or EventID=1074 or EventID=6008)]]'
p=subprocess.run(['C:/Windows/System32/wevtutil.exe','qe','System','/q:'+q,'/c:10','/rd:true','/f:xml'],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
s=p.stdout.decode('utf-8-sig',errors='replace');s=s[s.find('<'):];xml=ET.fromstring('<Events>'+s+'</Events>');ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
events=[]
for ev in xml:
    events.append({'id':int(ev.find('e:System/e:EventID',ns).text),'utc':ev.find('e:System/e:TimeCreated',ns).attrib['SystemTime'],
        'provider':ev.find('e:System/e:Provider',ns).attrib['Name'],
        'data':{d.attrib.get('Name',str(i)):d.text for i,d in enumerate(ev.findall('e:EventData/e:Data',ns))}})
raw=(control/'full-L-native-20261105-resources.jsonl').read_bytes()
samples=[json.loads(line) for line in raw.splitlines() if line.startswith(b'{') and line.endswith(b'}')]
state=json.loads((control/'results/L_R003S01C02-20261105-r16/state.json').read_text(encoding='utf8'))
report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'INCOMPLETE_WHOLE_MEETING_INTERRUPTED_BY_UNEXPECTED_SYSTEM_RESTART_NO_QUALITY_RESULT',
    'bootTime':datetime.fromtimestamp(psutil.boot_time()).astimezone().isoformat(),'events':events,'lastCompleteResourceSample':samples[-1],
    'observedPreRestartPeakPrivateBytes':max(x['processFamilyPrivateBytes'] for x in samples),'lastDurableWorkerPhase':state['state'],
    'generatedTokens':state['generatedTokens'],'resourceLogNulBytes':raw.count(bytes([0])),
    'rawRunReceiptRetainedUnedited':True,'cause':'Kernel-Power41 and EventLog6008 confirm unexpected system restart; bugcheck0/no dump does not identify cause. Last sampled RAM is not proof that hardware/driver/RAM was healthy at failure.',
    'eosCompleted':False,'accuracyResult':None,'sameConditionsAutomaticRetry':False}
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(m/'scoring-original-pip-check-failure-20261106.json').write_text(json.dumps({'exitCode':1,'state':'INHERITED_GLOBAL_DEPENDENCIES_CONFLICT',
    'issues':['gradio4.8.0 requires numpy~=1.0; inherited scoring numpy2.4.6','global transformers4.35.0 incompatible inherited hub1.25.1/tokenizers0.23.1'],
    'scoringParserAlreadyPassed':True,'resolution':'Create separate clean venv without system-site-packages; no edits to global or inference runtime.'},indent=2)+'\n',encoding='utf8')
print(json.dumps({k:report[k] for k in ['state','bootTime','lastCompleteResourceSample','lastDurableWorkerPhase','accuracyResult']},ensure_ascii=False))
