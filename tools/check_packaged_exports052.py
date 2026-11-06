from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,os,subprocess,time,hashlib,copy,zipfile,xml.etree.ElementTree as ET
from PIL import Image
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');b=r/'docs/handoffs/20261106-material-exports052';exe=b/'windows-bin/companion-type.exe'
assert exe.is_file()
run=Path('E:/CodexData/Companion/.build-cache/windows051')/('packaged-exports052-'+str(time.time_ns()));run.mkdir(parents=True)
out=b/'packaged-format-check';out.mkdir(exist_ok=False)
source=max((p for p in b.glob('native-files-*') if (p/'public-session.json').exists()),key=lambda p:p.stat().st_mtime)
rows=json.loads((source/'public-session.json').read_text(encoding='utf8'));row=rows[0]
for key in ['audioPath','deviceRecordingId','deviceRecordingKey','deviceTotalLength','deviceSha256','sourceDeviceId','recorderControl','meetingTracks']:row[key]=None
row.update(audioStored=False,audioBytes=0,chunks=[],status='minutesReady',source='importedTranscript',pendingReason=None,captureIncomplete=False,recorderControlUncertain=False)
row['retention']['audioCached']=False;row['recovery'].update(intent='none',stage='idle',nextRetryAtUnixMs=None)
row['title']='公开虚构样例·项目汇报与交付复盘'
body='AI 材料（请核对）｜项目汇报\n含人工编辑\n虚构文件导出排版样例，非真实会议或模型结果。\n## 采购状态\n尚未批准20%的追加费用。李明将在11月8日前核对差额，确认后再决定是否采购。\n## 后续安排\n'
body+='\n'.join(f'{i:02d}. 本项仅为分页与字符保留的虚构测试。请核对负责人、20%差额与11月8日的条件，不能把待确认事项改为已批准。' for i in range(1,26))
body+='\n## A '+('长标题校验'*8)+'\nThis purchase has not been approved. Keep the conditions and the original quotation.\n## 原文依据\n原文依据：尚未确认采购。不是已批准，也没有新增承诺。'
assert len(body)<4000
row['meetingNotes'][0]['text']=body
state=run/'sessions.json';state.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8');(run/'recordings').mkdir();(run/'settings.json').write_text('{}',encoding='utf8')
env=os.environ.copy();env.update(COMPANION_TYPE_STATE_PATH=str(state),COMPANION_TYPE_RECORDING_DIR=str(run/'recordings'),COMPANION_TYPE_PRODUCT_SETTINGS_PATH=str(run/'settings.json'),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1')
selection={'minutes':False,'transcript':False,'highlights':False,'timeline':False,'noteIds':[row['meetingNotes'][0]['id']]}
results=[]
for format in ['pptx','png','mindmap']:
    request={'sessionId':row['id'],'meetingMode':'offlineStore','format':format,'contentSections':selection}
    req=run/(format+'.json');req.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8');dest=out/('saved-material.'+('mm' if format=='mindmap' else format))
    started=time.perf_counter();p=subprocess.run([str(exe),'--meeting-export-request',str(req),str(dest)],cwd=exe.parent,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=220,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    (out/(format+'.log')).write_text(p.stdout+p.stderr,encoding='utf8');assert p.returncode==0,(format,p.stdout,p.stderr)
    assert dest.is_file();results.append({'format':format,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'wallSeconds':round(time.perf_counter()-started,3)})
    if format=='pptx':
        with zipfile.ZipFile(dest) as z:
            names=[n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')];assert len(names)>5
            text=''.join(''.join(ET.fromstring(z.read(n)).itertext()) for n in names)
            for expected in ['尚未批准20%的追加费用。','原文依据：尚未确认采购。','虚构文件导出排版样例','This purchase has not been approved.']:
                assert ''.join(expected.split()) in ''.join(text.split()),expected
            assert 'UNSELECTED_PRIVATE_MATERIAL' not in text
    elif format=='png':
        with Image.open(dest) as image:assert image.format=='PNG';image.verify()
    else:
        values=[n.get('TEXT') for n in ET.parse(dest).iter('node')];assert '采购状态' in values and '原文依据' in values
for kind in ['stale','missing-material']:
    request={'sessionId':row['id'],'meetingMode':'offlineStore','format':'pptx','contentSections':copy.deepcopy(selection)}
    if kind=='stale':request['expectedContentHash']='0'*64
    else:request['contentSections']['noteIds']=['missing-material']
    req=run/(kind+'.json');req.write_text(json.dumps(request),encoding='utf8');dest=out/(kind+'.pptx')
    p=subprocess.run([str(exe),'--meeting-export-request',str(req),str(dest)],cwd=exe.parent,env=env,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    assert p.returncode!=0 and not dest.exists(),kind
current=json.loads(state.read_text(encoding='utf8'))[0]
for key in ['transcriptText','utterances','transcriptReview','meetingNotes','noteRevision','minutes','minutesByMode','bookmarks','bookmarkRevision']:assert row.get(key)==current.get(key),key
report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'FROZEN_RELEASE_ACTUAL_NATIVE_FORMATS_AND_SOURCE_GUARDS_PASSED',
    'exeSha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'sourceCommit':json.loads((b/'source-frozen.json').read_text(encoding='utf8'))['sourceCommit'],
    'files':results,'staleSourceRejected':True,'missingMaterialRejected':True,'publicSourceContentUnchanged':True,'ownerDataUsed':False,'modelInference':False,'deviceIo':False,
    'scope':'Actual frozen release EXE, isolated native persistence/export boundary, synthetic saved material. OS Save As/share sheet and PowerPoint application not exercised.'}
(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(report,ensure_ascii=False))
