from pathlib import Path
A=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109');D=A/'apps/android/app/src/main/java/com/denzic/companion/app'
p=D/'MainActivity.java';t=p.read_text(encoding='utf8')
def change(old,new):
 global t
 assert t.count(old)==1,(old[:120],t.count(old));t=t.replace(old,new)
change('private long updateRequestId;','private long audioImportRequestId;private String audioImportLibraryToken;private boolean audioImportRequestRestored;\n    private long updateRequestId;')
change('return defaultRecordingTitle(session.segments.get(0).descriptor.sessionId, false);','if(session.imported!=null){String name=session.imported.name;return name.substring(0,Math.min(name.length(),100));}\n        return defaultRecordingTitle(session.segments.get(0).descriptor.sessionId, false);')
change('if(session.state!=RecordingLibrary.SessionState.COMPLETE)return -1;','if(session.imported!=null)return session.imported.samples/16;\n        if(session.state!=RecordingLibrary.SessionState.COMPLETE)return -1;')
change('state.putLong("updateRequestId",updateRequestId);','state.putLong("audioImportRequestId",audioImportRequestId);state.putString("audioImportLibraryToken",audioImportLibraryToken);\n        state.putLong("updateRequestId",updateRequestId);')
needle='updateRequestId=state.getLong("updateRequestId",0);'
assert needle in t
change(needle,'audioImportRequestId=state.getLong("audioImportRequestId",0);audioImportLibraryToken=state.getString("audioImportLibraryToken");audioImportRequestRestored=audioImportRequestId!=0;\n            '+needle)
change('notifySystemAppearance();\n        if(updateRequestRestored', 'notifySystemAppearance();\n        if(audioImportRequestRestored&&audioImportRequestId!=0){audioImportRequestId=0;audioImportRequestRestored=false;audioImportLibraryToken=null;android.widget.Toast.makeText(this,"文件选择已中断，请重新选择导入；原文件未改变。",android.widget.Toast.LENGTH_LONG).show();}\n        if(updateRequestRestored')
change('if(requestCode==33){finishUpdatePicker(resultCode,data);return;}','if(requestCode==34){finishAudioImportPicker(resultCode,data);return;}\n        if(requestCode==33){finishUpdatePicker(resultCode,data);return;}')
change('private void requireLibraryIdle() throws Exception {','private void finishAudioImportPicker(int resultCode,Intent data){\n        final long id=audioImportRequestId;final String token=audioImportLibraryToken;final boolean restored=audioImportRequestRestored;audioImportRequestId=0;audioImportLibraryToken=null;audioImportRequestRestored=false;\n        if(id==0)return;if(resultCode!=RESULT_OK||data==null||data.getData()==null){if(!restored)reply(id,false,null);return;}\n        try{AudioImportService.start(this,data.getData(),token);if(!restored)reply(id,new JSONObject().put("started",true),null);else android.widget.Toast.makeText(this,"正在导入，进度可在录音库查看。",android.widget.Toast.LENGTH_LONG).show();}\n        catch(Exception e){if(!restored)reply(id,null,e.getMessage());else android.widget.Toast.makeText(this,e.getMessage(),android.widget.Toast.LENGTH_LONG).show();}\n    }\n    private void requireLibraryIdle() throws Exception {\n        if(AudioImportService.isRunning())throw new java.io.IOException("正在导入录音，请等完成或取消后再操作资料。");')
change('@JavascriptInterface public void libraryArchive(long id,String kind,String token){','@JavascriptInterface public void cancelAudioImport(){AudioImportService.cancel();}\n        @JavascriptInterface public void pickAudioImport(long id,String token){\n            worker.execute(()->{try{requireLibraryIdle();if(LocalLibraryBackups.BUSY.get()||!token.equals(libraries().token()))throw new java.io.IOException("资料库已变化或正在更新，请稍后重试。");runOnUiThread(()->{\n                if(isFinishing()||isDestroyed())return;if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0){reply(id,null,"已有文件选择操作正在进行。");return;}\n                audioImportRequestId=id;audioImportLibraryToken=token;audioImportRequestRestored=false;try{Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"audio/*","video/*"});startActivityForResult(intent,34);}catch(Exception e){audioImportRequestId=0;audioImportLibraryToken=null;reply(id,null,"无法打开系统文件选择器，请重试。");}\n            });}catch(Exception e){reply(id,null,e.getMessage());}});\n        }\n        @JavascriptInterface public void libraryArchive(long id,String kind,String token){')
change('if (!s.segments.isEmpty() && MeetingStore.sessionKey(s.segments.get(0).descriptor).equals(key)) return s;','if (s.key().equals(key)) return s;')
change('for(RecordingLibrary.Session row:RecordingLibrary.inspect(recordings()).sessions){if(row.segments.isEmpty())continue;String key=MeetingStore.sessionKey(row.segments.get(0).descriptor);','for(RecordingLibrary.Session row:RecordingLibrary.inspect(recordings()).sessions){String key=row.key();')
change('case "appPreferences":return appPreferences();','case "audioImportStatus":return AudioImportService.status(this);\n            case "appPreferences":return appPreferences();')
change('if (s.segments.isEmpty()) continue;\n                    RecorderWire.Descriptor d = s.segments.get(0).descriptor;\n                    String key=MeetingStore.sessionKey(d);','RecorderWire.Descriptor d = s.imported==null?s.segments.get(0).descriptor:null;\n                    String key=s.key();')
change('title=defaultRecordingTitle(d.sessionId,true);titleProblems++;','title=d==null?"导入录音 · 名称暂不可用":defaultRecordingTitle(d.sessionId,true);titleProblems++;')
change('.put("session", Long.toUnsignedString(d.sessionId))','.put("session",d==null?"文件导入":Long.toUnsignedString(d.sessionId)).put("source",d==null?"importedAudio":"recorder")')
change('.put("segments", s.segments.size()).put("lifecycle",life)','.put("segments",s.imported==null?s.segments.size():s.imported.partCount()).put("lifecycle",life)')
p.write_text(t,encoding='utf8')
p=D/'RecordingBookmarkAccess.java';t=p.read_text();old='MessageDigest hash=MessageDigest.getInstance("SHA-256");';assert t.count(old)==1;t=t.replace(old,'if(session.imported!=null)return ImportedAudio.hash(session.imported.fingerprint());\n        '+old);p.write_text(t)
p=D/'LocalRecordingLifecycle.java';t=p.read_text();old='try(DirectoryStream<Path> entries=Files.newDirectoryStream(meetings)){';assert t.count(old)==1;t=t.replace(old,'''if(com.denzic.companion.mobile.ImportedAudio.validKey(key)){
            Path directory=recordings.resolve(com.denzic.companion.mobile.ImportedAudio.folder(key));
            if(Files.exists(directory,LinkOption.NOFOLLOW_LINKS)){
                managedPath(directory);com.denzic.companion.mobile.ImportedAudio imported=com.denzic.companion.mobile.ImportedAudio.read(directory);Set<Path> owned=new HashSet<>(imported.ownedFiles());
                for(Path file:owned)add(files,"recordings",recordings,file);
                try(DirectoryStream<Path> remaining=Files.newDirectoryStream(directory)){for(Path file:remaining)if(!owned.contains(file))retained++;}
            }
        }
        '''+old)
old='if(scope.equals("meetings")&&name.matches';new='if(scope.equals("recordings")&&com.denzic.companion.mobile.ImportedAudio.validKey(key))owned=name.matches(java.util.regex.Pattern.quote(com.denzic.companion.mobile.ImportedAudio.folder(key))+"/(original\\\\.audio|import\\\\.json|part-[0-9]{8}\\\\.wav)");\n            '+old;assert t.count(old)==1;t=t.replace(old,new);p.write_text(t)
p=A/'apps/android/app/src/main/AndroidManifest.xml';t=p.read_text();t=t.replace('<application android:label=', '<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />\n    <uses-permission android:name="android.permission.WAKE_LOCK" />\n    <application android:label=');t=t.replace('<service android:name=".DeviceUpdateService"','<service android:name=".AudioImportService" android:exported="false" android:foregroundServiceType="dataSync" />\n        <service android:name=".DeviceUpdateService"');p.write_text(t)
p=A/'apps/mobile/src/App.tsx';t=p.read_text()
t=t.replace("import {TranscriptReplace}","import {AudioImport,type AudioImportStatus} from './AudioImport';\nimport {TranscriptReplace}")
t=t.replace('call(id:number,method:string,args:string):void;','call(id:number,method:string,args:string):void;pickAudioImport?(id:number,token:string):void;cancelAudioImport?():void;')
marker='function saveLibraryArchive(';i=t.index(marker);t=t[:i]+'''function chooseAudioImport(token:string):Promise<false|{started:boolean}>{if(!window.CompanionNative?.pickAudioImport)return Promise.reject(new Error('请更新Android应用后导入文件。'));return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});window.CompanionNative!.pickAudioImport!(id,token);});}
'''+t[i:]
marker='<p className="library-count">{rows.length?`共 ${rows.length} 条录音`:';assert marker in t
t=t.replace("'录音同步后会显示在这里'","'连接录音卡或导入已有录音，即可开始整理'")
marker='</button></div>\n<LibraryLocation';
if marker not in t:
 marker=next(s for s in t.splitlines() if '<LibraryLocation' in s)
 insertion='''{!readingPreview&&<AudioImport busy={!!busy} onChoose={async()=>{const result=await run('请选择导入文件',async()=>{const status=await call<LibraryStatus>('libraryStatus');return chooseAudioImport(status.token);});return !!result&&result.started;}} onLoad={()=>call<AudioImportStatus>('audioImportStatus')} onCancel={()=>window.CompanionNative?.cancelAudioImport?.()} onChanged={()=>{void library();setNotice('导入流程已结束，请查看录音库与导入结果。');}}/>}
'''
 t=t.replace(marker,insertion+marker)
else:raise AssertionError('Review exact library insertion point')
p.write_text(t,encoding='utf8')
print('System picker/service, independent import sessions, existing meeting chain and exact deletion ownership wired.')
