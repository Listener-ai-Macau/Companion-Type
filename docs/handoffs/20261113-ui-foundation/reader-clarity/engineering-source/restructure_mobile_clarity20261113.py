from pathlib import Path
import shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';S=R/'companion-device-closure055';p=A/'apps/mobile/src/App.tsx';s=p.read_text(encoding='utf8')
start=s.index('{!readingPreview&&<details className="meeting-recording-tools"');end=s.index('<div ref={tabsAnchor}',start);tools=s[start:end];assert tools.endswith('</details>}');s=s[:start]+s[end:]
needle="<ContentExport key={'content-export:'";assert s.count(needle)==1;s=s.replace(needle,tools+'\n'+needle)
old='''{!readingPreview&&(detail?.transcript||aiContext?.available.some(scope=>scope.kind==='supplement'))&&<button type="button" className="detail-ai-entry" disabled={!!busy} onClick={()=>showReference('assistant')}>问这条录音 <span aria-hidden="true">↗</span></button>}''';assert s.count(old)==1;s=s.replace(old,'')
old='<RecordingContentNavigation value={detailTab} onChange={selectDetailTab} preview={readingPreview}/>';assert s.count(old)==1;s=s.replace(old,"<RecordingContentNavigation value={detailTab} onChange={selectDetailTab} preview={readingPreview} onAsk={!readingPreview&&(detail?.transcript||aiContext?.available.some(scope=>scope.kind==='supplement'))?()=>showReference('assistant'):undefined}/>")
p.write_bytes(s.replace('\n','\r\n').encode('utf8'))
for rel in ['packages/ui/src/MeetingReadingFrame.tsx','packages/ui/src/MeetingReferenceWorkspace.tsx','packages/ui/src/meetingReferenceWorkspace.css']:shutil.copyfile(S/rel,A/rel)
p=A/'apps/mobile/src/notebookMobile.css';s=p.read_text(encoding='utf8')
replacements={
 '.mobile-app main{padding:26px 22px 32px;':'.mobile-app main{padding:20px 22px 32px;',
 '.mobile-app .detail-title{margin-bottom:23px}':'.mobile-app .detail-page{padding-top:18px}.mobile-app .detail-title{margin-bottom:16px;align-items:flex-start}.mobile-app .detail-title h1{margin-top:0;font-size:22px;line-height:1.4}.mobile-app .detail-title>.text-button{margin-top:2px}.mobile-app .detail-status-row{display:none}',
 'padding:17px 0;margin:0 0 14px':'padding:12px 0;margin:0 0 16px',
 '.mobile-app .recording-content-navigation{position:relative;':'.mobile-app .recording-content-navigation{position:sticky;top:0;z-index:4;background:var(--surface);',
 '.mobile-app .detail-tabs{display:flex;flex:1;':'.mobile-app .detail-tabs{position:static;display:flex;flex:1;',
 '.mobile-app .detail-tabs button{display:block;':'.mobile-app .detail-tabs button{flex:none;min-width:44px;display:block;',
 '.mobile-app .meeting-recording-tools{margin-block:12px 20px;border:0}':'.mobile-app .meeting-recording-tools{margin-block:28px 20px;border-top:1px solid var(--line)}',
}
for old,new in replacements.items():assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
s+='\n.mobile-app .meeting-reading-indexed{display:block}.mobile-app .meeting-reading-sidebar{position:static;margin-bottom:12px;padding:0;border:0}.mobile-app .meeting-outline{display:flex;flex-wrap:wrap;gap:6px 15px}.mobile-app .meeting-outline button{padding:5px 0;border:0;background:transparent;color:var(--accent);font:inherit;font-size:12px}.mobile-app .reference-workspace-tools{margin:0 0 14px}.mobile-app .minutes-preamble-generated{display:none}\n'
p.write_bytes(s.encode('utf8'));print('Mobile reader reordered: title, replay, reading choices, content, management; shared source tools mounted and drafts retained')
