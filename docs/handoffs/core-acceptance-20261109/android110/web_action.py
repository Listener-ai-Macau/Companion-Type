from pathlib import Path
import json,sys,time,os
P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6/web-control')
request=json.loads(sys.argv[1]);number=max([int(p.stem.split('-')[1]) for p in P.glob('request-*.json')]+[0])+1
path=P/f'request-{number:03}.json';temp=path.with_suffix('.tmp');temp.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8');os.replace(temp,path)
if '--no-wait' in sys.argv:print(json.dumps({'queued':path.name}));sys.exit(0)
reply=P/path.name.replace('request-','reply-');deadline=time.monotonic()+25
while time.monotonic()<deadline:
 if reply.exists():print(reply.read_text(encoding='utf8'));sys.exit(0)
 if (P/'failure.json').exists():raise RuntimeError('Own WebView worker stopped; retained private failure')
 time.sleep(.1)
print(json.dumps({'pending':path.name,'nativePickerMayBeOpen':True}))
