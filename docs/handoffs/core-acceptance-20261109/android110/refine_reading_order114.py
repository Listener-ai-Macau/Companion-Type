"""Finish the same first-screen reading correction using the real phone result."""
from pathlib import Path
R=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109');P=R/'apps/mobile/src/App.tsx';s=P.read_text(encoding='utf8')
management="{!readingPreview&&detail.lifecycle&&detail.libraryToken&&<RecordingManagement key={selected.key} title={selected.title} life={detail.lifecycle} libraryToken={detail.libraryToken} busy={!!busy||!!status?.running||updateRunning} onChange={changeRecordingLife}/>}"
marks="{!readingPreview&&<DeviceBookmarks key={'device-bookmarks:'+selected.key} recordingKey={selected.key} busy={!!busy} onLoad={()=>call<DeviceMarkList>('bookmarks',{key:selected.key})} onPlay={playDeviceMark} onExport={exportDeviceMarks}/>}"
assert s.count(management)==1 and s.count(marks)==1
s=s.replace(management,'')
tools='{!readingPreview&&<div className="meeting-audio-tools">{'+management[len('{!readingPreview&&'):-1]+'}'+marks[len('{!readingPreview&&'):-1]+'</div>}'
s=s.replace(marks,tools)
start=s.index('{detail.transcript&&<MeetingAssistant');end=s.index('</MeetingAssistant>}',start)+len('</MeetingAssistant>}');old=s[start:end]
element=old[len('{detail.transcript&&'):-1]
s=s[:start]+'{!detail.minutes&&detail.transcript&&'+element+'}'+s[end:]
boundary=':null}{detail.minutesRecovered&&';assert s.count(boundary)==1
s=s.replace(boundary,':null}{detail.minutes&&detail.transcript&&'+element+'}{detail.minutesRecovered&&')
heading='<h2>纪要</h2>{detail.transcript&&<button';assert s.count(heading)==1
shortcut="<h2>纪要</h2>{detail.minutes&&<button className=\"text-button\" disabled={!!busy||updateRunning} onClick={()=>{const panel=document.querySelector<HTMLDetailsElement>('.existing-minutes');if(panel){panel.open=true;panel.scrollIntoView({block:'start'});}}}>整理方式</button>}{detail.transcript&&<button"
s=s.replace(heading,shortcut);P.write_text(s,encoding='utf8')
P=R/'apps/mobile/src/RecordingLifecycle.tsx';s=P.read_text();s=s.replace('Shield,Trash2,RotateCcw','Shield,Trash2,RotateCcw,ChevronDown')
old="<summary>录音管理{life.protected?' · 已保护':''}</summary>";assert old in s
s=s.replace(old,"<summary><span>录音管理{life.protected?' · 已保护':''}</span><ChevronDown size={15} aria-hidden=\"true\"/></summary>")
P.write_text(s,encoding='utf8')
P=R/'apps/mobile/src/mobilePremium.css';s=P.read_text();s+='''
/* Keep the saved meeting itself in the first phone viewport. */
.meeting-audio-tools{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}
.meeting-audio-tools>details{margin:0;padding:0;min-width:0}
.meeting-audio-tools:has(>details[open]){grid-template-columns:1fr}
.meeting-audio-tools>.recording-management>summary{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:44px;padding:12px 14px;box-sizing:border-box;list-style:none;font-size:13px;font-weight:600}
.meeting-audio-tools>.recording-management>p,.meeting-audio-tools>.recording-management>.buttons{margin-left:14px;margin-right:14px}
.meeting-audio-tools>details>summary::after,.meeting-assistant.existing-minutes>summary::after{display:none;content:none}
.meeting-audio-tools>details>summary::-webkit-details-marker{display:none}
.detail-title h1{font-size:22px;line-height:1.35;margin-top:10px;margin-bottom:8px}
@media(max-width:480px){
 .meeting-reading-frame .meeting-outline-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
 .meeting-reading-frame .meeting-outline-card{display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:6px;min-height:62px;padding:10px 8px}
 .meeting-reading-frame .meeting-outline-label{font-size:10.5px;gap:4px}
 .meeting-reading-frame .meeting-outline-label>svg:first-child{width:12px;height:12px}
 .meeting-reading-frame .meeting-outline-label>svg:last-child,.meeting-reading-frame .meeting-outline-hint{display:none}
 .meeting-reading-frame .meeting-outline-number{font-size:20px;line-height:1.1}
 .meeting-reading-frame .meeting-outline-number small{font-size:10px}
 .meeting-reading-frame .meeting-outline-grid:has(.meeting-outline-questions){grid-template-columns:repeat(4,minmax(0,1fr))}
}
@media(max-width:360px){.meeting-reading-frame .meeting-outline-grid:has(.meeting-outline-questions){grid-template-columns:repeat(2,minmax(0,1fr))}}
''';P.write_text(s,encoding='utf8')
P=R/'apps/android/app/build.gradle';s=P.read_text();assert 'versionCode 113' in s;s=s.replace('versionCode 113','versionCode 114').replace("versionName '0.1.113'","versionName '0.1.114'");P.write_text(s,encoding='utf8')
print('Saved meeting reading order updated; regeneration, recording management and local markers retained')
