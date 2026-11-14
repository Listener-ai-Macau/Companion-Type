from pathlib import Path
import json,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109'
p=A/'apps/mobile/src/App.tsx';raw=p.read_bytes();text=raw.decode()
old="<RecordingContentNavigation value={detailTab} onChange={selectDetailTab} preview={readingPreview} onAsk="
new="""<RecordingContentNavigation value={detailTab} onChange={selectDetailTab} preview={readingPreview} onOrganize={detail?.minutes?()=>{if(busy||updateRunning)return;const panel=document.querySelector<HTMLDetailsElement>('.existing-minutes');if(panel){panel.open=true;panel.scrollIntoView({block:'start'});}}:undefined} onAsk="""
assert text.count(old)==1;text=text.replace(old,new)
anchor=text.index('id="detail-panel-minutes"');start=text.index('<div className="section-heading">',anchor);end=text.index('{!detail.minutes&&detail.transcript&&<MeetingAssistant',start)
removed=text[start:end];assert '<h2>纪要</h2>'in removed and '打开 AI 助手' in removed and '整理方式' in removed
text=text[:start]+'<h2 className="minutes-panel-heading">纪要</h2>'+text[end:];assert p.read_bytes()==raw;p.write_bytes(text.encode())
g=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
paths=['apps/mobile/src/App.tsx','apps/mobile/src/RecordingContentNavigation.tsx','apps/mobile/src/notebookMobile.css']
subprocess.run(g+['add','--',*paths],cwd=A,check=True);subprocess.run(g+['diff','--cached','--check','--',*paths],cwd=A,check=True);subprocess.run(g+['commit','--only','-m','Give phone notes priority and gather occasional actions in one menu','--',*paths],cwd=A,check=True)
p=R/'docs/handoffs/20261110-android-media-import/android156/source.json';d=json.loads(p.read_bytes());d['frontendSourceCommit']=subprocess.check_output(g+['rev-parse','HEAD'],cwd=A,text=True).strip();d['frontendScope']='Shared notebook palette and compact real-app reading header/player; one more-menu owns meeting tools, unchanged native model and recording logic.';p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['frontendSourceCommit'])
