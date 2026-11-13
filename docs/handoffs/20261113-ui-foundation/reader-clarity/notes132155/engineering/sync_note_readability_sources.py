from pathlib import Path
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109'
p=S/'packages/ui/src/meetingNoteDocument.css';raw=p.read_text(encoding='utf8')
# The application foundation is imported after component CSS. Scope the new
# document rules to the actual root rather than relying on import order.
raw=raw.replace('body .ct-shell.ct-windows.ct-notebook','.ct-shell.ct-windows.ct-notebook').replace('body .ct-windows.ct-notebook','.ct-windows.ct-notebook')
raw=raw.replace('.ct-shell.ct-windows.ct-notebook','body .ct-shell.ct-windows.ct-notebook').replace('\n.ct-windows.ct-notebook','\nbody .ct-windows.ct-notebook')
p.write_text(raw,encoding='utf8')
paths=['packages/ui/src/transcriptReading.ts','packages/ui/src/TranscriptFind.tsx','packages/ui/src/MeetingTopic.tsx','packages/ui/src/overviewTopics.css','packages/ui/src/meetingNoteDocument.css','packages/ui/src/meetingReading.ts']
for rel in paths:
 source=(S/rel).read_bytes();(A/rel).write_bytes(source);assert (A/rel).read_bytes()==source
print(json.dumps({rel:hashlib.sha256((S/rel).read_bytes()).hexdigest() for rel in paths},indent=2))
