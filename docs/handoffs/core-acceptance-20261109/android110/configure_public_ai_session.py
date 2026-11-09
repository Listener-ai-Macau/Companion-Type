"""Ordinary UI configuration using the existing authorized service, no secret logs."""
from pathlib import Path
import json,os,time,urllib.parse
P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6/web-control')
def action(request,secret=False):
    number=max([int(p.stem.split('-')[1]) for p in P.glob('request-*.json')]+[0])+1
    path=P/f'request-{number:03}.json';temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8');os.replace(temporary,path)
    reply=path.with_name(path.name.replace('request-','reply-'))
    try:
        until=time.monotonic()+25
        while time.monotonic()<until:
            if reply.exists():
                value=json.loads(reply.read_text(encoding='utf8'))
                if value.get('error'):raise RuntimeError('Ordinary AI settings control failed; no credential printed')
                return value
            time.sleep(.1)
        raise RuntimeError('Ordinary AI settings control has not completed')
    finally:
        if secret:path.write_text(json.dumps({**request,'value':'[REDACTED_AFTER_ORDINARY_PASSWORD_FILL]'}),encoding='utf8')
state=action({'action':'inspect'});assert not any('停止' in s or '正在' in s for s in state['status']),'Do not interrupt the active public meeting job'
key=os.environ.get('DEEPSEEK_API_KEY','');assert key and '\n' not in key
base=os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com').rstrip('/')
parsed=urllib.parse.urlparse(base);assert parsed.scheme=='https' and parsed.hostname=='api.deepseek.com' and not parsed.username and not parsed.password
endpoint=base if base.endswith('/chat/completions') else base+'/chat/completions'
model=os.environ.get('DEEPSEEK_MODEL','deepseek-chat');assert model
action({'action':'click','role':'button','name':'设置','scope':'nav'})
action({'action':'fill','label':'AI服务密钥','value':key},secret=True)
action({'action':'click','selector':'.advanced-service > summary'})
action({'action':'fill','label':'AI服务地址','value':endpoint})
action({'action':'fill','label':'AI服务模型','value':model})
action({'action':'click','selector':'.service-remember input'})
action({'action':'click','role':'button','name':'保存服务配置'})
action({'action':'click','role':'button','name':'返回会议'})
print(json.dumps({'configuredThroughOrdinaryUI':True,'credentialPrinted':False,'remember':False,'scope':'Only current public meeting; process-local existing service credential'}))
