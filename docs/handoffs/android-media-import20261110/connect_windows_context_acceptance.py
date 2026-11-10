from pathlib import Path
import hashlib,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
def edit(name,old,new):
 p=S/name;s=p.read_text(encoding='utf-8')
 if new in s:return
 assert s.count(old)==1,(name,old[:100],s.count(old));p.write_text(s.replace(old,new),encoding='utf-8',newline='')
name='tools/qa/core_acceptance20261109/windows_meeting.py'
edit(name,"choices=['inspect','handoff','audio','ai','transcribe','actions']","choices=['inspect','handoff','audio','ai','transcribe','actions','context']")
edit(name,"'requireGroupedUi':v['version'] in {'0.1.79','0.1.80','0.1.81','0.1.82'}","'requireGroupedUi':v['version'] in {'0.1.79','0.1.80','0.1.81','0.1.82','0.1.83'}")
edit(name," if a.stage in {'audio','transcribe'}:\n", " if a.stage in {'audio','transcribe','context'}:\n")
edit(name," for name in ['roaming','local','recordings','webview','temp']:", """ if a.stage=='context':
  assert DEDICATED_CI,'Native picker context flow belongs to a disposable CI machine'
  public=Path(__file__).parent/'fixtures/public-whiteboard124.png';assert sha(public)=='96d134af463a7b50fa6377fd988fbaa20ec8a9a02fafbda31e9c15dd2b855855'
  received=root/'received-files';received.mkdir();image=received/'Companion-public-whiteboard083.png';bad=received/'Companion-public-invalid083.png';shutil.copy2(public,image);bad.write_text('This is not a raster image. Explicit public test fixture.')
  # The unrelated control is an honest text-only fixture, with no missing board audio.
  session.update(source='importedTranscript',audioPath=None,audioStored=False,audioBytes=0,chunks=[],deviceRecordingId=None,deviceRecordingKey=None,sourceDeviceId=None,meetingTracks=None)
  session['retention']['audioCached']=False;(state/'sessions.json').write_text(json.dumps(sessions,ensure_ascii=False),encoding='utf8')
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan.update(imageInput=str(image),imageSha256=sha(image),invalidImage=str(bad),invalidImageSha256=sha(bad),statePath=str(state/'sessions.json'),recordingDirectory=str(root/'recordings'));(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 for name in ['roaming','local','recordings','webview','temp']:""")
edit(name,"  if a.stage=='actions':\n   assert DEDICATED_CI,", "  if a.stage in {'actions','context'}:\n   assert DEDICATED_CI,")
edit(name,"else 480 if a.stage=='audio' else 180", "else 480 if a.stage in {'audio','context'} else 180")
edit(name,"  if a.stage=='actions':record['state']='REAL_NATIVE_ACTION_REVIEW_FOLLOWUP_AND_COPY_PASSED';record['remoteOwnedWindowFocused']=True", "  if a.stage=='context':record['state']='REAL_NATIVE_RECORDING_IMAGE_CONTEXT_AND_SELECTED_ZIP_PASSED';record['remoteOwnedWindowFocused']=True\n  if a.stage=='actions':record['state']='REAL_NATIVE_ACTION_REVIEW_FOLLOWUP_AND_COPY_PASSED';record['remoteOwnedWindowFocused']=True")
edit(name,"bool(DEDICATED_CI and a.stage=='actions')", "bool(DEDICATED_CI and a.stage in {'actions','context'})")
edit('tools/qa/core_acceptance20261109/windows_native_dialog.py',"assert sha(target)==request['sha256'] and target.suffix in {'.wav','.mp3'}", "assert sha(target)==request['sha256'] and target.suffix in {'.wav','.mp3','.png','.jpg','.jpeg','.webp'}")
edit('tools/qa/core_acceptance20261109/windows_native_dialog.py',"target.suffix in {'.wav','.mp3'} and not target.exists()", "target.suffix in {'.wav','.mp3','.zip','.docx'} and not target.exists()")
edit('tools/qa/core_acceptance20261109/windows_meeting_ui.cjs',"  }else if(stage==='actions'){", "  }else if(stage==='context'){\n   const result=await require('./windows_context_ui.cjs')(page,plan,out);\n   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));\n  }else if(stage==='actions'){")
source=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone124/Companion-Public-Whiteboard124.png');assert hashlib.sha256(source.read_bytes()).hexdigest()=='96d134af463a7b50fa6377fd988fbaa20ec8a9a02fafbda31e9c15dd2b855855';shutil.copy2(source,S/'tools/qa/core_acceptance20261109/fixtures/public-whiteboard124.png')
print('Existing isolated Windows native GUI/picker runner extended for image context; no app launch or owner input')
