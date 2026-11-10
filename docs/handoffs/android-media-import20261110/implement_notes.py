from pathlib import Path
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109'
p=A/'apps/android/app/src/main/java/com/denzic/companion/app/MainActivity.java';s=p.read_text(encoding='utf-8')
def replace(old,new):
 global s
 assert s.count(old)==1,(old[:100],s.count(old));s=s.replace(old,new)
replace('    private long audioImportRequestId;', '    private long noteImageRequestId;private JSONObject noteImageRequest;private boolean noteImageRestored;\n    private long audioImportRequestId;')
replace('            audioImportRequestId=state.getLong', '            noteImageRequestId=state.getLong("noteImageRequestId",0);noteImageRestored=noteImageRequestId!=0;\n            audioImportRequestId=state.getLong')
replace('        state.putLong("audioImportRequestId",','        state.putLong("noteImageRequestId",noteImageRequestId);\n        state.putLong("audioImportRequestId",')
replace('        notifySystemAppearance();\n        if(audioImportRequestRestored', '        notifySystemAppearance();\n        if(noteImageRestored&&noteImageRequestId!=0){noteImageRequestId=0;noteImageRestored=false;android.widget.Toast.makeText(this,"图片选择已中断，请重新选择；已保存备注仍保留。",android.widget.Toast.LENGTH_LONG).show();}\n        if(audioImportRequestRestored')
replace('        if(requestCode==34)', '        if(requestCode==35){finishNoteImagePicker(resultCode,data);return;}\n        if(requestCode==34)')
replace('    private void finishAudioImportPicker', '''    private RecordingNotes recordingNotes()throws Exception{return new RecordingNotes(libraries().meetings(),MainActivity::syncLifecycleDirectory);}
    private RecordingLibrary.Session noteSession(JSONObject a)throws Exception{
        if(!a.getString("libraryToken").equals(libraries().token()))throw new java.io.IOException("资料库已切换，请重新打开这条录音；输入尚未保存。");return session(a.getString("key"));
    }
    private static Long noteTime(JSONObject a)throws Exception{return !a.has("atMs")||a.isNull("atMs")?null:a.getLong("atMs");}
    private JSONObject noteDescription(String key)throws Exception{
        JSONObject value=recordingNotes().read(key);return value.put("libraryToken",libraries().token());
    }
    private void finishNoteImagePicker(int resultCode,Intent data){
        final long id=noteImageRequestId;final JSONObject args=noteImageRequest;final boolean restored=noteImageRestored;noteImageRequestId=0;noteImageRequest=null;noteImageRestored=false;
        if(id==0)return;if(restored||args==null){android.widget.Toast.makeText(this,"图片选择已中断，请重新选择；已保存备注仍保留。",android.widget.Toast.LENGTH_LONG).show();return;}
        if(resultCode!=RESULT_OK||data==null||data.getData()==null){try{reply(id,new JSONObject().put("cancelled",true),null);}catch(Exception ignored){}return;}
        final android.net.Uri uri=data.getData();worker.execute(()->{boolean locked=false;try{
            if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("正在保存其它资料，请稍后重试；输入仍保留。");locked=true;RecordingLibrary.Session selected=noteSession(args);String key=args.getString("key");String mime=getContentResolver().getType(uri),extension="image/jpeg".equals(mime)?"jpg":"image/png".equals(mime)?"png":"image/webp".equals(mime)?"webp":null;
            if(extension==null)throw new java.io.IOException("请选择JPEG、PNG或WebP图片。");String name="图片."+extension;
            try(android.database.Cursor cursor=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);}
            final String type=extension;try(java.io.InputStream input=getContentResolver().openInputStream(uri)){if(input==null)throw new java.io.IOException("所选图片暂不可读取。");recordingNotes().addImage(key,args.getLong("revision"),args.optString("text",""),noteTime(args),completeAudioDurationMs(selected),name,extension,input,path->RecordingNoteImages.validate(path,type));}
            reply(id,noteDescription(key),null);
        }catch(Exception e){reply(id,null,e.getMessage()==null?"图片保存未完成，输入仍保留，请重试。":e.getMessage());}finally{if(locked)LocalLibraryBackups.BUSY.set(false);}});
    }
    private void finishAudioImportPicker''')
replace('        @JavascriptInterface public void cancelAudioImport()', '''        @JavascriptInterface public void pickNoteImage(long id,String json){
            worker.execute(()->{try{JSONObject args=new JSONObject(json);noteSession(args);if(LocalLibraryBackups.BUSY.get())throw new java.io.IOException("资料正在保存，请稍后重试。");runOnUiThread(()->{
                if(isFinishing()||isDestroyed())return;if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0||noteImageRequestId!=0){reply(id,null,"已有文件选择操作正在进行。");return;}
                noteImageRequestId=id;noteImageRequest=args;noteImageRestored=false;try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/*").putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"image/jpeg","image/png","image/webp"}),35);}catch(Exception e){noteImageRequestId=0;noteImageRequest=null;reply(id,null,"无法打开系统图片选择器，输入仍保留。");}
            });}catch(Exception e){reply(id,null,e.getMessage());}});
        }
        @JavascriptInterface public void cancelAudioImport()''')
# Include the new picker in existing mutually exclusive file chooser guards.
s=s.replace('documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0){','documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0||noteImageRequestId!=0){')
s=s.replace('documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0){','documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0||noteImageRequestId!=0){')
replace('                if (segments.isEmpty() || !"www".equals(segments.get(0)))', '''                if(segments.size()==5&&"notes".equals(segments.get(0))){try{
                    String token=segments.get(1),key=segments.get(2),id=segments.get(3),sha=segments.get(4);if(!token.equals(libraries().token()))return blockedAsset();session(key);JSONObject value=recordingNotes().read(key);JSONArray entries=value.getJSONArray("entries");
                    for(int i=0;i<entries.length();i++){JSONObject e=entries.getJSONObject(i);if(id.equals(e.getString("id"))&&e.has("image")&&sha.equals(e.getJSONObject("image").getString("sha256"))){Path file=recordingNotes().verifiedImage(key,e.getJSONObject("image"));return new WebResourceResponse("image/jpeg",null,RecordingNoteImages.thumbnail(file));}}
                }catch(Exception unavailable){}return blockedAsset();}
                if (segments.isEmpty() || !"www".equals(segments.get(0)))''')
replace('            case "audioImportStatus":', '''            case "recordingNotes":{String key=a.getString("key");session(key);return noteDescription(key);}
            case "saveRecordingNote":{RecordingLibrary.Session selected=noteSession(a);String key=a.getString("key");recordingNotes().save(key,a.getLong("revision"),a.optString("id",""),a.optString("text",""),noteTime(a),completeAudioDurationMs(selected));return noteDescription(key);}
            case "removeRecordingNote":{noteSession(a);String key=a.getString("key");recordingNotes().remove(key,a.getLong("revision"),a.getString("id"));return noteDescription(key);}
            case "playRecordingNote":{RecordingLibrary.Session selected=noteSession(a);String key=a.getString("key");JSONObject value=recordingNotes().read(key);if(value.getLong("revision")!=a.getLong("revision"))throw new java.io.IOException("备注已更新，请重新读取后回听。");JSONArray entries=value.getJSONArray("entries");Long target=null;
                for(int i=0;i<entries.length();i++){JSONObject e=entries.getJSONObject(i);if(a.getString("id").equals(e.getString("id"))&&!e.isNull("atMs"))target=e.getLong("atMs");}
                if(target==null)throw new java.io.IOException("这条备注没有已保存的时间点。");NativeAudio.PartsResult parts=ManagedAudioParts.prepare(selected,root().resolve("companion-decoded-audio"));if(target<0||target>=parts.samples/16)throw new java.io.IOException("备注位置尚无可用音频，请完成接收后重试。");
                stopPlayback();JSONObject resume=savedPlaybackProgress(selected,key,parts.samples/16);try{beginPlayback(selected,key,parts,target,resume.getDouble("speed"));}catch(Exception e){stopPlayback();throw e;}return new JSONObject().put("durationMs",parts.samples/16).put("positionMs",target).put("speed",playingSpeed);
            }
            case "audioImportStatus":''')
replace('problems,materials);','problems,materials,readNotesForExport(key,problems));')
replace('    private boolean confirmDeviceRecordingDelete', '''    private JSONObject readNotesForExport(String key,JSONArray problems)throws Exception{try{return recordingNotes().read(key);}catch(Exception e){problems.put("备注与图片暂不可读取，原文件保留；可先导出其它内容。");return null;}}
    private boolean confirmDeviceRecordingDelete''')
replace('switch(format){case "txt":','switch(format){case "bundle":extension="zip";mime="application/zip";break;case "txt":')
replace('            if("pdf".equals(format))MeetingPdf', '''            if("bundle".equals(format))recordingNotes().bundle(source.key,source.notes==null?new JSONObject().put("entries",new JSONArray()):source.notes,source.title,MeetingDocumentSections.markdown(sections),out);
            else if("pdf".equals(format))MeetingPdf''')
# ZIP includes originals only if the user selected notes, never silently includes unselected data.
s=s.replace('source.notes==null?new JSONObject().put("entries",new JSONArray()):source.notes','!selected.toString().contains("\\\"notes\\\"")||source.notes==null?new JSONObject().put("entries",new JSONArray()):source.notes')
p.write_text(s,encoding='utf-8',newline='\r\n')
print('MainActivity notes/image/export integration written')
