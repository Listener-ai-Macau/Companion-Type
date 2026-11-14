from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,threading,os,subprocess,sys,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
real=False
assert '--configured-service'not in sys.argv
Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/software-value20261114')/('native148-real-service-unused'if real else'native148-r1');Q.mkdir(exist_ok=False)
calls=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  request=json.loads(self.rfile.read(int(self.headers['Content-Length'])));assert self.path=='/v1/chat/completions'
  source=json.loads(request['messages'][-1]['content']);assert '明确虚构工程检查' in source['question'] and '追加20%的费用尚未批准' in source['transcript']
  calls.append(dict(question=source['question'],transcriptSha256=hashlib.sha256(source['transcript'].encode()).hexdigest()))
  data=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'items':[{'answer':'小王负责周五前核对采购清单；追加20%的费用尚未批准，需要书面确认。','quote':'追加20%的费用尚未批准，需要书面确认。'}]},ensure_ascii=False)}}]},ensure_ascii=False).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
# Keep the original isolated-station/job/resource/process-close framework. Only
# the scoped service fixture and the UI check module differ. No production hook.
p=S/'tools/qa/core_acceptance20261109/windows_meeting.py';source=p.read_text(encoding='utf8')
needle="  reopen_from=os.environ.get('COMPANION_ACCEPTANCE_REOPEN_FROM_EVIDENCE')"
assert source.count(needle)==1
if real:
 assert os.environ.get('DEEPSEEK_API_KEY')
 source=source.replace(needle,"  env.update(DEEPSEEK_API_KEY=os.environ['DEEPSEEK_API_KEY'],DEEPSEEK_BASE_URL=os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com/v1'),DEEPSEEK_MODEL=os.environ.get('DEEPSEEK_MODEL','deepseek-v4-flash'),COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED='1',COMPANION_ACCEPTANCE_REAL_AI_FUNCTIONAL='1')\n"+needle)
else:source=source.replace(needle,"  env.update(DEEPSEEK_API_KEY='explicit-fictional-loopback-only',DEEPSEEK_BASE_URL='http://127.0.0.1:"+str(server.server_port)+"/v1',DEEPSEEK_MODEL='explicit-local-fixture',COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED='1')\n"+needle)
needle="S/'tools/qa/core_acceptance20261109/windows_meeting_ui.cjs'";assert source.count(needle)==2;source=source.replace(needle,repr(str(W/'software_material_title148_ui.cjs')))
env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(Q/'product'),'COMPANION_ACCEPTANCE_CACHE':str(Q/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(R/'docs/handoffs/20261112-product-closure/windows148/windows-verification.json'),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':json.loads((R/'docs/handoffs/20261112-product-closure/windows148/windows-verification.json').read_bytes())['nativeRoot'],'COMPANION_ACCEPTANCE_OWNER_PREFLIGHT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1','NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'}
runner=Q/'scoped-runner.py';runner.write_text('import sys\nsys.path.insert(0,'+repr(str(p.parent))+')\n__file__='+repr(str(p))+'\n'+source,encoding='utf8')
try:
 with(Q/'runner.log').open('xb')as log:run=subprocess.run([sys.executable,str(runner),'--stage','product-background'],env=env,cwd=S,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 assert run.returncode==0,(Q/'runner.log').read_text(encoding='utf8',errors='replace')[-2500:]
 cases=list((Q/'product/docs/handoffs/20261109-core-acceptance').iterdir());assert len(cases)==1
 proof=cases[0]/'result.json';result=json.loads(proof.read_bytes());assert result['ui']['state']=='ACTUAL_NATIVE_ASSISTANT_SAVE_EXACT_EXPORT_PASSED'and result['processRestart']['previousAppExited']and len(calls)==(0 if real else 1)
 receipt=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='NORMAL148_NATIVE_ASSISTANT_SAVE_EXPORT_PROCESS_REOPEN_PASSED',evidence=str(proof),localFictionalServiceReplies=len(calls),configuredActualTextServiceUsed=real,modelServiceOrSpeechRun=real,speechAsrRun=False,source='Explicit fictional purchase meeting text; no private recordings or real audio.',actualNativeUiStorageExportAndReopen=True,ownerDesktopOperated=False,ordinaryRecipientRetested=False,saleQualified=False)
 (Q/'result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt,ensure_ascii=False))
finally:
 server.shutdown();(Q/'local-fixture-calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2),encoding='utf8')
