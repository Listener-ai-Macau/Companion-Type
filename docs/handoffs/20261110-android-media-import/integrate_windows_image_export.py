from pathlib import Path
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055')
def edit(name,old,new):
 p=S/name;s=p.read_text(encoding='utf-8');assert s.count(old)==1,(name,old[:100],s.count(old));p.write_text(s.replace(old,new),encoding='utf-8',newline='\r\n')
for name in ['apps/windows/src-tauri/src/backend/export.rs','apps/windows/src-tauri/src/commands.rs']:
 edit(name,'    Png,','    Png,\n    Bundle,')
edit('apps/windows/src-tauri/src/backend/export.rs','            Self::Png => "png",','            Self::Png => "png",\n            Self::Bundle => "zip",')
edit('apps/windows/src-tauri/src/backend/export.rs','            Self::Png => "思维导图 PNG",','            Self::Png => "思维导图 PNG",\n            Self::Bundle => "图文 ZIP（含原图）",')
edit('apps/windows/src-tauri/src/backend/export.rs','        MeetingExportFormat::Json => {','        MeetingExportFormat::Bundle => return Err("图文 ZIP 请在导出面板选择要保存的内容。".into()),\n        MeetingExportFormat::Json => {')
edit('apps/windows/src-tauri/src/backend/export.rs','        MeetingExportFormat::Json => "完整资料",','        MeetingExportFormat::Json => "完整资料",\n        MeetingExportFormat::Bundle => "图文资料",')
edit('apps/windows/src-tauri/src/commands.rs','            CompanionMeetingExportFormat::Png => Self::Png,','            CompanionMeetingExportFormat::Png => Self::Png,\n            CompanionMeetingExportFormat::Bundle => Self::Bundle,')
edit('apps/windows/src-tauri/src/lib.rs','                Some("png") => backend::export::MeetingExportFormat::Png,','                Some("png") => backend::export::MeetingExportFormat::Png,\n                Some("bundle") => backend::export::MeetingExportFormat::Bundle,')
edit('apps/windows/src-tauri/src/backend/content_export.rs','Format::Srt|Format::Pptx|Format::Png)', 'Format::Srt|Format::Pptx|Format::Png|Format::Bundle)')
edit('apps/windows/src-tauri/src/backend/content_export.rs','        Format::Docx=>super::meeting_document_export::word', '        Format::Bundle=>super::meeting_note_images::bundle(session,&content,&choice.note_ids)?,\n        Format::Docx=>super::meeting_document_export::word')
edit('packages/ui/src/CompanionDashboard.tsx',"| 'pptx' | 'png' | 'todo'", "| 'pptx' | 'png' | 'bundle' | 'todo'")
edit('packages/ui/src/ContentExportPanel.tsx',"|'pptx'|'png';", "|'pptx'|'png'|'bundle';")
edit('packages/ui/src/ContentExportPanel.tsx',"=[['pdf','PDF']", "=[['bundle','图文 ZIP（含原图）'],['pdf','PDF']")
edit('packages/ui/src/ContentExportPanel.tsx','return <', 'return <') if False else None
# Descriptive UI help stays beside the existing format selector, not in a new wizard.
p=S/'packages/ui/src/ContentExportPanel.tsx';s=p.read_text(encoding='utf-8');anchor="{format==='srt'";assert anchor in s;s=s.replace(anchor,"{format==='bundle'&&<p className=\"ct-export-hint\">解压图文 ZIP 后打开“打开阅读.html”即可离线阅读。仅包含勾选内容和其中的原图片，每次图片合计不超过64MB；其它格式只保留备注文字、时间和图片名称。</p>}"+anchor,1);p.write_text(s,encoding='utf-8',newline='\r\n')
print('Selected-content ZIP integrated in normal save/share export; other formats retain explicit image captions')
