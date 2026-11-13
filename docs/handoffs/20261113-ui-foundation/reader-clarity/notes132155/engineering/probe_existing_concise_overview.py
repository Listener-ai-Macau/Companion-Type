from pathlib import Path
from datetime import datetime
import hashlib,json,os,re,time,requests
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055')
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
P=O/'public-source-full30-127';Q=O/'note-readability-overview-diagnosis-r3';Q.mkdir(exist_ok=False)
gate=json.loads((P/'text-reviewed-before-cloud.json').read_bytes());assert gate['allTextRead'] and gate['publicOnly']
saved=json.loads((P/'minutes.json').read_bytes());assert hashlib.sha256(saved['transcriptText'].encode()).hexdigest()==gate['transcriptSha256']
markdown=saved['minutesByMode']['offlineStore']['markdown'];summary=markdown.split('## Summary\n',1)[1].split('\n## ',1)[0]
items=[line[2:] for line in summary.splitlines() if line.startswith('- ')];assert 1<len(items)<500
source=(S/'apps/windows/src-tauri/src/backend/minutes/long_meeting.rs').read_text(encoding='utf8');function=source[source.index('fn request_concise_overview('):source.index('// Select existing source-backed')]
literal=re.search(r'let instruction = (".*");',function).group(1);instruction=json.loads(literal)
model=os.getenv('DEEPSEEK_MODEL','deepseek-v4-flash');base=os.getenv('DEEPSEEK_BASE_URL','https://api.deepseek.com/v1').rstrip('/')
body=dict(model=model,temperature=.1,messages=[dict(role='system',content=instruction),dict(role='user',content=json.dumps([dict(id=i,text=t)for i,t in enumerate(items)],ensure_ascii=False))],response_format=dict(type='json_object'),max_tokens=1024)
if model.lower().startswith('deepseek-'):body['thinking']=dict(type='disabled')
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),scope='One engineering diagnosis of unchanged native concise-overview request with the verified public-source saved summary. Not new app-generated minutes or ASR.',publicOnly=True,originalSavedStateChanged=False,itemCount=len(items),maxTokens=1024);start=time.monotonic()
try:
 response=requests.post(base+'/chat/completions',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']},json=body,timeout=30)
 record['statusCode']=response.status_code
 if response.status_code!=200:raise RuntimeError('service status '+str(response.status_code))
 payload=response.json();record['finishReason']=payload['choices'][0]['finish_reason'];record['usage']=payload.get('usage');content=payload['choices'][0]['message'].get('content','')
 (Q/'actual-public-response.txt').write_text(content,encoding='utf8')
 parsed=json.loads(content);points=parsed['overview'];record['pointCount']=len(points);record['characters']=[len(p['text'])for p in points];record['sourceIds']=[p['sources']for p in points]
 record['state']='ACTUAL_EXISTING_REQUEST_RETURNED'
except BaseException as error:
 record['state']='ACTUAL_EXISTING_REQUEST_FAILED';record['errorType']=type(error).__name__
finally:
 record['seconds']=round(time.monotonic()-start,3);(Q/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(record,ensure_ascii=False))
