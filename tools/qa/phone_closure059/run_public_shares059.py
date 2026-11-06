from pathlib import Path
import hashlib,json,re,shlex,subprocess,sys,time
W=Path(__file__).parent;C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059');D=C/'shared';D.mkdir(exist_ok=True)
PRE=['C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe','-s','6LCAPVHE9PBE45DU']
QA='com.denzic.companion.shareqa056';APP='com.denzic.companion.app';KEY='0102030405060708090a0b0c:1122334455667788:f056'
def cmd(args,binary=False):
    p=subprocess.run(list(map(str,args)),cwd=W.parent,capture_output=True,timeout=50)
    assert p.returncode==0,p.stdout.decode('utf8',errors='replace')+p.stderr.decode('utf8',errors='replace')
    return p.stdout if binary else p.stdout.decode('utf8')
def shell(*args,binary=False):return cmd(PRE+['shell',' '.join(shlex.quote(str(x)) for x in args)],binary)
def receipts():return [x for x in shell('run-as',QA,'ls','files').splitlines() if re.fullmatch(r'\d+\.json',x)]
def web(*args):return json.loads(cmd(['C:/Program Files/nodejs/node.exe',W/'phone059_web.cjs',*args]))
def native(*args):return json.loads(cmd([sys.executable,W/'virtual_native059.py',*args]))
def collect(name):
    receipt=json.loads(shell('run-as',QA,'cat','files/'+name));assert receipt['readOnly'] and receipt['otherUriDenied'] and receipt['mime']==receipt['intentMime']
    data=cmd(PRE+['exec-out','run-as',QA,'cat','files/'+receipt['id']+'.payload'],binary=True)
    assert len(data)==receipt['bytes']==receipt['declaredBytes'] and hashlib.sha256(data).hexdigest()==receipt['sha256']
    source_file=shell('run-as',APP,'sh','-c','ls -td cache/companion-shared/*/manifest.json').splitlines()[0]
    assert re.fullmatch(r'cache/companion-shared/[0-9a-f-]{36}/manifest.json',source_file)
    source=json.loads(shell('run-as',APP,'cat',source_file));assert source['key']==KEY and source['sha256']==receipt['sha256'] and source['filename']==receipt['filename'] and source['mime']==receipt['mime']
    destination=D/('QA059-'+receipt['id']+Path(receipt['filename']).suffix);destination.write_bytes(data)
    item={'receipt':receipt,'sourceManifest':source,'sourceManifestSha256':hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),'actualRecipientBytesMatchSource':True,'local':str(destination),'mainDisplayInput':False}
    (D/(receipt['id']+'-receipt.json')).write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf8');return item
out=C/'actual-share-receipts.json';items=json.loads(out.read_text(encoding='utf8')) if out.exists() else []
# Resume already completed UI steps; the receiver can publish its durable
# receipt just after accessibility reports that its chooser tap was injected.
existing=receipts();known={x['receipt']['id']+'.json' for x in items}
pending=set(existing)-known;assert len(pending)<=1,pending
if pending:
    value=collect(pending.pop());suffix=Path(value['receipt']['filename']).suffix
    kind={'.pdf':'pdf','.docx':'word','.txt':'txt','.md':'markdown','.pptx':'pptx','.xlsx':'xlsx','.mm':'mindmap','.png':'png'}[suffix]
    items.append({'format':kind,**value});out.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf8')
for kind in ['txt','markdown','word','pptx','xlsx','mindmap','png']:
    if any(x['format']==kind for x in items):continue
    before=set(receipts());shell('am','start','--display','2','-n',APP+'/.MainActivity')
    state=web('format',kind);assert len(state['selectedSections'])==4
    web('click','分享文件');native('tap','Companion 本机分享验收')
    until=time.monotonic()+8
    while True:
        after=set(receipts());created=after-before
        if created:break
        assert time.monotonic()<until,'Actual recipient did not publish a receipt'
        time.sleep(.15)
    assert len(created)==1,(before,after)
    item={'format':kind,**collect(created.pop())};items.append(item)
    (C/'actual-share-receipts.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'format':kind,'bytes':item['receipt']['bytes'],'shaMatchesProducer':True,'readOnly':True,'ungrantedUriDenied':True}),flush=True)
clipboard=[x for x in shell('run-as',QA,'ls','files').splitlines() if re.fullmatch(r'clipboard-\d+\.json',x)]
assert clipboard
clip=json.loads(shell('run-as',QA,'cat','files/'+clipboard[-1]));text=cmd(PRE+['exec-out','run-as',QA,'cat','files/'+clip['id']+'.txt'],binary=True).decode('utf8')
assert hashlib.sha256(text.encode()).hexdigest()==clip['sha256'] and '追加20%的费用尚未批准。' in text
(D/'actual-clipboard.txt').write_text(text,encoding='utf8');(D/'actual-clipboard-receipt.json').write_text(json.dumps(clip,indent=2),encoding='utf8')
print('ALL_EIGHT_ACTUAL_CHOOSER_RECIPIENTS_AND_PUBLIC_CLIPBOARD_VERIFIED',flush=True)
