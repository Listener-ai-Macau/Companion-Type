from pathlib import Path
import shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';S=R/'companion-device-closure055'
p=A/'apps/android/app/src/main/java/com/denzic/companion/app/MainActivity.java';raw=p.read_bytes();text=raw.decode('utf-8').replace('\r\n','\n')
def change(old,new):
    global text
    assert text.count(old)==1,old[:140]
    text=text.replace(old,new)
change('asset.endsWith(".js") ? "text/javascript"','(asset.endsWith(".js") || asset.endsWith(".mjs")) ? "text/javascript"')
change('    private RecordingNotes recordingNotes()throws Exception{', '''    private DocumentContextStore documentContexts()throws Exception{return new DocumentContextStore(libraries().meetings(),MainActivity::syncLifecycleDirectory);}
    private JSONObject documentDescription(String key)throws Exception{return documentContexts().read(key).put("libraryToken",libraries().token());}
    private RecordingNotes recordingNotes()throws Exception{''')
change('locked=true;RecordingLibrary.Session selected=noteSession(args);String key=args.getString("key");String mime=', '''locked=true;RecordingLibrary.Session selected=noteSession(args);String key=args.getString("key");
            if("document".equals(args.optString("attachmentKind"))){
                String name=null;try(android.database.Cursor cursor=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);}
                if(name==null)throw new java.io.IOException("无法确认文档名称和格式，请另存后重试。");
                try(java.io.InputStream input=getContentResolver().openInputStream(uri)){if(input==null)throw new java.io.IOException("所选文档暂不可读取。");documentContexts().add(key,args.getLong("revision"),args.getString("id"),name,input);}
                reply(id,documentDescription(key),null);return;
            }
            String mime=''')
assert text.count('图片选择已中断，请重新选择；已保存备注仍保留。')==2
text=text.replace('图片选择已中断，请重新选择；已保存备注仍保留。','文件选择已中断，请重新选择；已保存材料和备注仍保留。')
change('    private final class Bridge {','''    private final class Bridge {
        @JavascriptInterface public void pickContextDocument(long id,String json){
            worker.execute(()->{try{JSONObject args=new JSONObject(json);noteSession(args);args.put("attachmentKind","document");if(LocalLibraryBackups.BUSY.get())throw new java.io.IOException("资料正在保存，请稍后重试。");runOnUiThread(()->{
                if(isFinishing()||isDestroyed())return;if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0||noteImageRequestId!=0){reply(id,null,"已有文件选择操作正在进行。");return;}
                noteImageRequestId=id;noteImageRequest=args;noteImageRestored=false;try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","application/vnd.openxmlformats-officedocument.presentationml.presentation","text/plain","text/markdown","text/csv"}),35);}catch(Exception e){noteImageRequestId=0;noteImageRequest=null;reply(id,null,"无法打开系统文档选择器，请重试。");}
            });}catch(Exception e){reply(id,null,e.getMessage());}});
        }''')
change('    private JSONObject aiDocument(String key) throws Exception {','''    private JSONObject aiDocument(String key) throws Exception {
        if(key.startsWith("document:")){int split=key.lastIndexOf(':');if(split<10)throw new java.io.IOException("材料来源标识无效。");String owner=key.substring(9,split);session(owner);return documentContexts().aiDocument(owner,key.substring(split+1));}''')
change('            case "recordingNotes":{','''            case "documentContexts":{String key=a.getString("key");session(key);return documentDescription(key);}
            case "documentContextChunk":{noteSession(a);return documentContexts().chunk(a.getString("key"),a.getLong("revision"),a.getString("id"),a.getInt("offset"));}
            case "documentContextRead":{noteSession(a);return documentContexts().extraction(a.getString("key"),a.getLong("revision"),a.getString("id"));}
            case "documentContextCommit":{noteSession(a);String key=a.getString("key");documentContexts().saveExtraction(key,a.getLong("revision"),a.getString("id"),a.getJSONObject("extraction"));return documentDescription(key);}
            case "documentContextRemove":{noteSession(a);String key=a.getString("key");documentContexts().remove(key,a.getLong("revision"),a.getString("id"));return documentDescription(key);}
            case "documentContextOriginal":{noteSession(a);String key=a.getString("key"),id=a.getString("id");long revision=a.getLong("revision");JSONObject list=documentContexts().read(key),entry=null;JSONArray documents=list.getJSONArray("rows");for(int i=0;i<documents.length();i++)if(id.equals(documents.getJSONObject(i).getString("id")))entry=documents.getJSONObject(i);if(entry==null)throw new java.io.IOException("材料已移除。");Path file=documentContexts().original(key,revision,id);String ext=entry.getString("format"),mime="pdf".equals(ext)?"application/pdf":"docx".equals(ext)?"application/vnd.openxmlformats-officedocument.wordprocessingml.document":"xlsx".equals(ext)?"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":"pptx".equals(ext)?"application/vnd.openxmlformats-officedocument.presentationml.presentation":"text/plain";
                return preparedExports().create(new JSONObject().put("key",key).put("libraryToken",libraries().token()).put("title",entry.getString("name")),PreparedExports.filename(entry.getString("name"),"原件",ext),mime,null,out->java.nio.file.Files.copy(file,out)).dto();}
            case "recordingNotes":{''')
change('                return new JSONObject().put("libraryToken",libraries().token()).put("available",available)', '''                if(a.has("ownerKey")){String owner=a.getString("ownerKey");session(owner);try{JSONObject context=documentContexts().read(owner);JSONArray rows=context.getJSONArray("rows");for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);if(!row.has("extraction"))continue;try{JSONObject doc=documentContexts().aiDocument(owner,row.getString("id"));identity.append(doc.getString("binding"));doc.remove("text");available.put(doc);}catch(Exception unavailable){problems++;}}}catch(Exception unavailable){problems++;}}
                return new JSONObject().put("libraryToken",libraries().token()).put("available",available)''')
change('"请选择1到12场会议。"','"请选择1到12项会议转写或补充材料。"')
assert p.read_bytes()==raw;p.write_bytes(text.replace('\n','\r\n' if b'\r\n' in raw else '\n').encode('utf-8'))
for rel in ['packages/document-context','vendor/document-context']:
    shutil.copytree(S/rel,A/rel,dirs_exist_ok=True)
for rel in ['packages/ui/src/DocumentContextPanel.tsx','packages/ui/src/documentContext.css','apps/mobile/vite.config.ts']:shutil.copyfile(S/rel,A/rel)
print('Android native document storage, guarded picker, original export and explicit supplementary AI sources integrated; UI and packaging pending.')
