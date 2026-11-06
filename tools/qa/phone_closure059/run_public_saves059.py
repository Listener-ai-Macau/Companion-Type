from pathlib import Path
import hashlib,json,subprocess,sys,time
W=Path(__file__).parent;C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059');D=C/'saved';D.mkdir(exist_ok=True)
A='C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';PRE=[A,'-s','6LCAPVHE9PBE45DU']
REMOTE='/sdcard/Download/Companion-QA-048/Companion-QA059'
def cmd(args):
    p=subprocess.run(list(map(str,args)),cwd=W.parent,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=50);assert p.returncode==0,p.stdout+p.stderr;return p.stdout
def web(*args):return json.loads(cmd(['C:/Program Files/nodejs/node.exe',W/'phone059_web.cjs',*args]))
def native(*args):return json.loads(cmd([sys.executable,W/'virtual_native059.py',*args]))
selected=web('select-public-content');assert len(selected['selectedSections'])==4,selected
records=[];out=C/'actual-saf-saves.json'
for kind,extension in [('txt','txt'),('markdown','md'),('word','docx'),('pdf','pdf'),('pptx','pptx'),('xlsx','xlsx'),('mindmap','mm'),('png','png')]:
    item={'format':kind,'filename':'QA059-all.'+extension,'scope':'Actual ordinary Android059 App selected public fixture minutes/transcript/notes/one edited AI material; not an ASR or AI quality test','startedAt':time.time()}
    try:
        changed=web('format',kind);assert changed['exportFormat']==kind
        web('click','保存文件')
        picker=native('dump');assert any(n['text']=='Companion-QA059' for n in picker['nodes']),picker
        assert any(n['id']=='android:id/title' and n['class']=='EditText' for n in picker['nodes']),picker
        native('setText','id:android:id/title',item['filename'])
        native('tap','保存')
        state=web('inspect');assert '文件已保存到你选择的位置。' in state['alerts'],state
        destination=D/item['filename'];cmd(PRE+['pull',REMOTE+'/'+item['filename'],destination]);data=destination.read_bytes();assert data
        phone_hash=cmd(PRE+['shell','sha256sum',REMOTE+'/'+item['filename']]).split()[0];assert hashlib.sha256(data).hexdigest()==phone_hash
        item.update(result='SAVED_BY_ACTUAL_SAF_AND_PULLED_BYTES_MATCH',bytes=len(data),sha256=phone_hash,local=str(destination),selectedSections=state['selectedSections'],mainDisplayInput=False)
    except Exception as error:
        item.update(result='FAILED_OR_INCOMPLETE',error=str(error));records.append(item);out.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8');raise
    records.append(item);out.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'format':kind,'result':item['result'],'bytes':item['bytes']},ensure_ascii=False),flush=True)
print('ALL_EIGHT_ACTUAL_SAF_SAVES_COMPLETE',flush=True)
