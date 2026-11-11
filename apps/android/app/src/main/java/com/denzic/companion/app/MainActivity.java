package com.denzic.companion.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.bluetooth.BluetoothDevice;
import android.content.pm.PackageManager;
import android.content.Intent;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.JsResult;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import com.denzic.companion.mobile.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.ByteArrayInputStream;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Local-only presentation bridge. Device and file work never runs on the UI thread. */
public final class MainActivity extends Activity {
    private WebView web;
    private final java.util.concurrent.ScheduledExecutorService worker = Executors.newSingleThreadScheduledExecutor();
    private final DeviceConnectionOwner<RecordingClient> deviceConnection=new DeviceConnectionOwner<>(RecordingClient::isConnected);
    private List<BluetoothDevice> devices = new ArrayList<>();
    private List<RecorderWire.Descriptor> segments = new ArrayList<>();
    private BluetoothDevice selectedDevice;
    private MediaPlayer player;
    private List<NativeAudio.Part> playingParts = new ArrayList<>();
    private int playingIndex;
    private String playingKey,playingBinding;
    private Path playingMeetings;
    private long playingDurationMs,lastPlaybackSave;
    private double playingSpeed=1;
    private boolean playingComplete;
    private boolean playbackPaused;
    private String playbackSaveWarning;
    private final AtomicBoolean cancelTranscription = new AtomicBoolean();
    private final AtomicBoolean cancelMinutes = new AtomicBoolean();
    private long documentRequestId;
    private String documentKey, documentFormat, documentPreparedId;
    // A restored Activity has a new WebView, so its old JavaScript request ID is no longer valid.
    private boolean documentRequestRestored;
    private long libraryRequestId;
    private String libraryRequestKind,libraryRequestToken,documentLibraryToken;
    private boolean libraryRequestRestored;
    private long noteImageRequestId;private JSONObject noteImageRequest;private boolean noteImageRestored;
    private long audioImportRequestId;private String audioImportLibraryToken;private boolean audioImportRequestRestored;
    private long updateRequestId;
    private boolean updateRequestRestored;
    private Path root() { return getFilesDir().toPath(); }
    private LocalLibraryBackups libraries(){return new LocalLibraryBackups(root());}
    private Path recordings() throws java.io.IOException { return libraries().recordings(); }
    private MeetingStore store() throws java.io.IOException { return new MeetingStore(libraries().meetings()); }
    private LocalRecordingLifecycle lifecycle()throws Exception{return new LocalRecordingLifecycle(root(),recordings(),libraries().meetings(),MainActivity::syncLifecycleDirectory);}
    private RecordingOrganization recordingOrganization()throws Exception{return new RecordingOrganization(libraries().meetings(),MainActivity::syncLifecycleDirectory);}
    private static void syncLifecycleDirectory(Path directory)throws java.io.IOException{
        java.io.FileDescriptor fd=null;
        try{
            fd=android.system.Os.open(directory.toString(),android.system.OsConstants.O_RDONLY|android.system.OsConstants.O_CLOEXEC|android.system.OsConstants.O_NOFOLLOW,0);
            if(!android.system.OsConstants.S_ISDIR(android.system.Os.fstat(fd).st_mode))throw new java.io.IOException("管理资料目录无效。");
            android.system.Os.fsync(fd);
        }catch(android.system.ErrnoException e){throw new java.io.IOException("管理资料尚未安全保存，原文件保留，请重试。",e);}
        finally{if(fd!=null)try{android.system.Os.close(fd);}catch(android.system.ErrnoException ignored){}}
    }
    private TranslationStore translations() throws java.io.IOException { return new TranslationStore(libraries().meetings().resolve("translations")); }
    private android.util.AtomicFile titleFile(String key) throws Exception {
        byte[] digest=java.security.MessageDigest.getInstance("SHA-256").digest(key.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        StringBuilder name=new StringBuilder();for(byte value:digest)name.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
        return new android.util.AtomicFile(libraries().meetings().resolve(name+".title").toFile());
    }
    private String recordingTitle(String key, RecordingLibrary.Session session) throws Exception {
        android.util.AtomicFile file=titleFile(key);
        try {
            byte[] bytes;
            try (java.io.InputStream in=file.openRead(); java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream()) {
                byte[] buffer=new byte[256];int count;
                while((count=in.read(buffer))!=-1){if(out.size()+count>400)throw new java.io.IOException("录音名称文件损坏；原文件已保留。");out.write(buffer,0,count);}
                bytes=out.toByteArray();
            }
            if (bytes.length>400) throw new java.io.IOException("录音名称文件损坏；原文件已保留。");
            String name=new String(bytes,java.nio.charset.StandardCharsets.UTF_8).trim();
            if (name.isEmpty()||name.length()>100) throw new java.io.IOException("录音名称文件损坏；原文件已保留。");
            return name;
        } catch (java.io.FileNotFoundException missing) {
            File base=file.getBaseFile();
            if (base.exists() || new File(base.getPath()+".bak").exists())
                throw new java.io.IOException("录音名称暂不可读；原文件已保留。",missing);
        }
        if(session.imported!=null){String name=session.imported.name;return name.substring(0,Math.min(name.length(),100));}
        return defaultRecordingTitle(session.segments.get(0).descriptor.sessionId, false);
    }

    private static String defaultRecordingTitle(long sessionId, boolean unreadable) {
        String id=Long.toUnsignedString(sessionId);
        String suffix=id.substring(Math.max(0,id.length()-6));
        return (unreadable?"名称暂不可用 · ":"未命名录音 · ")+suffix;
    }
    private static long completeAudioDurationMs(RecordingLibrary.Session session) {
        if(session.imported!=null)return session.imported.samples/16;
        if(session.state!=RecordingLibrary.SessionState.COMPLETE)return -1;
        long samples=0;
        try { for(RecordingLibrary.Entry entry:session.segments) samples=Math.addExact(samples,entry.descriptor.sampleCount); }
        catch(ArithmeticException invalid) { return -1; }
        long ms=samples/16;
        return ms>0 && ms<=9007199254740991L ? ms : -1;
    }

    @SuppressLint("SetJavaScriptEnabled") @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        worker.scheduleAtFixedRate(()->savePlaybackProgress(false),5,5,java.util.concurrent.TimeUnit.SECONDS);
        if (state != null) {
            noteImageRequestId=state.getLong("noteImageRequestId",0);noteImageRestored=noteImageRequestId!=0;
            audioImportRequestId=state.getLong("audioImportRequestId",0);audioImportLibraryToken=state.getString("audioImportLibraryToken");audioImportRequestRestored=audioImportRequestId!=0;
            updateRequestId=state.getLong("updateRequestId",0);updateRequestRestored=updateRequestId!=0;
            libraryRequestId=state.getLong("libraryRequestId",0);libraryRequestKind=state.getString("libraryRequestKind");libraryRequestToken=state.getString("libraryRequestToken");
            libraryRequestRestored=libraryRequestId!=0;documentLibraryToken=state.getString("documentLibraryToken");documentPreparedId=state.getString("documentPreparedId");
            long pendingId=state.getLong("documentRequestId",0);
            String pendingKey=state.getString("documentKey"), pendingFormat=state.getString("documentFormat");
            if (pendingId!=0 && pendingKey!=null && DocumentRecovery.isPickerFormat(pendingFormat)) {
                documentRequestId=pendingId;documentKey=pendingKey;documentFormat=pendingFormat;documentRequestRestored=true;
            } else if(pendingId!=0&&"preparedPreparing".equals(pendingFormat)){
                android.widget.Toast.makeText(this,"文件准备已中断，请重新操作。",android.widget.Toast.LENGTH_LONG).show();
            } else if (pendingId!=0 && "audioPreparing".equals(pendingFormat)) {
                android.widget.Toast.makeText(this,"录音准备已中断，请重新导出。",android.widget.Toast.LENGTH_LONG).show();
            }
        }
        web = new WebView(this);
        // WebView can draw HTML underneath its own padding on edge-to-edge Android.
        // Inset a parent instead, so the web viewport and its fixed navigation both
        // stay outside system bars, cutouts and the on-screen keyboard.
        android.widget.FrameLayout content = new android.widget.FrameLayout(this);
        content.addView(web, new android.widget.FrameLayout.LayoutParams(
            android.view.ViewGroup.LayoutParams.MATCH_PARENT, android.view.ViewGroup.LayoutParams.MATCH_PARENT));
        content.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars() | android.view.WindowInsets.Type.displayCutout());
                int keyboard=insets.getInsets(android.view.WindowInsets.Type.ime()).bottom;
                view.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,keyboard));
                return android.view.WindowInsets.CONSUMED;
            }
            view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true); // App-private preference for the selected appearance.
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setAllowFileAccessFromFileURLs(false);
        web.getSettings().setAllowUniversalAccessFromFileURLs(false);
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onJsConfirm(WebView view, String url, String message, JsResult result) {
                new android.app.AlertDialog.Builder(MainActivity.this).setMessage(message)
                    .setPositiveButton("继续", (dialog, which) -> result.confirm())
                    .setNegativeButton("取消", (dialog, which) -> result.cancel())
                    .setOnCancelListener(dialog -> result.cancel()).show();
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) { return true; }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                android.net.Uri uri = request.getUrl();
                if (!"https".equals(uri.getScheme()) || !"appassets.androidplatform.net".equals(uri.getHost()))
                    return blockedAsset();
                List<String> segments = uri.getPathSegments();
                if(segments.size()==5&&"notes".equals(segments.get(0))){try{
                    String token=segments.get(1),key=segments.get(2),id=segments.get(3),sha=segments.get(4);if(!token.equals(libraries().token()))return blockedAsset();session(key);JSONObject value=recordingNotes().read(key);JSONArray entries=value.getJSONArray("entries");
                    for(int i=0;i<entries.length();i++){JSONObject e=entries.getJSONObject(i);if(id.equals(e.getString("id"))&&e.has("image")&&sha.equals(e.getJSONObject("image").getString("sha256"))){Path file=recordingNotes().verifiedImage(key,e.getJSONObject("image"));return new WebResourceResponse("image/jpeg",null,200,"OK",java.util.Collections.singletonMap("Cache-Control","no-store"),RecordingNoteImages.thumbnail(file));}}
                }catch(Exception unavailable){}return blockedAsset();}
                if (segments.isEmpty() || !"www".equals(segments.get(0))) return blockedAsset();
                StringBuilder name = new StringBuilder();
                for (String part : segments) {
                    if (part.isEmpty() || part.equals(".") || part.equals("..") || part.contains("/") || part.contains("\\")) return blockedAsset();
                    if (name.length() > 0) name.append('/');
                    name.append(part);
                }
                String asset = name.toString();
                String mime = (asset.endsWith(".js") || asset.endsWith(".mjs")) ? "text/javascript" : asset.endsWith(".css") ? "text/css" : asset.endsWith(".html") ? "text/html" : "application/octet-stream";
                try { return new WebResourceResponse(mime, "UTF-8", getAssets().open(asset)); }
                catch (java.io.IOException error) { return blockedAsset(); }
            }
        });
        web.addJavascriptInterface(new Bridge(), "CompanionNative");
        setContentView(content);
        web.loadUrl("https://appassets.androidplatform.net/www/index.html");
        if(state==null)receiveIncoming(getIntent());
    }
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);receiveIncoming(intent);}
    private IncomingFileQueue incomingFiles(){return new IncomingFileQueue(root(),MainActivity::syncLifecycleDirectory);}
    private void receiveIncoming(Intent intent){
        if(intent==null||!java.util.Arrays.asList(Intent.ACTION_SEND,Intent.ACTION_SEND_MULTIPLE,Intent.ACTION_VIEW).contains(intent.getAction()))return;
        // Clear the Activity's launch intent; recreating its WebView must not deliver it again.
        setIntent(new Intent(this,MainActivity.class).setAction(Intent.ACTION_MAIN));
        worker.execute(()->{try{
            java.util.List<android.net.Uri> uris=new java.util.ArrayList<>();
            if(Intent.ACTION_VIEW.equals(intent.getAction())){if(intent.getData()!=null)uris.add(intent.getData());}
            else if(Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction())){java.util.ArrayList<android.os.Parcelable> supplied=intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);if(supplied!=null)for(android.os.Parcelable item:supplied){if(!(item instanceof android.net.Uri))throw new java.io.IOException("分享内容不是可读取的文件，请另存后重试。");uris.add((android.net.Uri)item);}}
            else {android.os.Parcelable supplied=intent.getParcelableExtra(Intent.EXTRA_STREAM);if(supplied instanceof android.net.Uri)uris.add((android.net.Uri)supplied);}
            if(uris.isEmpty()&&intent.getClipData()!=null)for(int i=0;i<intent.getClipData().getItemCount();i++){android.net.Uri uri=intent.getClipData().getItemAt(i).getUri();if(uri!=null)uris.add(uri);}
            if(uris.isEmpty()||uris.size()>16)throw new java.io.IOException("请分享1至16个实际文件；文字消息或网页链接请先另存为文件。");
            JSONArray files=new JSONArray();
            for(android.net.Uri uri:uris){
                if(!"content".equals(uri.getScheme())||uri.toString().length()>8192)throw new java.io.IOException("只接收应用明确分享的文件，不自动读取网页或本机路径。");
                String name=null,mime=getContentResolver().getType(uri);long bytes=-1;
                try(android.database.Cursor cursor=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME,android.provider.OpenableColumns.SIZE},null,null,null)){
                    if(cursor!=null&&cursor.moveToFirst()){int n=cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME),z=cursor.getColumnIndex(android.provider.OpenableColumns.SIZE);if(n>=0&&!cursor.isNull(n))name=cursor.getString(n);if(z>=0&&!cursor.isNull(z))bytes=cursor.getLong(z);}
                }
                if(name==null||name.trim().isEmpty())throw new java.io.IOException("无法确认分享文件名称，请先另存后再分享。");
                name=name.replaceAll("[\\p{Cntrl}]"," ").trim();if(name.length()>200)throw new java.io.IOException("文件名称超过200字，请改名后重新分享。");
                if(mime==null)mime=intent.getType();if(mime==null||mime.length()>256)mime="application/octet-stream";
                files.put(new JSONObject().put("uri",uri.toString()).put("name",name).put("mime",mime).put("bytes",bytes));
            }
            incomingFiles().receive(files);
            runOnUiThread(()->{if(!isFinishing()&&!isDestroyed()){android.widget.Toast.makeText(this,"文件已加入待接收清单，请确认资料库和所属会议后导入。",android.widget.Toast.LENGTH_LONG).show();web.evaluateJavascript("window.dispatchEvent(new Event('companion-incoming'))",null);}});
        }catch(Exception error){String message=error.getMessage();runOnUiThread(()->android.widget.Toast.makeText(this,message!=null&&message.matches("(?s).*[\\u4e00-\\u9fff].*")?message:"无法读取分享文件，请在来源应用中另存后重新分享。已有资料未改变。",android.widget.Toast.LENGTH_LONG).show());}});
    }
    private JSONObject incomingDescription()throws Exception{
        IncomingFileQueue queue=incomingFiles();JSONObject job=AudioImportService.status(this);JSONArray rows=queue.list();
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);if("attempting".equals(row.getString("state"))&&!AudioImportService.isRunning()){
            boolean matching=row.getString("id").equals(job.optString("incomingId")),completed=matching&&"complete".equals(job.optString("state"));
            String message=completed?"已保存在指定资料库。":matching&&("cancelled".equals(job.optString("state"))||"failed".equals(job.optString("state")))&&!job.optString("message").isEmpty()?job.getString("message"):"上次接收尚未确认完成，可在原资料库重试；若来源权限已失效，请重新分享。";
            queue.state(row.getString("id"),completed?"complete":"failed",message);
        }}
        JSONObject library=libraries().status();String active=library.getString("activeId"),label="原始资料库";
        if(!"original".equals(active)){
            label="恢复的资料库";JSONArray known=library.getJSONArray("libraries");
            for(int i=0;i<known.length();i++){JSONObject item=known.getJSONObject(i);if(active.equals(item.getString("id"))){long restoredAt=item.getLong("restoredAt");if(restoredAt>0)label+=" · "+new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm",java.util.Locale.CHINA).format(new java.util.Date(restoredAt));break;}}
        }
        return new JSONObject().put("rows",queue.list()).put("libraryId",active).put("libraryToken",library.getString("token")).put("libraryLabel",label).put("running",AudioImportService.isRunning());
    }
    private JSONObject importIncoming(JSONObject args)throws Exception{
        requireLibraryIdle();if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("正在保存其它资料，请稍后重试。");boolean locked=true;
        try{
            LocalLibraryBackups library=libraries();String token=args.getString("libraryToken");if(!token.equals(library.token()))throw new java.io.IOException("资料库已切换，请重新确认接收目标。");
            IncomingFileQueue queue=incomingFiles();String id=args.getString("id");JSONObject row=queue.get(id);String kind=row.getString("kind"),key=args.optString("key",""),title;
            if("unsupported".equals(kind))throw new java.io.IOException("暂不支持此文件格式，请使用音视频、PDF、Office文档或常见图片。");
            RecordingLibrary.Session selected=null;
            if("media".equals(kind)){key=com.denzic.companion.mobile.ImportedAudio.hash(id.getBytes(java.nio.charset.StandardCharsets.UTF_8))+":1:1";title="新录音 · "+row.getString("name");}
            else {selected=session(key);title=recordingTitle(key,selected);}
            row=queue.bind(id,library.status().getString("activeId"),key,title);
            if("complete".equals(row.getString("state")))return incomingDescription();
            queue.state(id,"attempting","正在保存原文件，离开页面后请查看接收结果。");
            if("media".equals(kind)){
                // The existing foreground importer owns decoding, cancellation and publication.
                LocalLibraryBackups.BUSY.set(false);locked=false;
                AudioImportService.startIncoming(this,id,token);
            }else{
                android.net.Uri uri=android.net.Uri.parse(row.getString("uri"));
                if("document".equals(kind)){
                    JSONObject docs=documentContexts().read(key);JSONArray entries=docs.getJSONArray("rows");boolean saved=false;
                    for(int i=0;i<entries.length();i++)if(id.equals(entries.getJSONObject(i).getString("id"))){if(!row.getString("name").equals(entries.getJSONObject(i).getString("name")))throw new java.io.IOException("接收记录与已保存材料不符，原资料保留。");documentContexts().original(key,docs.getLong("revision"),id);saved=true;}
                    if(!saved)try(java.io.InputStream input=getContentResolver().openInputStream(uri)){if(input==null)throw new java.io.IOException("来源权限已失效，请重新分享原文件。");documentContexts().add(key,docs.getLong("revision"),id,row.getString("name"),input);}
                }else if("image".equals(kind)){
                    if(!recordingNotes().incomingImagePresent(key,id,row.getString("name"))){JSONObject notes=recordingNotes().read(key);final String extension=IncomingFileQueue.imageExtension(row);try(java.io.InputStream input=getContentResolver().openInputStream(uri)){if(input==null)throw new java.io.IOException("来源权限已失效，请重新分享原图片。");recordingNotes().addIncomingImage(key,notes.getLong("revision"),id,row.getString("name"),extension,input,path->RecordingNoteImages.validate(path,extension));}}
                }
                else throw new java.io.IOException("暂不支持此文件格式，请使用音视频、PDF、Office文档或常见图片。");
                queue.state(id,"complete","原文件已保存到“"+title+"”，可在补充材料中查看。");
            }
            return incomingDescription();
        }catch(Exception error){
            try{JSONObject row=incomingFiles().get(args.getString("id"));if("attempting".equals(row.getString("state")))incomingFiles().state(row.getString("id"),"failed","保存尚未确认，可在原目标重试；来源文件未改变。");}catch(Exception ignored){}
            if(error instanceof SecurityException||error instanceof java.io.FileNotFoundException)throw new java.io.IOException("来源文件已不可读取，请在来源应用重新分享。已有资料未改变。",error);
            throw error;
        }finally{if(locked)LocalLibraryBackups.BUSY.set(false);}
    }
    private static WebResourceResponse blockedAsset() {
        return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", java.util.Collections.singletonMap("Cache-Control","no-store"), new ByteArrayInputStream(new byte[0]));
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        state.putLong("noteImageRequestId",noteImageRequestId);
        state.putLong("audioImportRequestId",audioImportRequestId);state.putString("audioImportLibraryToken",audioImportLibraryToken);
        state.putLong("updateRequestId",updateRequestId);
        state.putLong("libraryRequestId",libraryRequestId);state.putString("libraryRequestKind",libraryRequestKind);state.putString("libraryRequestToken",libraryRequestToken);state.putString("documentLibraryToken",documentLibraryToken);state.putString("documentPreparedId",documentPreparedId);
        if (documentRequestId!=0) {
            state.putLong("documentRequestId",documentRequestId);
            state.putString("documentKey",documentKey);
            state.putString("documentFormat",documentFormat);
        }
    }
    @Override protected void onResume() {
        super.onResume();
        notifySystemAppearance();
        if(noteImageRestored&&noteImageRequestId!=0){noteImageRequestId=0;noteImageRestored=false;android.widget.Toast.makeText(this,"文件选择已中断，请重新选择；已保存材料和备注仍保留。",android.widget.Toast.LENGTH_LONG).show();}
        if(audioImportRequestRestored&&audioImportRequestId!=0){audioImportRequestId=0;audioImportRequestRestored=false;audioImportLibraryToken=null;android.widget.Toast.makeText(this,"文件选择已中断，请重新选择导入；原文件未改变。",android.widget.Toast.LENGTH_LONG).show();}
        if(updateRequestRestored&&updateRequestId!=0){updateRequestId=0;updateRequestRestored=false;android.widget.Toast.makeText(this,"升级包选择已中断，请重新选择。设备保持原状态。",android.widget.Toast.LENGTH_LONG).show();}
        if(libraryRequestRestored&&libraryRequestId!=0){libraryRequestId=0;libraryRequestKind=null;libraryRequestToken=null;libraryRequestRestored=false;android.widget.Toast.makeText(this,"备份文件选择已中断，原资料仍保留，请重新操作。",android.widget.Toast.LENGTH_LONG).show();}
        // If a restored picker never delivers a result, do not block future exports.
        // Android delivers an activity result before the following onResume.
        if (documentRequestRestored && documentRequestId!=0) {
            documentRequestId=0;documentKey=null;documentFormat=null;documentRequestRestored=false;
            android.widget.Toast.makeText(this,"文件选择已中断，请检查保存位置后重试。",android.widget.Toast.LENGTH_LONG).show();
        }
    }
    @Override protected void onStop(){
        if(!worker.isShutdown())worker.execute(()->{savePlaybackProgress(true);closeSelectedDevice();});
        super.onStop();
    }
    @Override protected void onDestroy() {
        meetingAi.cancelAll();
        worker.execute(()->{closeSelectedDevice();stopPlayback();});
        web.removeJavascriptInterface("CompanionNative");
        worker.shutdown();
        super.onDestroy();
    }
    @Override public void onBackPressed() { web.evaluateJavascript("window.companionBack()", null); }
    @Override public void onConfigurationChanged(android.content.res.Configuration configuration){super.onConfigurationChanged(configuration);notifySystemAppearance();}
    private boolean systemDark(){return (getResources().getConfiguration().uiMode&android.content.res.Configuration.UI_MODE_NIGHT_MASK)==android.content.res.Configuration.UI_MODE_NIGHT_YES;}
    private void notifySystemAppearance(){if(web!=null)web.evaluateJavascript("if(typeof window.companionSystemAppearance==='function')window.companionSystemAppearance("+systemDark()+")",null);}
    private android.content.SharedPreferences userPreferences(){return getSharedPreferences("companion-user-preferences",MODE_PRIVATE);}
    private JSONObject appPreferences()throws Exception{
        android.content.SharedPreferences prefs=userPreferences();double speed=prefs.getFloat("defaultPlaybackSpeed",1);
        if(!PlaybackProgress.validSpeed(speed))throw new java.io.IOException("回听设置暂时无法读取，请重新设置。");
        boolean bluetooth=Build.VERSION.SDK_INT<31||checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)==PackageManager.PERMISSION_GRANTED;
        boolean notifications=(Build.VERSION.SDK_INT<33||checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED)&&getSystemService(android.app.NotificationManager.class).areNotificationsEnabled();
        return new JSONObject().put("defaultPlaybackSpeed",speed).put("resumePlayback",prefs.getBoolean("resumePlayback",true)).put("systemDark",systemDark()).put("bluetoothAllowed",bluetooth).put("notificationsAllowed",notifications).put("version",getPackageManager().getPackageInfo(getPackageName(),0).versionName);
    }
    private JSONObject savedPlaybackProgress(RecordingLibrary.Session selected,String key,long duration)throws Exception{
        JSONObject result=new PlaybackProgress(libraries().meetings(),MainActivity::syncLifecycleDirectory).load(key,RecordingBookmarkAccess.binding(selected),duration),prefs=appPreferences();
        if(!result.getBoolean("saved"))result.put("speed",prefs.getDouble("defaultPlaybackSpeed"));
        if(!prefs.getBoolean("resumePlayback"))result.put("positionMs",0);
        return result;
    }
    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if(requestCode==35){finishNoteImagePicker(resultCode,data);return;}
        if(requestCode==34){finishAudioImportPicker(resultCode,data);return;}
        if(requestCode==33){finishUpdatePicker(resultCode,data);return;}
        if(requestCode==32){finishLibraryPicker(resultCode,data);return;}
        if (requestCode != 31) return;
        final long id=documentRequestId; final String key=documentKey, format=documentFormat;
        final boolean restored=documentRequestRestored;
        final String libraryToken=documentLibraryToken;documentLibraryToken=null;final String preparedId=documentPreparedId;documentPreparedId=null;
        documentRequestId=0; documentKey=null; documentFormat=null;documentRequestRestored=false;
        if (id==0 || key==null || !DocumentRecovery.isPickerFormat(format)) return;
        if (resultCode!=RESULT_OK || data==null || data.getData()==null) { replyDocument(id,false,null,restored); return; }
        android.net.Uri destination=data.getData();
        worker.execute(() -> {
            try {
                if(LocalLibraryBackups.BUSY.get()||libraryToken==null||!libraryToken.equals(libraries().token()))throw new java.io.IOException("资料已切换，请重新选择要导出的录音。");
                if("prepared".equals(format)){
                    PreparedExports exports=preparedExports();PreparedExports.Entry entry=exports.load(preparedId,true);exports.requireLibrary(entry,libraryToken);lifecycle().requireVisible(entry.meta.getString("key"));if(!key.equals(entry.meta.getString("key")))throw new java.io.IOException("文件来源已变化，请重新操作。");
                    try(java.io.OutputStream out=getContentResolver().openOutputStream(destination,"w")){if(out==null)throw new java.io.IOException("无法写入所选位置。");exports.write(entry,out);}
                    replyDocument(id,true,null,restored);return;
                }
                RecordingLibrary.Session original=session(key);
                if("marks".equals(format)){
                    NativeAudio.VerifiedPrefix prefix=NativeAudio.inspectPrefix(original);
                    JSONObject marks=RecordingBookmarkAccess.describe(key,libraries().token(),RecordingBookmarkAccess.binding(original),prefix);
                    byte[] text=RecordingBookmarkAccess.text(recordingTitle(key,original),marks);
                    try(java.io.OutputStream out=getContentResolver().openOutputStream(destination,"w")){if(out==null)throw new java.io.IOException("无法写入所选位置。");out.write(text);}
                    replyDocument(id,true,null,restored);return;
                }
                if ("audio".equals(format) || "audioZip".equals(format)) {
                    NativeAudio.PartsResult parts=ManagedAudioParts.prepare(original,root().resolve("companion-decoded-audio"));
                    if (parts.parts.isEmpty() || ("audio".equals(format) && parts.parts.size()!=1))
                        throw new java.io.IOException("录音分段发生变化，请重新导出。");
                    try (java.io.OutputStream out=getContentResolver().openOutputStream(destination,"w")) {
                        if(out==null)throw new java.io.IOException("无法写入所选位置。");
                        List<Path> audioPaths=new ArrayList<>();
                        for(NativeAudio.Part part:parts.parts)audioPaths.add(part.path);
                        AudioExport.write(audioPaths,out,"audioZip".equals(format));
                    }
                    replyDocument(id,new JSONObject().put("saved",true).put("complete",parts.captureComplete).put("parts",parts.parts.size()),null,restored);
                    return;
                }
                String title=recordingTitle(key,original); MeetingStore ms=store(); MeetingStore.Snapshot meeting=ms.load(key); MeetingStore.Minutes minutes=ms.loadMinutes(key);
                if (meeting==null) throw new IllegalStateException("没有可导出的已保存内容。");
                boolean hasText=meeting.transcript!=null&&!meeting.transcript.trim().isEmpty();
                boolean hasNotes=(meeting.notes!=null&&!meeting.notes.trim().isEmpty())||!meeting.tasks.isEmpty();
                if ("pdf".equals(format) && minutes==null && !hasText && !hasNotes) throw new IllegalStateException("没有可导出的已保存内容。");
                byte[] bytes=null;
                if ("word".equals(format)) bytes=NativeMeetingDocuments.word(title,minutes,meeting);
                if ("mindmap".equals(format)) bytes=NativeMeetingDocuments.mindmap(title,minutes,meeting);
                try (java.io.OutputStream out=getContentResolver().openOutputStream(destination,"w")) {
                    if (out==null) throw new java.io.IOException("无法写入所选位置。");
                    if ("pdf".equals(format)) MeetingPdf.write(title,minutes,meeting,new MeetingPdf.Sections(minutes!=null,hasText,hasNotes),out,
                        android.graphics.Typeface.createFromAsset(getAssets(),"companion-documents/CompanionPDFSans-Regular.ttf"));
                    else out.write(bytes);
                }
                replyDocument(id,true,null,restored);
            } catch(Exception e) { replyDocument(id,null,"导出未完成；所选位置可能留有不完整文件。"+(e.getMessage()==null?"":e.getMessage()),restored); }
        });
    }
    private DocumentContextStore documentContexts()throws Exception{return new DocumentContextStore(libraries().meetings(),MainActivity::syncLifecycleDirectory);}
    private JSONObject documentDescription(String key)throws Exception{return documentContexts().read(key).put("libraryToken",libraries().token());}
    private RecordingNotes recordingNotes()throws Exception{return new RecordingNotes(libraries().meetings(),MainActivity::syncLifecycleDirectory);}
    private RecordingLibrary.Session noteSession(JSONObject a)throws Exception{
        if(!a.getString("libraryToken").equals(libraries().token()))throw new java.io.IOException("资料库已切换，请重新打开这条录音；输入尚未保存。");return session(a.getString("key"));
    }
    private static String manualNoteKind(JSONObject a)throws Exception{return !a.has("kind")||a.isNull("kind")?null:a.getString("kind");}
    private static JSONArray manualNoteReferences(JSONObject a)throws Exception{return !a.has("references")||a.isNull("references")?null:a.getJSONArray("references");}
    private void verifyManualEvidence(String key,JSONObject reference)throws Exception {
        if("document".equals(reference.getString("kind"))){
            JSONObject value=documentContexts().read(key),entry=null;JSONArray rows=value.getJSONArray("rows");
            for(int i=0;i<rows.length();i++)if(reference.getString("documentId").equals(rows.getJSONObject(i).getString("id")))entry=rows.getJSONObject(i);
            if(entry==null)throw new java.io.IOException("这份材料已移除；已有引文仍保留，请重新选择新的依据。");
            ManualNoteContext.verifyDocument(reference,entry,documentContexts().extraction(key,value.getLong("revision"),entry.getString("id")));
        }else{
            MeetingStore.Snapshot saved=store().load(key);if(saved==null||saved.transcript.trim().isEmpty())throw new java.io.IOException("这场会议的转写暂不可读取；已有引文仍保留。");
            ManualNoteContext.verifyTranscript(reference,saved.transcript);
        }
    }
    private static Long noteTime(JSONObject a)throws Exception{return !a.has("atMs")||a.isNull("atMs")?null:a.getLong("atMs");}
    private JSONObject noteDescription(String key)throws Exception{
        JSONObject value=recordingNotes().read(key);return value.put("libraryToken",libraries().token());
    }
    private void finishNoteImagePicker(int resultCode,Intent data){
        final long id=noteImageRequestId;final JSONObject args=noteImageRequest;final boolean restored=noteImageRestored;noteImageRequestId=0;noteImageRequest=null;noteImageRestored=false;
        if(id==0)return;if(restored||args==null){android.widget.Toast.makeText(this,"文件选择已中断，请重新选择；已保存材料和备注仍保留。",android.widget.Toast.LENGTH_LONG).show();return;}
        if(resultCode!=RESULT_OK||data==null||data.getData()==null){try{reply(id,new JSONObject().put("cancelled",true),null);}catch(Exception ignored){}return;}
        final android.net.Uri uri=data.getData();worker.execute(()->{boolean locked=false;try{
            if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("正在保存其它资料，请稍后重试；输入仍保留。");locked=true;RecordingLibrary.Session selected=noteSession(args);String key=args.getString("key");
            if("document".equals(args.optString("attachmentKind"))){
                String name=null;try(android.database.Cursor cursor=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);}
                if(name==null)throw new java.io.IOException("无法确认文档名称和格式，请另存后重试。");
                try(java.io.InputStream input=getContentResolver().openInputStream(uri)){if(input==null)throw new java.io.IOException("所选文档暂不可读取。");documentContexts().add(key,args.getLong("revision"),args.getString("id"),name,input);}
                reply(id,documentDescription(key),null);return;
            }
            String mime=getContentResolver().getType(uri),extension="image/jpeg".equals(mime)?"jpg":"image/png".equals(mime)?"png":"image/webp".equals(mime)?"webp":null;
            if(extension==null)throw new java.io.IOException("请选择JPEG、PNG或WebP图片。");String name="图片."+extension;
            try(android.database.Cursor cursor=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);}
            final String type=extension;try(java.io.InputStream input=getContentResolver().openInputStream(uri)){if(input==null)throw new java.io.IOException("所选图片暂不可读取。");recordingNotes().addImageContext(key,args.getLong("revision"),args.optString("text",""),noteTime(args),completeAudioDurationMs(selected),name,extension,input,path->RecordingNoteImages.validate(path,type),manualNoteKind(args),manualNoteReferences(args),reference->verifyManualEvidence(key,reference));}
            reply(id,noteDescription(key),null);
        }catch(Exception e){reply(id,null,e.getMessage()==null?"图片保存未完成，输入仍保留，请重试。":e.getMessage());}finally{if(locked)LocalLibraryBackups.BUSY.set(false);}});
    }
    private void finishAudioImportPicker(int resultCode,Intent data){
        final long id=audioImportRequestId;final String token=audioImportLibraryToken;final boolean restored=audioImportRequestRestored;audioImportRequestId=0;audioImportLibraryToken=null;audioImportRequestRestored=false;
        if(id==0)return;if(resultCode!=RESULT_OK||data==null||data.getData()==null){if(!restored)reply(id,false,null);return;}
        try{AudioImportService.start(this,data.getData(),token);if(!restored)reply(id,new JSONObject().put("started",true),null);else android.widget.Toast.makeText(this,"正在导入，进度可在录音库查看。",android.widget.Toast.LENGTH_LONG).show();}
        catch(Exception e){if(!restored)reply(id,null,e.getMessage());else android.widget.Toast.makeText(this,e.getMessage(),android.widget.Toast.LENGTH_LONG).show();}
    }
    private void requireLibraryIdle() throws Exception {
        if(AudioImportService.isRunning())throw new java.io.IOException("正在导入录音，请等完成或取消后再操作资料。");
        if(DeviceUpdateService.isRunning())throw new java.io.IOException("正在升级录音卡，请等待完成后再操作资料备份。");
        if(RecordingSyncService.isRunning())throw new java.io.IOException("正在接收录音，请等待完成或暂停接收后再操作资料备份。");
    }
    private void libraryReply(long id,Object value,String error,boolean restored){
        if(!restored){reply(id,value,error);return;}
        String message=error!=null?error:Boolean.FALSE.equals(value)?"已取消，原资料仍保留。":"备份操作已完成，请刷新录音库查看。";
        runOnUiThread(()->{
            if(!isFinishing()&&!isDestroyed())web.evaluateJavascript("window.companionProgress?.('');window.companionLibraryChanged?.();",null);
            android.widget.Toast.makeText(this,message,android.widget.Toast.LENGTH_LONG).show();
        });
    }
    private void finishLibraryPicker(int resultCode,Intent data){
        final long id=libraryRequestId;final String kind=libraryRequestKind,token=libraryRequestToken;final boolean restored=libraryRequestRestored;
        libraryRequestId=0;libraryRequestKind=null;libraryRequestToken=null;libraryRequestRestored=false;
        if(id==0||token==null||!("backup".equals(kind)||"restore".equals(kind)))return;
        if(resultCode!=RESULT_OK||data==null||data.getData()==null){libraryReply(id,false,null,restored);return;}
        final android.net.Uri uri=data.getData();worker.execute(()->{
            if(!LocalLibraryBackups.BUSY.compareAndSet(false,true)){libraryReply(id,null,"另一个资料操作正在进行，请稍后重试。",restored);return;}
            try{
                requireLibraryIdle();stopPlayback();progress("backup".equals(kind)?"正在备份本机资料":"正在校验并恢复资料");
                if("backup".equals(kind)){
                    try(java.io.OutputStream out=getContentResolver().openOutputStream(uri,"w")){if(out==null)throw new java.io.IOException("无法写入所选位置。");libraries().write(out,token);}
                    libraryReply(id,new JSONObject().put("saved",true).put("kind","backup"),null,restored);
                }else{
                    JSONObject result;try(java.io.InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new java.io.IOException("无法读取所选备份。");result=libraries().restore(in,token);}
                    selectedDevice=null;segments=new ArrayList<>();libraryReply(id,new JSONObject().put("saved",true).put("kind","restore").put("library",result),null,restored);
                }
            }catch(Exception error){libraryReply(id,null,("backup".equals(kind)?"备份未完成，所选位置可能留有不完整文件；":"恢复未完成，原资料仍保留；")+(error.getMessage()==null?"请重试。":error.getMessage()),restored);}
            finally{LocalLibraryBackups.BUSY.set(false);}
        });
    }
    private void replyDocument(long id,Object result,String error,boolean restored) {
        if (!restored) { reply(id,result,error);return; }
        boolean saved=Boolean.TRUE.equals(result) || result instanceof JSONObject;
        boolean complete=!(result instanceof JSONObject) || ((JSONObject)result).optBoolean("complete",true);
        String message=DocumentRecovery.notice(saved,complete,error);
        runOnUiThread(() -> android.widget.Toast.makeText(getApplicationContext(),message,android.widget.Toast.LENGTH_LONG).show());
    }
    private void reply(long id, Object result, String error) {
        try {
            JSONObject envelope = new JSONObject().put("id", id).put("result", result == null ? JSONObject.NULL : result)
                    .put("error", error == null ? JSONObject.NULL : error);
            runOnUiThread(() -> { if (!isFinishing() && !isDestroyed()) web.evaluateJavascript("window.companionReply(" + envelope + ")", null); });
        } catch (Exception ignored) { }
    }
    private boolean bluetoothGranted() {
        if (Build.VERSION.SDK_INT >= 31) return checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        return true;
    }
    private final class Bridge {
        @JavascriptInterface public void pickContextDocument(long id,String json){
            worker.execute(()->{try{JSONObject args=new JSONObject(json);noteSession(args);args.put("attachmentKind","document");if(LocalLibraryBackups.BUSY.get())throw new java.io.IOException("资料正在保存，请稍后重试。");runOnUiThread(()->{
                if(isFinishing()||isDestroyed())return;if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0||noteImageRequestId!=0){reply(id,null,"已有文件选择操作正在进行。");return;}
                noteImageRequestId=id;noteImageRequest=args;noteImageRestored=false;try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","application/vnd.openxmlformats-officedocument.presentationml.presentation","text/plain","text/markdown","text/csv"}),35);}catch(Exception e){noteImageRequestId=0;noteImageRequest=null;reply(id,null,"无法打开系统文档选择器，请重试。");}
            });}catch(Exception e){reply(id,null,e.getMessage());}});
        }
        @JavascriptInterface public void pickNoteImage(long id,String json){
            worker.execute(()->{try{JSONObject args=new JSONObject(json);noteSession(args);if(LocalLibraryBackups.BUSY.get())throw new java.io.IOException("资料正在保存，请稍后重试。");runOnUiThread(()->{
                if(isFinishing()||isDestroyed())return;if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0||noteImageRequestId!=0){reply(id,null,"已有文件选择操作正在进行。");return;}
                noteImageRequestId=id;noteImageRequest=args;noteImageRestored=false;try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/*").putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"image/jpeg","image/png","image/webp"}),35);}catch(Exception e){noteImageRequestId=0;noteImageRequest=null;reply(id,null,"无法打开系统图片选择器，输入仍保留。");}
            });}catch(Exception e){reply(id,null,e.getMessage());}});
        }
        @JavascriptInterface public void cancelAudioImport(){AudioImportService.cancel();}
        @JavascriptInterface public void pickAudioImport(long id,String token){
            worker.execute(()->{try{requireLibraryIdle();if(LocalLibraryBackups.BUSY.get()||!token.equals(libraries().token()))throw new java.io.IOException("资料库已变化或正在更新，请稍后重试。");runOnUiThread(()->{
                if(isFinishing()||isDestroyed())return;if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0||noteImageRequestId!=0){reply(id,null,"已有文件选择操作正在进行。");return;}
                audioImportRequestId=id;audioImportLibraryToken=token;audioImportRequestRestored=false;try{Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"audio/*","video/*"});startActivityForResult(intent,34);}catch(Exception e){audioImportRequestId=0;audioImportLibraryToken=null;reply(id,null,"无法打开系统文件选择器，请重试。");}
            });}catch(Exception e){reply(id,null,e.getMessage());}});
        }
        @JavascriptInterface public void libraryArchive(long id,String kind,String token){
            worker.execute(()->{
                try{
                    requireLibraryIdle();if(LocalLibraryBackups.BUSY.get())throw new java.io.IOException("资料操作正在进行，请稍后重试。");
                    if(!token.equals(libraries().token()))throw new java.io.IOException("资料已变化，请刷新备份页面后重试。");
                    if(!("backup".equals(kind)||"restore".equals(kind)))throw new java.io.IOException("不支持的资料操作。");
                    runOnUiThread(()->{
                        if(isFinishing()||isDestroyed())return;
                        if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||audioImportRequestId!=0||noteImageRequestId!=0){reply(id,null,"已有文件选择操作正在进行。");return;}
                        libraryRequestId=id;libraryRequestKind=kind;libraryRequestToken=token;libraryRequestRestored=false;
                        try{
                            Intent intent=new Intent("backup".equals(kind)?Intent.ACTION_CREATE_DOCUMENT:Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/zip");
                            if("backup".equals(kind))intent.putExtra(Intent.EXTRA_TITLE,"Companion-本机资料备份-"+java.time.LocalDate.now()+".zip");
                            startActivityForResult(intent,32);
                        }catch(Exception error){libraryRequestId=0;libraryRequestKind=null;libraryRequestToken=null;reply(id,null,"无法打开系统文件选择器，原资料仍保留。");}
                    });
                }catch(Exception error){reply(id,null,error.getMessage()==null?"暂时无法操作备份，请重试。":error.getMessage());}
            });
        }
        @JavascriptInterface public void setAppearance(String theme) {
            boolean dark = "dark".equals(theme);
            runOnUiThread(() -> {
                android.view.Window window = getWindow();
                int background = android.graphics.Color.parseColor(dark ? "#15151a" : "#f8f7f5");
                int navigation = android.graphics.Color.parseColor(dark ? "#202027" : "#ffffff");
                window.getDecorView().setBackgroundColor(background);
                if (web != null) web.setBackgroundColor(background); // Keep inset areas in the selected theme.
                window.setStatusBarColor(background);
                window.setNavigationBarColor(navigation);
                if (Build.VERSION.SDK_INT >= 30) {
                    android.view.WindowInsetsController controller=window.getInsetsController();
                    if(controller!=null) {
                        int bars=android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                        controller.setSystemBarsAppearance(dark ? 0 : bars,bars);
                    }
                } else {
                    android.view.View decor=window.getDecorView();
                    int bars=android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                    int flags=decor.getSystemUiVisibility();
                    decor.setSystemUiVisibility(dark ? flags & ~bars : flags | bars);
                }
            });
        }
        @JavascriptInterface public void finishApp() { runOnUiThread(MainActivity.this::finish); }
        @JavascriptInterface public void pickDeviceUpdate(long id){runOnUiThread(()->{
            if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||LocalLibraryBackups.BUSY.get()||RecordingSyncService.isRunning()||DeviceUpdateService.isRunning()){reply(id,null,"已有文件选择、接收或升级正在进行，请等待完成。");return;}
            updateRequestId=id;updateRequestRestored=false;
            try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/zip"),33);}
            catch(Exception e){updateRequestId=0;reply(id,null,"无法打开升级包选择器。");}
        });}
        @JavascriptInterface public void openBluetoothSettings() {
            runOnUiThread(() -> {
                try { startActivity(new Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS)); }
                catch (android.content.ActivityNotFoundException error) { android.widget.Toast.makeText(MainActivity.this,"无法打开手机蓝牙设置，请在系统设置中配对。",android.widget.Toast.LENGTH_LONG).show(); }
            });
        }
        @JavascriptInterface public void exportDocument(long id, String key, String format) {
            runOnUiThread(() -> {
                if (documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||LocalLibraryBackups.BUSY.get()) { reply(id,null,"已有文件选择或资料操作正在进行。"); return; }
                String mime, extension;
                if ("pdf".equals(format)) { mime="application/pdf";extension="pdf"; }
                else if ("word".equals(format)) { mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document";extension="docx"; }
                else if ("mindmap".equals(format)) { mime="application/x-freemind";extension="mm"; }
                else if ("marks".equals(format)) { mime="text/plain";extension="txt"; }
                else { reply(id,null,"不支持的导出格式。");return; }
                documentRequestId=id;documentKey=key;documentFormat=format;documentRequestRestored=false;
                try {
                    documentLibraryToken=libraries().token();
                    Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(mime).putExtra(Intent.EXTRA_TITLE,"Companion-录音."+extension);
                    startActivityForResult(intent,31);
                } catch (Exception error) {documentRequestId=0;documentKey=null;documentFormat=null;reply(id,null,"无法打开文件选择器。");}
            });
        }
        @JavascriptInterface public void exportPrepared(long id,String preparedId){
            runOnUiThread(()->{
                if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||LocalLibraryBackups.BUSY.get()){reply(id,null,"已有文件选择或资料操作正在进行。");return;}
                documentRequestId=id;documentFormat="preparedPreparing";documentPreparedId=preparedId;documentRequestRestored=false;
                worker.execute(()->{try{
                    PreparedExports exports=preparedExports();PreparedExports.Entry entry=exports.load(preparedId,true);exports.requireLibrary(entry,libraries().token());lifecycle().requireVisible(entry.meta.getString("key"));
                    String key=entry.meta.getString("key"),token=entry.meta.getString("libraryToken"),mime=entry.meta.getString("mime"),filename=entry.meta.getString("filename");
                    runOnUiThread(()->{if(isFinishing()||isDestroyed())return;documentKey=key;documentLibraryToken=token;documentFormat="prepared";
                        try{startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(mime).putExtra(Intent.EXTRA_TITLE,filename),31);}
                        catch(Exception error){documentRequestId=0;documentPreparedId=null;documentKey=null;documentFormat=null;reply(id,null,"无法打开文件选择器。");}});
                }catch(Exception error){runOnUiThread(()->{documentRequestId=0;documentPreparedId=null;documentKey=null;documentFormat=null;reply(id,null,error.getMessage()==null?"文件准备失败，请重新操作。":error.getMessage());});}});
            });
        }
        @JavascriptInterface public void exportAudio(long id,String key) {
            runOnUiThread(() -> {
                if (documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0||LocalLibraryBackups.BUSY.get()) { reply(id,null,"已有文件选择或资料操作正在进行。");return; }
                documentRequestId=id;documentKey=key;documentFormat="audioPreparing";documentRequestRestored=false;
                worker.execute(() -> {
                    try {
                        documentLibraryToken=libraries().token();
                        RecordingLibrary.Session original=session(key);
                        NativeAudio.PartsResult parts=ManagedAudioParts.prepare(original,root().resolve("companion-decoded-audio"));
                        if(parts.parts.isEmpty())throw new IllegalStateException("没有可导出的音频。");
                        boolean multiple=parts.parts.size()>1;
                        String title;
                        try { title=recordingTitle(key,original); } catch(java.io.IOException unreadable) { title="Companion-录音"; }
                        String filename=DocumentNames.audio(title,multiple);
                        runOnUiThread(() -> {
                            if(isFinishing() || isDestroyed())return;
                            documentFormat=multiple?"audioZip":"audio";
                            try {
                                Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                                    .setType(multiple?"application/zip":"audio/wav")
                                    .putExtra(Intent.EXTRA_TITLE,filename);
                                startActivityForResult(intent,31);
                            } catch(Exception error) {
                                documentRequestId=0;documentKey=null;documentFormat=null;reply(id,null,"无法打开文件选择器。");
                            }
                        });
                    } catch(Exception error) {
                        runOnUiThread(() -> {documentRequestId=0;documentKey=null;documentFormat=null;
                            reply(id,null,error.getMessage()==null?"音频准备失败，原录音已保留。":error.getMessage());});
                    }
                });
            });
        }
        @JavascriptInterface public void copyTranslation(String text) {
            if(text==null || text.trim().isEmpty() || text.length()>200000)return;
            runOnUiThread(() -> {
                android.content.ClipboardManager clipboard=(android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE);
                if(clipboard==null){android.widget.Toast.makeText(MainActivity.this,"暂时无法复制译文。",android.widget.Toast.LENGTH_SHORT).show();return;}
                clipboard.setPrimaryClip(android.content.ClipData.newPlainText("Companion 译文",text));
                android.widget.Toast.makeText(MainActivity.this,"译文已复制。",android.widget.Toast.LENGTH_SHORT).show();
            });
        }
        @JavascriptInterface public void cancelTranscription() { cancelTranscription.set(true); }
        @JavascriptInterface public void cancelMinutes() { cancelMinutes.set(true); }
        @JavascriptInterface public void permissions() {
            runOnUiThread(() -> {
                List<String> needed = new ArrayList<>();
                if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED)
                    needed.add(Manifest.permission.BLUETOOTH_CONNECT);
                if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                    needed.add(Manifest.permission.POST_NOTIFICATIONS);
                if (!needed.isEmpty()) requestPermissions(needed.toArray(new String[0]), 17);
            });
        }
        @JavascriptInterface public void openAppSettings(){runOnUiThread(()->startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+getPackageName()))));}
        @JavascriptInterface public void call(long id, String method, String json) {
            if("cancelMeetingQuestion".equals(method)){try{reply(id,meetingAi.cancel(new JSONObject(json).getString("jobId")),null);}catch(Exception e){reply(id,null,"停止查询未确认，请重试。");}return;}
            if ("transcribe".equals(method) || "transcribeCloud".equals(method)) cancelTranscription.set(false);
            if ("minutes".equals(method)) cancelMinutes.set(false);
            worker.execute(() -> {
                try { Object value=execute(method,new JSONObject(json));
                    if(("minutes".equals(method)||"translate".equals(method))&&new JSONObject(json).optString("apiKey","").isEmpty())aiServices().verified();
                    reply(id,value,null); }
                catch (java.util.concurrent.CancellationException stopped) {
                    String message="transcribeCloud".equals(method)?"已停止云端转写。已发送的音频无法撤回，原录音保留。"
                        : "minutes".equals(method)?"已停止整理。已发送的文字无法撤回，原录音和已保存内容保留。"
                        : "已停止本地转写，原录音保留。";
                    reply(id,null,message);
                }
                catch (Exception e) { reply(id, null, e.getMessage() == null ? e.toString() : e.getMessage()); }
            });
        }
    }
    private RecordingLibrary.Session session(String key) throws Exception {
        lifecycle().requireVisible(key);return storedSession(key);
    }
    private RecordingLibrary.Session storedSession(String key) throws Exception {
        for (RecordingLibrary.Session s : RecordingLibrary.inspectSession(recordings(),key).sessions)
            if (s.key().equals(key)) return s;
        throw new IllegalStateException("找不到这条本机录音，请刷新列表。");
    }
    private void requireLifecycleIdle()throws Exception{
        requireLibraryIdle();
        if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0)throw new java.io.IOException("请先完成当前文件选择，再管理录音。");
    }
    private void requirePurgeReceiptsResolved(String key)throws Exception{
        RecorderWire.Descriptor pending=RecordingLibrary.pendingConfirmation(recordings());
        if(pending!=null&&key.equals(MeetingStore.sessionKey(pending)))throw new java.io.IOException("这条录音还有未完成的设备接收确认，请先恢复并处理原确认。");
        for(RecordingLibrary.DeferredConfirmation row:RecordingLibrary.deferredConfirmations(recordings()))
            if(key.equals(MeetingStore.sessionKey(row.descriptor)))throw new java.io.IOException("这条录音有暂缓的设备接收确认，请先恢复并处理原确认。");
        if(!RecordingLibrary.unreadableConfirmations(recordings()).isEmpty())throw new java.io.IOException("有无法辨认的设备确认资料，请先备份并检查；本次未开始永久清除。");
    }
    private boolean confirmLocalPurge(JSONObject offer)throws Exception{
        java.util.concurrent.CompletableFuture<Boolean> answer=new java.util.concurrent.CompletableFuture<>();
        java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog> shown=new java.util.concurrent.atomic.AtomicReference<>();
        runOnUiThread(()->{
            if(answer.isDone())return;if(isFinishing()||isDestroyed()){answer.complete(false);return;}
            String extra=offer.optInt("retainedUnassigned")>0?"\n另有"+offer.optInt("retainedUnassigned")+"份损坏副本无法确认归属，本次保留。":"";
            android.app.AlertDialog dialog=new android.app.AlertDialog.Builder(this).setTitle("永久清除这条本机录音？")
                .setMessage(offer.optString("title")+"\n将清除当前资料库中可确认归属的原音、转写、纪要、译文与AI材料，共"+offer.optInt("files")+"个文件（约"+offer.optLong("bytes")/1024+" KiB），并清理此条录音的接收信息，无法恢复。\n录音卡、其他资料库、已导出副本和应用临时缓存不在本次范围。"+extra)
                .setNegativeButton("取消",(d,w)->answer.complete(false)).setPositiveButton("永久清除",(d,w)->answer.complete(true))
                .setOnCancelListener(d->answer.complete(false)).create();
            shown.set(dialog);dialog.setOnDismissListener(d->answer.complete(false));dialog.show();
        });
        try{return answer.get(45,java.util.concurrent.TimeUnit.SECONDS);}
        finally{answer.cancel(false);runOnUiThread(()->{android.app.AlertDialog dialog=shown.get();if(dialog!=null)dialog.dismiss();});}
    }
    private JSONObject changeLocalRecording(JSONObject a)throws Exception{
        requireLifecycleIdle();String token=a.getString("libraryToken"),key=a.getString("key"),action=a.getString("action");
        if(!token.equals(libraries().token()))throw new java.io.IOException("资料库已切换，请重新选择录音。");
        if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("资料操作正在进行。");
        try{
            LocalRecordingLifecycle lifecycle=lifecycle();long revision=a.getLong("revision");
            if(action.equals("purge")){
                requirePurgeReceiptsResolved(key);JSONObject state=lifecycle.get(key);
                if(!state.getBoolean("purging")&&storedSession(key).state!=RecordingLibrary.SessionState.COMPLETE)throw new java.io.IOException("录音尚未完整结束或接收，不能永久清除。可先恢复并补齐。");
                JSONObject offer;
                synchronized(RecordingSyncService.class){requireLifecycleIdle();offer=lifecycle.preparePurge(key,revision);}
                // No service monitor is held while waiting for the user's dialog.
                if(!confirmLocalPurge(offer))return new JSONObject().put("cancelled",true);
                synchronized(RecordingSyncService.class){requireLifecycleIdle();if(!token.equals(libraries().token()))throw new java.io.IOException("资料库已切换，本次未清除。");requirePurgeReceiptsResolved(key);incomingFiles().removeBound(libraries().status().getString("activeId"),key);return lifecycle.purge(key,revision,offer.getString("token"));}
            }
            RecordingLibrary.Session original=storedSession(key);
            String title="";if(action.equals("trash"))title=recordingTitle(key,original);
            if(action.equals("trash")){stopPlayback();playbackEvent("stopped","");}
            synchronized(RecordingSyncService.class){requireLifecycleIdle();return lifecycle.change(key,revision,action,title).put("libraryToken",token);}
        }finally{LocalLibraryBackups.BUSY.set(false);}
    }
    private JSONObject changeRecordingOrganization(JSONObject a)throws Exception{
        requireLifecycleIdle();String token=a.getString("libraryToken");
        if(!token.equals(libraries().token()))throw new java.io.IOException("资料库已切换，请重新选择录音。");
        if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("资料操作正在进行。");
        try{synchronized(RecordingSyncService.class){
            requireLifecycleIdle();if(!token.equals(libraries().token()))throw new java.io.IOException("资料库已切换，本次未修改。");
            java.util.Set<String> visible=new java.util.HashSet<>();LocalRecordingLifecycle life=lifecycle();
            for(RecordingLibrary.Session row:RecordingLibrary.inspect(recordings()).sessions){
                try{JSONObject state=life.get(row.key());if(state.getLong("trashedAt")==0&&!state.getBoolean("purging"))visible.add(row.key());}catch(Exception unreadable){/* Exclude unreadable identities; never change them. */}
            }
            JSONObject value=recordingOrganization().change(a.getLong("revision"),a.getJSONArray("keys"),a.getString("action"),a.optString("folder",""),a.optJSONArray("tags"),visible);
            return new JSONObject().put("revision",value.getLong("revision")).put("available",true).put("libraryToken",token);
        }}finally{LocalLibraryBackups.BUSY.set(false);}
    }
    private JSONObject changeRecordingBatch(JSONObject a)throws Exception{
        requireLifecycleIdle();String token=a.getString("libraryToken"),action=a.getString("action");JSONArray targets=a.getJSONArray("targets");
        if(!token.equals(libraries().token()))throw new java.io.IOException("资料库已切换，请重新选择录音。");
        if(!java.util.Arrays.asList("trash","protect","unprotect").contains(action)||targets.length()==0||targets.length()>500)throw new java.io.IOException("请选择1到500条录音进行保护或移入回收站。");
        if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("资料操作正在进行。");
        try{synchronized(RecordingSyncService.class){
            requireLifecycleIdle();if(!token.equals(libraries().token()))throw new java.io.IOException("资料库已切换，本批未修改。");
            LocalRecordingLifecycle life=lifecycle();java.util.Map<String,RecordingLibrary.Session> originals=new java.util.HashMap<>();for(RecordingLibrary.Session row:RecordingLibrary.inspect(recordings()).sessions)originals.put(row.key(),row);
            java.util.Set<String> seen=new java.util.HashSet<>();java.util.Map<String,String> titles=new java.util.HashMap<>();
            // Validate the entire selection before the first reversible state write.
            for(int i=0;i<targets.length();i++){
                JSONObject target=targets.getJSONObject(i);String key=target.getString("key");JSONObject current=life.get(key);
                if(!seen.add(key)||!originals.containsKey(key)||current.getLong("revision")!=target.getLong("revision")||current.getLong("trashedAt")!=0||current.getBoolean("purging"))throw new java.io.IOException("所选录音状态已变化，本批未修改，请刷新后重新选择。");
                if(action.equals("trash")&&current.getBoolean("protected"))throw new java.io.IOException("所选内容含受保护录音，本批未移入回收站；请先解除保护。");
                if(action.equals("trash"))titles.put(key,recordingTitle(key,originals.get(key)));
            }
            if(action.equals("trash")){stopPlayback();playbackEvent("stopped","");}
            JSONArray completed=new JSONArray(),pending=new JSONArray();String warning=null;
            for(int i=0;i<targets.length();i++){
                JSONObject target=targets.getJSONObject(i);String key=target.getString("key");
                if(warning!=null){pending.put(key);continue;}
                try{life.change(key,target.getLong("revision"),action,titles.getOrDefault(key,""));completed.put(key);}
                catch(Exception uncertain){pending.put(key);warning="部分管理状态尚未确认，请刷新录音库和回收站核对；原音没有永久清除。";}
            }
            return new JSONObject().put("completed",completed).put("pending",pending).put("warning",warning==null?JSONObject.NULL:warning).put("libraryToken",token);
        }}finally{LocalLibraryBackups.BUSY.set(false);}
    }
    private JSONObject syncStatus() throws Exception {
        RecordingSyncStatus s = RecordingSyncService.status(this);
        String saved=getSharedPreferences("companion_recording_sync",MODE_PRIVATE).getString("directory",null);
        if(!s.running&&saved!=null&&!saved.equals(recordings().getFileName().toString()))return new JSONObject().put("state","idle").put("detail","原接收任务保留在另一份资料中；切回该资料后可继续。").put("running",false).put("hasSavedTask",false);
        JSONObject result=new JSONObject().put("state", s.state).put("detail", s.detail).put("running", s.running).put("hasSavedTask", s.hasSavedTask);
        if(!s.running&&"complete".equals(s.state)){
            android.content.SharedPreferences prefs=getSharedPreferences("companion_recording_sync",MODE_PRIVATE);
            String encoded=prefs.getString("descriptor",null),address=prefs.getString("address",null);
            if(encoded!=null&&address!=null)try{
                RecorderWire.Descriptor completed=RecorderWire.Descriptor.decode(android.util.Base64.decode(encoded,android.util.Base64.NO_WRAP));
                result.put("completedDeviceRecording",new JSONObject().put("address",address).put("identity",recordingIdentity(completed)));
            }catch(java.io.IOException|IllegalArgumentException invalidSavedSelection){/* No completion claim for unverified metadata. */}
        }
        return result;
    }
    private void playbackEvent(String state, String message) {
        try {
            JSONObject event = new JSONObject().put("state", state).put("message", message);
            runOnUiThread(() -> { if (!isFinishing() && !isDestroyed()) web.evaluateJavascript("window.companionPlayback(" + event + ")", null); });
        } catch (Exception ignored) { }
    }
    private void progress(String message) {
        runOnUiThread(() -> { if (!isFinishing() && !isDestroyed()) web.evaluateJavascript("window.companionProgress(" + JSONObject.quote(message) + ")", null); });
    }
    private void stopPlayback() {
        savePlaybackProgress(true);
        if (player != null) { player.release(); player = null; }
        playingParts = new ArrayList<>();
        playingKey=null;playingBinding=null;playingMeetings=null;playingDurationMs=0;playingSpeed=1;playbackPaused=false;
    }
    private long playbackPosition(){return player==null||playingIndex>=playingParts.size()?0:Math.max(0,Math.min(playingDurationMs,playingParts.get(playingIndex).firstSample/16+player.getCurrentPosition()));}
    private void savePlaybackProgress(boolean force){
        if(player==null||playingKey==null||playingMeetings==null)return;
        long now=android.os.SystemClock.elapsedRealtime();if(!force&&(playbackPaused||now-lastPlaybackSave<5000))return;
        try{new PlaybackProgress(playingMeetings,MainActivity::syncLifecycleDirectory).save(playingKey,playingBinding,playbackPosition(),playingSpeed,false);lastPlaybackSave=now;playbackSaveWarning=null;}
        catch(Exception error){playbackSaveWarning="续听位置暂未保存；原录音仍保留，请稍后重试。";}
    }
    private void requirePlayback(JSONObject args)throws Exception{
        if(player==null||playingParts.isEmpty())throw new IllegalStateException("请先播放这条录音。");
        if(args.has("key")&&!args.getString("key").equals(playingKey)||args.has("libraryToken")&&!args.getString("libraryToken").equals(libraries().token()))throw new java.io.IOException("回听对象已变化，请重新打开这条录音。");
    }
    private void seekPlayer(MediaPlayer target,int offset)throws Exception{
        java.util.concurrent.CompletableFuture<Void> done=new java.util.concurrent.CompletableFuture<>();
        target.setOnSeekCompleteListener(ignored->done.complete(null));
        try{target.seekTo(offset,MediaPlayer.SEEK_CLOSEST);done.get(5,java.util.concurrent.TimeUnit.SECONDS);}
        finally{target.setOnSeekCompleteListener(null);}
    }
    private void seekPlayback(long requested)throws Exception{
        long target=Math.max(0,Math.min(Math.max(0,playingDurationMs-1),requested));int index=playingParts.size()-1;
        for(int i=0;i<playingParts.size();i++){NativeAudio.Part part=playingParts.get(i);if(target<(part.firstSample+part.samples)/16){index=i;break;}}
        NativeAudio.Part part=playingParts.get(index);int within=(int)Math.max(0,Math.min(Math.max(0,part.samples/16-1),target-part.firstSample/16));
        if(index==playingIndex&&player!=null)seekPlayer(player,within);
        else{if(player!=null)player.release();player=null;playingIndex=index;playPart(within,!playbackPaused);}
        savePlaybackProgress(true);
    }
    private void beginPlayback(RecordingLibrary.Session source,String key,NativeAudio.PartsResult parts,long position,double speed)throws Exception{
        playingParts=parts.parts;playingIndex=0;playingKey=key;playingBinding=RecordingBookmarkAccess.binding(source);playingMeetings=libraries().meetings();playingDurationMs=parts.samples/16;playingComplete=parts.captureComplete;playingSpeed=speed;playbackPaused=false;playbackSaveWarning=null;lastPlaybackSave=0;
        if(position>0)seekPlayback(position);else playPart();savePlaybackProgress(true);
    }
    private void playPart() throws Exception { playPart(0); }
    private void playPart(int positionMs) throws Exception { playPart(positionMs, true); }
    private void playPart(int positionMs, boolean startImmediately) throws Exception {
        if (playingIndex >= playingParts.size()) {
            try{if(playingKey!=null)new PlaybackProgress(playingMeetings,MainActivity::syncLifecycleDirectory).save(playingKey,playingBinding,playingComplete?0:Math.max(0,playingDurationMs-1),playingSpeed,playingComplete);}catch(Exception ignored){}
            stopPlayback();playbackEvent("stopped","回听结束");return;
        }
        MediaPlayer next = new MediaPlayer();
        try {
            next.setDataSource(playingParts.get(playingIndex).path.toString());
            // Initialized state: setting rate here must not auto-start a paused seek.
            next.setPlaybackParams(new android.media.PlaybackParams().allowDefaults().setSpeed((float)playingSpeed).setPitch(1));
            next.setOnCompletionListener(done -> {
                if(worker.isShutdown())return;
                try { worker.execute(() -> {
                    if (player != done) return;
                    done.release(); player = null; playingIndex++;
                    try { playPart(); } catch (Exception e) { stopPlayback(); playbackEvent("stopped", "回听失败：" + e.getMessage()); }
                }); } catch(java.util.concurrent.RejectedExecutionException ignored) { /* Activity is closing. */ }
            });
            next.prepare(); player = next;
            if (positionMs > 0) seekPlayer(next,positionMs);
            playbackPaused=!startImmediately;if (startImmediately) next.start();
        } catch (Exception error) { if(player==next)player=null;next.release();throw error; }
    }
    private void finishUpdatePicker(int resultCode,Intent data){
        final long id=updateRequestId;final boolean restored=updateRequestRestored;updateRequestId=0;updateRequestRestored=false;
        if(id==0)return;
        if(restored){android.widget.Toast.makeText(this,"升级包选择已中断，请重新选择；没有自动开始升级。",android.widget.Toast.LENGTH_LONG).show();return;}
        if(resultCode!=RESULT_OK||data==null||data.getData()==null){reply(id,JSONObject.NULL,null);return;}
        final android.net.Uri source=data.getData();worker.execute(()->{try{
            if(LocalLibraryBackups.BUSY.get())throw new java.io.IOException("资料操作正在进行，请稍后再选升级包。");
            try(java.io.InputStream in=getContentResolver().openInputStream(source)){if(in==null)throw new java.io.IOException("升级包无法读取。");reply(id,DeviceUpdateService.prepare(this,in),null);}
        }catch(Exception e){reply(id,null,e.getMessage()==null?"升级包读取失败；未发送任何升级内容。":e.getMessage());}});
    }
    private boolean confirmDeviceUpdate(String name,SystemUpdatePackage pack)throws Exception{
        return confirmDeviceAction("升级录音卡？","设备："+name+"\n程序版本："+pack.firmwareVersion+"\n资源版本："+pack.resourceVersion+"\n\n升级时请保持录音卡供电与手机蓝牙连接。设备会在安装前验证签名；原录音保留。","开始升级");
    }
    private boolean confirmDeviceMaintenance(String operation,String name)throws Exception{
        boolean clear="clearPairings".equals(operation);
        return confirmDeviceAction(clear?"清除录音卡配对？":"恢复录音卡设置？",
            (clear?"将清除 "+name+" 上全部已保存的蓝牙配对。之后请在手机系统蓝牙中忘记旧配对，再重新连接。":"将恢复 "+name+" 的设备设置。")+"\n\n设备原录音和手机里已保存的资料保留。",clear?"清除配对":"恢复设置");
    }
    private boolean confirmDeviceAction(String title,String message,String positive)throws Exception{
        java.util.concurrent.CompletableFuture<Boolean> answer=new java.util.concurrent.CompletableFuture<>();
        java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog> shown=new java.util.concurrent.atomic.AtomicReference<>();
        onUi(()->{if(answer.isDone())return null;android.app.AlertDialog dialog=new android.app.AlertDialog.Builder(this).setTitle(title).setMessage(message)
            .setNegativeButton("取消",(d,w)->answer.complete(false)).setPositiveButton(positive,(d,w)->answer.complete(true)).setOnCancelListener(d->answer.complete(false)).create();
            shown.set(dialog);dialog.setOnDismissListener(d->answer.complete(false));dialog.show();return null;});
        try{return answer.get(90,java.util.concurrent.TimeUnit.SECONDS);}
        catch(java.util.concurrent.TimeoutException expired){return false;}
        finally{answer.cancel(false);runOnUiThread(()->{android.app.AlertDialog dialog=shown.get();if(dialog!=null)dialog.dismiss();});}
    }
    private JSONObject maintainDevice(JSONObject args)throws Exception{
        if(RecordingSyncService.isRunning())throw new java.io.IOException("正在接收录音，请等待完成或停止接收后再维护设备。");
        final BluetoothDevice device=selectedDevice;String address=args.getString("address"),operation=args.getString("operation");
        if(device==null||!address.equals(device.getAddress()))throw new java.io.IOException("设备已变化，请重新选择录音卡。");
        DeviceMaintenance.Operation command;
        switch(operation){case "query":command=DeviceMaintenance.Operation.QUERY;break;case "openPairing":command=DeviceMaintenance.Operation.OPEN_PAIRING;break;case "restoreSettings":command=DeviceMaintenance.Operation.RESTORE_SETTINGS;break;case "clearPairings":command=DeviceMaintenance.Operation.CLEAR_PAIRINGS;break;default:throw new java.io.IOException("不支持的设备维护操作。");}
        String name=device.getName()==null?"录音卡":device.getName();
        if(("restoreSettings".equals(operation)||"clearPairings".equals(operation))&&!confirmDeviceMaintenance(operation,name))return new JSONObject().put("address",address).put("name",name).put("operation",operation).put("cancelled",true);
        if(RecordingSyncService.isRunning()||selectedDevice!=device)throw new java.io.IOException("设备或接收任务已变化，请重新操作。");
        DeviceMaintenance.Status result;
        try(RecordingClient client=CompanionAndroidBackend.connect(this,device)){result=client.maintainDevice(command);}
        if(command==DeviceMaintenance.Operation.RESTORE_SETTINGS&&(!result.settingsSaved||!result.defaultSettings))throw new java.io.IOException("设备已回复，但尚未确认设置已保存，请重新读取状态。");
        if(command==DeviceMaintenance.Operation.CLEAR_PAIRINGS&&(!result.bondCountValid||result.bonds!=0))throw new java.io.IOException("设备已回复，但尚未确认配对已清除，请重新连接后读取状态。");
        if(command==DeviceMaintenance.Operation.CLEAR_PAIRINGS){selectedDevice=null;segments=new ArrayList<>();}
        return new JSONObject().put("address",address).put("name",name).put("operation",operation).put("settingsSaved",result.settingsSaved).put("defaultSettings",result.defaultSettings).put("radioEnabled",result.radioEnabled).put("bondCountValid",result.bondCountValid).put("bonds",result.bonds);
    }
    private void closeSelectedDevice(){try{deviceConnection.close();}catch(java.io.IOException ignored){}}
    private <T>T withSelectedDevice(DeviceConnectionOwner.Operation<RecordingClient,T> operation)throws Exception {
        if(selectedDevice==null)throw new IllegalStateException("请先选择录音卡。");
        final BluetoothDevice requested=selectedDevice;
        return deviceConnection.use(requested.getAddress(),()->CompanionAndroidBackend.connect(this,requested),operation);
    }
    private static String recordingIdentity(RecorderWire.Descriptor d){
        return android.util.Base64.encodeToString(d.uid(),android.util.Base64.NO_WRAP)+":"+Long.toUnsignedString(d.epoch)+":"+Long.toUnsignedString(d.sessionId);
    }
    /** Publish the exact catalogue already read on the current GATT owner. */
    private JSONArray deviceRecordingRows(java.util.List<com.denzic.companion.mobile.DeviceRecordings.Session> sessions)throws org.json.JSONException {
        java.util.List<RecorderWire.Descriptor> selected=new ArrayList<>();JSONArray out=new JSONArray();
        for(int i=0;i<sessions.size();i++){
            com.denzic.companion.mobile.DeviceRecordings.Session row=sessions.get(i);RecorderWire.Descriptor d=row.representative;selected.add(d);
            out.put(new JSONObject().put("index",i).put("identity",recordingIdentity(d)).put("session",Long.toUnsignedString(d.sessionId))
                .put("segment",d.segmentIndex).put("bytes",row.bytes).put("segments",row.segments)
                .put("startedAtUnixSeconds",row.startedUnixSeconds==0?JSONObject.NULL:row.startedUnixSeconds)
                .put("durationMs",row.durationMillis).put("complete",row.complete));
        }
        segments=selected;return out;
    }
    /** A confirmed control ACK remains confirmed if a later list read fails.
     * Reuse this operation's connection; never replay START/STOP for a refresh. */
    private JSONObject recordingControlSnapshot(RecordingClient client,boolean receiving,String action,JSONObject result)throws Exception {
        if(!receiving&&"STOP".equals(action)&&"stopped".equals(result.optString("state"))){
            try{client.prepareStoppedReceive();}catch(java.io.IOException optionalPreferenceUnavailable){/* The ordinary catalogue still determines whether this link is usable. */}
        }
        try{
            result.put("inventory",new JSONObject(receiving ? RecordingSyncService.controlSessions(root().resolve("companion-control")) : client.controlSessions(root().resolve("companion-control"))));
        }catch(java.io.IOException refresh){result.put("inventoryRefreshFailed",true);}
        if(!receiving&&"STOP".equals(action)&&"stopped".equals(result.optString("state"))){
            try{result.put("recordings",deviceRecordingRows(client.listDeviceSessions()));}
            catch(java.io.IOException refresh){segments=new ArrayList<>();result.put("recordingsRefreshFailed",true);}
        }
        if(!receiving&&(result.optBoolean("inventoryRefreshFailed")||result.optBoolean("recordingsRefreshFailed")))closeSelectedDevice();
        return result;
    }
    private JSONArray deviceRows()throws Exception{
        JSONArray out=new JSONArray();for(int i=0;i<devices.size();i++){BluetoothDevice device=devices.get(i);out.put(new JSONObject().put("index",i).put("name",device.getName()==null?"未命名设备":device.getName()).put("address",device.getAddress()).put("bonded",device.getBondState()==BluetoothDevice.BOND_BONDED));}return out;
    }
    private JSONArray discoverDevices()throws Exception{
        if(!bluetoothGranted())throw new java.io.IOException("请先允许附近设备权限，再搜索录音卡。");
        if(RecordingSyncService.isRunning())throw new java.io.IOException("正在接收录音，请等待完成后再搜索设备。");
        java.util.Map<String,BluetoothDevice> found=java.util.Collections.synchronizedMap(new java.util.LinkedHashMap<>());
        for(BluetoothDevice d:CompanionAndroidBackend.pairedDevices(this))found.put(d.getAddress(),d);
        java.util.concurrent.CountDownLatch finished=new java.util.concurrent.CountDownLatch(1);java.util.concurrent.atomic.AtomicReference<String> failure=new java.util.concurrent.atomic.AtomicReference<>();
        try(AndroidDevices.Scan scan=CompanionAndroidBackend.discover(this,new AndroidDevices.Listener(){
            @Override public void onDevice(BluetoothDevice device,String name){found.put(device.getAddress(),device);}
            @Override public void onFinished(String error){failure.set(error);finished.countDown();}
        })){
            if(!finished.await(16,java.util.concurrent.TimeUnit.SECONDS))throw new java.io.IOException("搜索尚未结束，请检查附近设备权限后重试。");
        }
        if(failure.get()!=null)throw new java.io.IOException("搜索录音卡失败："+failure.get());
        synchronized(found){devices=new ArrayList<>(found.values());}selectedDevice=null;segments=new ArrayList<>();return deviceRows();
    }
    private PreparedExports preparedExports(){return new PreparedExports(getCacheDir().toPath());}
    private ExportContents.Source exportSource(String key)throws Exception{
        RecordingLibrary.Session recording=session(key);MeetingStore ms=store();MeetingStore.Snapshot meeting=null;MeetingStore.Minutes minutes=null;TranslationStore.Entry translation=null;JSONArray problems=new JSONArray();
        try{meeting=ms.load(key);}catch(java.io.IOException error){problems.put("原文或补充暂不可读取，原文件保留。");}
        try{minutes=ms.loadMinutes(key);}catch(java.io.IOException error){problems.put("纪要暂不可读取，原文件保留。");}
        try{translation=translations().load(key);}catch(java.io.IOException error){problems.put("译文暂不可读取，原文件保留。");}
        JSONArray materials=new JSONArray();try{materials=new AiMaterialStore(libraries().meetings()).list(key);}catch(Exception error){problems.put("部分AI材料暂不可读取，原文件保留；可先导出其它内容。");}
        return new ExportContents.Source(key,recordingTitle(key,recording),libraries().token(),meeting,minutes,translation,problems,materials,readNotesForExport(key,problems));
    }
    private JSONObject readNotesForExport(String key,JSONArray problems)throws Exception{try{return recordingNotes().read(key);}catch(Exception e){problems.put("备注与图片暂不可读取，原文件保留；可先导出其它内容。");return null;}}
    private boolean confirmDeviceRecordingDelete(com.denzic.companion.mobile.DeviceRecordings.Offer offer)throws java.io.IOException {
        java.util.concurrent.CompletableFuture<Boolean> answer=new java.util.concurrent.CompletableFuture<>();
        java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog> shown=new java.util.concurrent.atomic.AtomicReference<>();
        runOnUiThread(()->{
            if(answer.isDone())return;
            if(isFinishing()||isDestroyed()){answer.complete(false);return;}
            String date=offer.startedUnixSeconds==0?"日期未知":new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm",java.util.Locale.getDefault()).format(new java.util.Date(offer.startedUnixSeconds*1000));
            android.app.AlertDialog dialog=new android.app.AlertDialog.Builder(this).setTitle("删除设备录音")
                .setMessage(date+"，设备剩余音频约"+offer.durationMillis/1000+"秒，可释放"+offer.releasableBytes/1024+" KiB。\n未同步的设备原音将永久删除。本机已保存的副本保留。")
                .setNegativeButton("取消",(d,w)->answer.complete(false)).setPositiveButton("删除这场录音",(d,w)->answer.complete(true))
                .setOnCancelListener(d->answer.complete(false)).create();
            shown.set(dialog);dialog.setOnDismissListener(d->answer.complete(false));dialog.show();
        });
        try{return answer.get(45,java.util.concurrent.TimeUnit.SECONDS);}
        catch(Exception e){answer.cancel(false);throw new java.io.IOException("删除确认已取消或过期，请重新选择。",e);}
        finally{runOnUiThread(()->{android.app.AlertDialog dialog=shown.get();if(dialog!=null)dialog.dismiss();});}
    }
    private Object onUi(java.util.concurrent.Callable<Object> action)throws Exception{
        java.util.concurrent.CompletableFuture<Object> result=new java.util.concurrent.CompletableFuture<>();
        runOnUiThread(()->{try{if(result.isCancelled())return;if(isFinishing()||isDestroyed())throw new java.io.IOException("界面已关闭，请重新操作。");result.complete(action.call());}catch(Exception e){result.completeExceptionally(e);}});
        try{return result.get(30,java.util.concurrent.TimeUnit.SECONDS);}catch(java.util.concurrent.TimeoutException e){result.cancel(false);throw new java.io.IOException("界面暂时没有响应，请重新操作。",e);}catch(java.util.concurrent.ExecutionException e){throw new java.io.IOException(e.getCause().getMessage(),e.getCause());}
    }
    private PreparedExports.Entry prepareContent(JSONObject a)throws Exception{
        ExportContents.Source source=exportSource(a.getString("key"));JSONObject info=source.info();
        if(!info.getString("binding").equals(a.getString("binding"))||!source.token.equals(a.getString("libraryToken")))throw new java.io.IOException("资料内容已更新，请重新读取导出选项后再操作。");
        JSONArray selected=a.getJSONArray("sections");List<MeetingDocumentSections.Section> sections=source.select(selected);String format=a.getString("format"),extension,mime;
        switch(format){case "bundle":extension="zip";mime="application/zip";break;case "txt":extension="txt";mime="text/plain";break;case "markdown":extension="md";mime="text/markdown";break;case "pdf":extension="pdf";mime="application/pdf";break;case "word":extension="docx";mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document";break;case "srt":extension="srt";mime="application/x-subrip";break;case "pptx":extension="pptx";mime="application/vnd.openxmlformats-officedocument.presentationml.presentation";break;case "png":extension="png";mime="image/png";break;case "mindmap":extension="mm";mime="application/x-freemind";break;case "xlsx":extension="xlsx";mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";break;default:throw new java.io.IOException("不支持的文件格式。");}
        String plain=MeetingDocumentSections.plain(sections);JSONArray warnings=ExportContents.warnings(info,selected);String subtitle=null;
        if("srt".equals(format)){
            if(selected.length()!=1||!"transcript".equals(selected.getString(0)))throw new java.io.IOException("SRT只用于有分段时间的当前原文，请只选择会议转写。");
            RecordingLibrary.Session recording=session(source.key);NativeAudio.PartsResult parts=ManagedAudioParts.prepare(recording,root().resolve("companion-decoded-audio"));
            subtitle=ExportContents.srt(store().loadTranscriptTimingParts(source.key,recording,parts.directory));warnings.put("字幕使用识别分段的近似时间，不是逐字时间。");
        }
        final String srt=subtitle;String suffix=selected.length()==1?sections.get(0).title:"会议资料";if("srt".equals(format))suffix+="-分段时间";
        JSONObject meta=new JSONObject().put("key",source.key).put("title",source.title).put("libraryToken",source.token).put("binding",info.getString("binding")).put("warnings",warnings).put("sections",selected);
        return preparedExports().create(meta,PreparedExports.filename(source.title,suffix,extension),mime,plain,out->{
            if("bundle".equals(format))recordingNotes().bundle(source.key,!selected.toString().contains("\"notes\"")||source.notes==null?new JSONObject().put("entries",new JSONArray()):source.notes,source.title,MeetingDocumentSections.markdown(sections),out);
            else if("pdf".equals(format))MeetingPdf.writeSelected(source.title,sections,out,android.graphics.Typeface.createFromAsset(getAssets(),"companion-documents/CompanionPDFSans-Regular.ttf"));
            else if("word".equals(format))out.write(MeetingDocumentSections.word(source.title,MaterialLayout.wordSections(sections)));
            else if("pptx".equals(format))PresentationDocuments.write(source.title,sections,out);
            else if("png".equals(format))MindmapImage.write(source.title,sections,out);
            else if("mindmap".equals(format))out.write(MaterialLayout.mindmap(source.title,sections).getBytes(java.nio.charset.StandardCharsets.UTF_8));
            else if("xlsx".equals(format))StructuredWorkbook.write(source.title,sections,out);
            else {String content="srt".equals(format)?srt:"markdown".equals(format)?"# "+source.title+"\n\n"+MeetingDocumentSections.markdown(sections):source.title+"\n\n"+plain;out.write(content.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
            ExportContents.Source current=exportSource(source.key);
            if(!source.token.equals(current.token)||!info.getString("binding").equals(current.info().getString("binding")))throw new java.io.IOException("资料在准备文件期间发生变化，请重新读取后再操作。");
        });
    }
    private AiServiceVault aiServices;
    private final MeetingAiAccess meetingAi=new MeetingAiAccess();
    private AiServiceVault aiServices(){if(aiServices==null)aiServices=new AiServiceVault(this);return aiServices;}
    private JSONObject aiDocument(String key) throws Exception {
        if(key.startsWith("document:")){int split=key.lastIndexOf(':');if(split<10)throw new java.io.IOException("材料来源标识无效。");String owner=key.substring(9,split);session(owner);return documentContexts().aiDocument(owner,key.substring(split+1));}
        RecordingLibrary.Session recording=session(key);MeetingStore.Snapshot meeting=store().load(key);
        if(meeting==null||meeting.transcript.trim().isEmpty())throw new java.io.IOException("请先完成这场会议的转写。");
        return new JSONObject().put("id",key).put("title",recordingTitle(key,recording)).put("text",meeting.transcript).put("revision",meeting.revision)
            .put("binding",AiMaterialStore.hash(key+":"+meeting.revision+":"+meeting.transcript));
    }
    private void requireAiSources(JSONArray docs,String token) throws Exception {
        if(!token.equals(libraries().token()))throw new java.io.IOException("资料库已切换，请重新打开会议。");
        for(int i=0;i<docs.length();i++){JSONObject d=docs.getJSONObject(i);if(!d.getString("binding").equals(aiDocument(d.getString("id")).getString("binding")))throw new java.io.IOException("会议文字已变化，请重新提问，原内容仍保留。");}
    }
    private Object execute(String method, JSONObject a) throws Exception {
        if(DeviceUpdateService.isRunning()&&java.util.Arrays.asList("devices","discoverDevices","pairDevice","connectDevice","catalog","deviceMaintenance","deleteDeviceRecording","sync","resume","resumeConfirmation","controlInventory","control","libraryActivate").contains(method))throw new java.io.IOException("录音卡正在升级，请等待完成后再操作设备。");
        if(LocalLibraryBackups.BUSY.get()&&!"status".equals(method)&&!"audioImportStatus".equals(method)&&!"incomingFiles".equals(method)&&!"removeIncomingFile".equals(method))throw new IllegalStateException(AudioImportService.isRunning()?"正在完成导入保存，请稍后重试。":"正在备份或恢复资料，请等待完成。");
        if(("minutes".equals(method)||"translate".equals(method))&&a.optString("apiKey","").isEmpty()){
            JSONObject credentials=aiServices().credentials();a.put("apiKey",credentials.getString("apiKey")).put("endpoint",credentials.getString("endpoint")).put("model",credentials.getString("model"));
        }
        switch (method) {
            case "incomingFiles":return incomingDescription();
            case "importIncomingFile":return importIncoming(a);
            case "removeIncomingFile":{
                String id=a.getString("id");JSONObject job=AudioImportService.status(this);
                if(AudioImportService.isRunning()&&id.equals(job.optString("incomingId")))throw new java.io.IOException("此文件正在导入，请先取消并等待收尾。");
                incomingFiles().remove(id);return incomingDescription();
            }

            case "documentContexts":{String key=a.getString("key");session(key);return documentDescription(key);}
            case "documentContextChunk":{noteSession(a);return documentContexts().chunk(a.getString("key"),a.getLong("revision"),a.getString("id"),a.getInt("offset"));}
            case "documentContextRead":{noteSession(a);return documentContexts().extraction(a.getString("key"),a.getLong("revision"),a.getString("id"));}
            case "documentContextCommit":{noteSession(a);String key=a.getString("key");documentContexts().saveExtraction(key,a.getLong("revision"),a.getString("id"),a.getJSONObject("extraction"));return documentDescription(key);}
            case "documentContextRemove":{noteSession(a);String key=a.getString("key");documentContexts().remove(key,a.getLong("revision"),a.getString("id"));return documentDescription(key);}
            case "documentContextOriginal":{noteSession(a);String key=a.getString("key"),id=a.getString("id");long revision=a.getLong("revision");JSONObject list=documentContexts().read(key),entry=null;JSONArray documents=list.getJSONArray("rows");for(int i=0;i<documents.length();i++)if(id.equals(documents.getJSONObject(i).getString("id")))entry=documents.getJSONObject(i);if(entry==null)throw new java.io.IOException("材料已移除。");Path file=documentContexts().original(key,revision,id);String ext=entry.getString("format"),mime="pdf".equals(ext)?"application/pdf":"docx".equals(ext)?"application/vnd.openxmlformats-officedocument.wordprocessingml.document":"xlsx".equals(ext)?"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":"pptx".equals(ext)?"application/vnd.openxmlformats-officedocument.presentationml.presentation":"text/plain";
                return preparedExports().create(new JSONObject().put("key",key).put("libraryToken",libraries().token()).put("title",entry.getString("name")),PreparedExports.filename(entry.getString("name"),"原件",ext),mime,null,out->java.nio.file.Files.copy(file,out)).dto();}
            case "recordingNotes":{String key=a.getString("key");session(key);return noteDescription(key);}
            case "saveRecordingNote":{RecordingLibrary.Session selected=noteSession(a);String key=a.getString("key");recordingNotes().saveContext(key,a.getLong("revision"),a.optString("id",""),a.optString("text",""),noteTime(a),completeAudioDurationMs(selected),manualNoteKind(a),manualNoteReferences(a),reference->verifyManualEvidence(key,reference));return noteDescription(key);}
            case "recordingNoteEvidenceStatus":{
                noteSession(a);String key=a.getString("key");JSONObject value=recordingNotes().read(key);if(value.getLong("revision")!=a.getLong("revision"))throw new java.io.IOException("备注已更新，请重新读取后核对引用；当前输入保留。");
                JSONArray entries=value.getJSONArray("entries");JSONObject reference=null;
                for(int i=0;i<entries.length();i++){JSONObject entry=entries.getJSONObject(i);if(a.getString("noteId").equals(entry.getString("id"))){JSONArray refs=ManualNoteContext.references(entry);for(int j=0;j<refs.length();j++)if(a.getString("referenceId").equals(refs.getJSONObject(j).getString("id")))reference=refs.getJSONObject(j);}}
                if(reference==null)throw new java.io.IOException("这条引用已不存在，请重新读取备注；已有文字保留。");
                verifyManualEvidence(key,reference);
                return new JSONObject().put("key",key).put("libraryToken",libraries().token()).put("revision",value.getLong("revision")).put("noteId",a.getString("noteId")).put("referenceId",a.getString("referenceId")).put("ready",true);
            }
            case "removeRecordingNote":{noteSession(a);String key=a.getString("key");recordingNotes().remove(key,a.getLong("revision"),a.getString("id"));return noteDescription(key);}
            case "playRecordingNote":{RecordingLibrary.Session selected=noteSession(a);String key=a.getString("key");JSONObject value=recordingNotes().read(key);if(value.getLong("revision")!=a.getLong("revision"))throw new java.io.IOException("备注已更新，请重新读取后回听。");JSONArray entries=value.getJSONArray("entries");Long target=null;
                for(int i=0;i<entries.length();i++){JSONObject e=entries.getJSONObject(i);if(a.getString("id").equals(e.getString("id"))&&!e.isNull("atMs"))target=e.getLong("atMs");}
                if(target==null)throw new java.io.IOException("这条备注没有已保存的时间点。");NativeAudio.PartsResult parts=ManagedAudioParts.prepare(selected,root().resolve("companion-decoded-audio"));if(target<0||target>=parts.samples/16)throw new java.io.IOException("备注位置尚无可用音频，请完成接收后重试。");
                stopPlayback();JSONObject resume=savedPlaybackProgress(selected,key,parts.samples/16);try{beginPlayback(selected,key,parts,target,resume.getDouble("speed"));}catch(Exception e){stopPlayback();throw e;}return new JSONObject().put("durationMs",parts.samples/16).put("positionMs",target).put("speed",playingSpeed);
            }
            case "audioImportStatus":return AudioImportService.status(this);
            case "audioDerivationSources":{
                requireLibraryIdle();if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("资料操作正在进行，请稍后编辑。");
                try{JSONArray requested=a.getJSONArray("keys");if(requested.length()<1||requested.length()>128)throw new java.io.IOException("请选择有效的本机录音。");List<String> keys=new ArrayList<>();for(int i=0;i<requested.length();i++)keys.add(requested.getString(i));String token=a.getString("libraryToken");AudioDerivationAccess access=AudioImportService.derivationAccess(this,libraries());return access.describe(token,access.resolve(token,keys,(done,total)->{}));}finally{LocalLibraryBackups.BUSY.set(false);}
            }
            case "startAudioDerivation":AudioImportService.startDerivation(this,a);return new JSONObject().put("started",true);
            case "retryAudioDerivation":AudioImportService.retryDerivation(this,a.getString("id"));return new JSONObject().put("started",true);
            case "audioDerivationProvenance":{
                if(!a.getString("libraryToken").equals(libraries().token()))throw new java.io.IOException("资料库已切换，请重新打开录音。");RecordingLibrary.Session source=session(a.getString("key"));AudioDerivationPlan plan=source.imported==null?null:DerivedAudioPublication.read(source.imported);return new JSONObject().put("available",plan!=null).put("provenance",plan==null?JSONObject.NULL:plan.provenance());
            }
            case "audioDerivationSourceTarget":case "playDerivedSource":{
                String token=a.getString("libraryToken");if(!token.equals(libraries().token()))throw new java.io.IOException("资料库已切换，请重新打开录音。");RecordingLibrary.Session owner=session(a.getString("key"));AudioDerivationPlan plan=owner.imported==null?null:DerivedAudioPublication.read(owner.imported);
                Object rawIndex=a.get("sliceIndex");if(plan==null||!(rawIndex instanceof Number))throw new java.io.IOException("找不到这段原音的对应资料。");double exactIndex=((Number)rawIndex).doubleValue();int index=((Number)rawIndex).intValue();if(exactIndex!=index||index<0||index>=plan.slices.size())throw new java.io.IOException("请选择有效的原音片段。");AudioDerivationPlan.Slice slice=plan.slices.get(index);
                AudioDerivationAccess access=AudioImportService.derivationAccess(this,libraries());AudioDerivationAccess.Resolved resolved=access.resolve(token,java.util.Collections.singletonList(slice.source.key),(done,total)->{}).get(0);if(!resolved.source.identity.equals(slice.source.identity))throw new java.io.IOException("原录音内容已变化，不能按旧位置回听。派生录音仍保留。");
                long position=slice.start/16;double speed=1;
                if("playDerivedSource".equals(method)){RecordingLibrary.Session original=session(slice.source.key);NativeAudio.PartsResult parts=ManagedAudioParts.prepare(original,root().resolve("companion-decoded-audio"));JSONObject resume=savedPlaybackProgress(original,slice.source.key,parts.samples/16);speed=resume.getDouble("speed");stopPlayback();try{beginPlayback(original,slice.source.key,parts,position,speed);}catch(Exception error){stopPlayback();throw error;}}
                return new JSONObject().put("key",slice.source.key).put("positionMs",position).put("durationMs",resolved.source.frames/16).put("complete",true).put("speed",speed);
            }
            case "appPreferences":return appPreferences();
            case "saveAppPreferences":{
                if(a.length()==0)throw new IllegalArgumentException("没有需要保存的设置。");
                java.util.Iterator<String> keys=a.keys();while(keys.hasNext()){String key=keys.next();if(!key.equals("defaultPlaybackSpeed")&&!key.equals("resumePlayback"))throw new IllegalArgumentException("不支持的设置项。");}
                android.content.SharedPreferences.Editor edit=userPreferences().edit();
                if(a.has("defaultPlaybackSpeed")){double speed=a.getDouble("defaultPlaybackSpeed");if(!PlaybackProgress.validSpeed(speed))throw new IllegalArgumentException("请选择支持的回听速度。");edit.putFloat("defaultPlaybackSpeed",(float)speed);}
                if(a.has("resumePlayback")){if(!(a.get("resumePlayback") instanceof Boolean))throw new IllegalArgumentException("续听设置无效。");edit.putBoolean("resumePlayback",a.getBoolean("resumePlayback"));}
                if(!edit.commit())throw new java.io.IOException("设置尚未保存，请重试；原录音仍保留。");return appPreferences();
            }
            case "deviceUpdateStatus":return DeviceUpdateService.status(this);
            case "cancelDeviceUpdate":return DeviceUpdateService.cancel(this);
            case "startDeviceUpdate":case "verifyDeviceUpdate":{
                if(documentRequestId!=0||libraryRequestId!=0||updateRequestId!=0)throw new java.io.IOException("请先完成当前文件选择。");
                BluetoothDevice requested=selectedDevice;if(requested==null||!requested.getAddress().equals(a.getString("address")))throw new java.io.IOException("请先连接对应的录音卡。");
                boolean verify=method.equals("verifyDeviceUpdate");String name=requested.getName()==null?"录音卡":requested.getName(),id=a.optString("id","");
                if(!verify&&!confirmDeviceUpdate(name,DeviceUpdateService.load(this,id)))return DeviceUpdateService.status(this).put("cancelled",true);
                closeSelectedDevice();
                if(selectedDevice!=requested||LocalLibraryBackups.BUSY.get())throw new java.io.IOException("设备或资料状态已变化，请重新操作。");
                return onUi(()->DeviceUpdateService.start(this,requested,name,id,verify));
            }
            case "libraryStatus":return libraries().status();
            case "recordingTrash":return lifecycle().trash().put("libraryToken",libraries().token());
            case "recordingLifecycle":return changeLocalRecording(a);
            case "recordingOrganization":return changeRecordingOrganization(a);
            case "recordingLifecycleBatch":return changeRecordingBatch(a);
            case "exportInfo":return exportSource(a.getString("key")).info();
            case "prepareExport":return prepareContent(a).dto();
            case "copyExport":{
                PreparedExports exports=preparedExports();PreparedExports.Entry entry=exports.load(a.getString("id"),true);exports.requireLibrary(entry,libraries().token());lifecycle().requireVisible(entry.meta.getString("key"));String text=exports.copyText(entry);
                return onUi(()->{android.content.ClipboardManager clipboard=(android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE);if(clipboard==null)throw new java.io.IOException("暂时无法复制，请保存文件。");clipboard.setPrimaryClip(android.content.ClipData.newPlainText("Companion 会议资料",text));return true;});
            }
            case "shareExport":{
                PreparedExports exports=preparedExports();PreparedExports.Entry entry=exports.load(a.getString("id"),true);exports.requireLibrary(entry,libraries().token());lifecycle().requireVisible(entry.meta.getString("key"));
                return onUi(()->{Intent send=ExportFileProvider.shareIntent(this,entry);Intent chooser=Intent.createChooser(send,"分享会议资料");chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION).setClipData(send.getClipData());startActivity(chooser);return new JSONObject().put("opened",true);});
            }
            case "prepareAudioShare":{
                ExportContents.Source source=exportSource(a.getString("key"));JSONObject info=source.info();if(!source.token.equals(a.getString("libraryToken"))||!info.getString("binding").equals(a.getString("binding")))throw new java.io.IOException("资料已变化，请重新读取。");
                NativeAudio.PartsResult parts=ManagedAudioParts.prepare(session(source.key),root().resolve("companion-decoded-audio"));if(parts.parts.isEmpty())throw new java.io.IOException("没有可分享的音频。");
                List<Path> audio=new ArrayList<>();for(NativeAudio.Part part:parts.parts)audio.add(part.path);boolean multiple=audio.size()>1;JSONArray warnings=new JSONArray();if(!parts.captureComplete)warnings.put("这是当前已接收的部分音频，原录音仍保留。");
                return preparedExports().create(new JSONObject().put("key",source.key).put("title",source.title).put("libraryToken",source.token).put("warnings",warnings),DocumentNames.audio(source.title,multiple),multiple?"application/zip":"audio/wav",null,out->AudioExport.write(audio,out,multiple)).dto();
            }
            case "aiServiceStatus":return aiServices().status();
            case "aiServiceSave":return aiServices().save(a);
            case "aiServiceClear":return aiServices().clear();
            case "aiContext":{
                JSONArray available=new JSONArray();int problems=0;StringBuilder identity=new StringBuilder();
                for(RecordingLibrary.Session row:RecordingLibrary.inspect(recordings()).sessions){String key=row.key();
                    try{lifecycle().requireVisible(key);MeetingStore.Snapshot value=store().load(key);if(value==null||value.transcript.trim().isEmpty())continue;JSONObject doc=aiDocument(key);identity.append(doc.getString("binding"));doc.remove("text");available.put(doc);}catch(Exception unavailable){problems++;}}
                if(a.has("ownerKey")){String owner=a.getString("ownerKey");session(owner);try{JSONObject context=documentContexts().read(owner);JSONArray rows=context.getJSONArray("rows");for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);if(!row.has("extraction"))continue;try{JSONObject doc=documentContexts().aiDocument(owner,row.getString("id"));identity.append(doc.getString("binding"));doc.remove("text");available.put(doc);}catch(Exception unavailable){problems++;}}}catch(Exception unavailable){problems++;}}
                return new JSONObject().put("libraryToken",libraries().token()).put("available",available).put("sourceVersion",AiMaterialStore.hash(identity.toString())).put("problems",problems);
            }
            case "askMeeting":{
                String token=a.getString("libraryToken"),owner=a.getString("ownerKey");session(owner);
                if(!token.equals(libraries().token()))throw new java.io.IOException("资料已切换，请重新选择会议。");
                JSONArray selection=a.getJSONArray("sources"),docs=new JSONArray();java.util.Set<String> seen=new java.util.HashSet<>();
                if(selection.length()<1||selection.length()>12)throw new java.io.IOException("请选择1到12项会议转写或补充材料。");
                for(int i=0;i<selection.length();i++){JSONObject selected=selection.getJSONObject(i),doc=aiDocument(selected.getString("id"));if(!seen.add(doc.getString("id"))||!doc.getString("binding").equals(selected.getString("binding")))throw new java.io.IOException("会议范围或文字已变化，请重新读取。");docs.put(doc);}
                JSONObject result=meetingAi.ask(a.getString("jobId"),token,owner,a.getString("question"),docs,aiServices().credentials(),a.optJSONObject("resume"),this::requireAiSources,a.optString("purpose","会议问答"));aiServices().verified();return result;
            }
            case "aiMaterials":{String key=a.getString("key");session(key);return new AiMaterialStore(libraries().meetings()).list(key);}
            case "saveAiMaterial":session(a.getString("ownerKey"));return meetingAi.save(a,new AiMaterialStore(libraries().meetings()),this::requireAiSources);
            case "copyAiText":{
                String value=a.getString("text");if(value.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>256*1024)throw new java.io.IOException("文字较长，请保存文件。");
                return onUi(()->{android.content.ClipboardManager clipboard=(android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE);if(clipboard==null)throw new java.io.IOException("剪贴板暂不可用。");clipboard.setPrimaryClip(android.content.ClipData.newPlainText("会议材料",value));return true;});
            }
            case "minutesTemplates":return new MinutesTemplateLibrary(libraries().meetings()).load().put("libraryToken",libraries().token());
            case "minutesTemplateChange":{
                if(!a.getString("libraryToken").equals(libraries().token()))throw new java.io.IOException("资料已切换，请重新读取模板。");
                return new MinutesTemplateLibrary(libraries().meetings()).change(a.getString("etag"),a.getString("action"),a.optJSONObject("template"),a.optString("key","")).put("libraryToken",libraries().token());
            }
            case "libraryActivate":{
                requireLibraryIdle();if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("资料操作正在进行。");
                try{closeSelectedDevice();stopPlayback();JSONObject result=libraries().activate(a.getString("id"),a.getString("token"));selectedDevice=null;segments=new ArrayList<>();return result;}finally{LocalLibraryBackups.BUSY.set(false);}
            }
            case "devices": {
                closeSelectedDevice();
                if (!bluetoothGranted()) throw new IllegalStateException("请先允许附近设备权限，再重新读取。");
                devices = CompanionAndroidBackend.pairedDevices(this); segments = new ArrayList<>(); selectedDevice = null;
                return deviceRows();
            }
            case "discoverDevices":closeSelectedDevice();return discoverDevices();
            case "pairDevice":{
                if(RecordingSyncService.isRunning())throw new java.io.IOException("正在接收录音，请等待完成后再配对。");
                BluetoothDevice device=devices.get(a.getInt("index"));if(!device.getAddress().equals(a.getString("address")))throw new java.io.IOException("设备列表已变化，请重新搜索。");
                closeSelectedDevice();
                AndroidPairing.pair(this,device);return new JSONObject().put("paired",true).put("address",device.getAddress());
            }
            case "deviceMaintenance":closeSelectedDevice();return maintainDevice(a);
            case "connectDevice":{
                if(RecordingSyncService.isRunning())throw new java.io.IOException("正在接收录音，请等待完成后再连接其它设备。");
                BluetoothDevice requested=devices.get(a.getInt("index"));if(!requested.getAddress().equals(a.getString("address")))throw new java.io.IOException("设备列表已变化，请重新搜索。");
                JSONArray recordings;
                recordings=deviceConnection.use(requested.getAddress(),()->CompanionAndroidBackend.connect(this,requested),client->{
                    client.readDeviceStatus();return deviceRecordingRows(client.listDeviceSessions());
                });
                selectedDevice=requested;return new JSONObject().put("address",requested.getAddress()).put("connected",true).put("recordings",recordings);
            }
            case "catalog": {
                if (RecordingSyncService.isRunning()) throw new IllegalStateException("正在接收录音，请先等待接收结束。");
                if(a.has("index")){BluetoothDevice requested=devices.get(a.getInt("index"));if(a.has("address")&&!requested.getAddress().equals(a.getString("address")))throw new java.io.IOException("设备列表已变化，请重新选择。");selectedDevice=requested;}
                if(selectedDevice==null)throw new IllegalStateException("请先选择录音卡。");
                if(a.has("address")&&!a.getString("address").equals(selectedDevice.getAddress()))throw new java.io.IOException("设备已变化，请重新选择。");
                segments = new ArrayList<>();
                java.util.List<com.denzic.companion.mobile.DeviceRecordings.Session> sessions;
                sessions=withSelectedDevice(RecordingClient::listDeviceSessions);
                return deviceRecordingRows(sessions);
            }
            case "deleteDeviceRecording": {
                if(RecordingSyncService.isRunning())throw new IllegalStateException("请先等待录音接收结束。");
                if(selectedDevice==null)throw new IllegalStateException("请重新选择设备。");
                RecorderWire.Descriptor selected=segments.get(a.getInt("index"));
                boolean deleted;
                deleted=withSelectedDevice(client->client.deleteDeviceSession(selected,this::confirmDeviceRecordingDelete));
                return new JSONObject().put("deleted",deleted).put("message",deleted?"设备副本已删除，空间已回收。本机已保存的录音保留。":"已取消删除。");
            }
            case "sync": {
                if (selectedDevice == null) throw new IllegalStateException("请重新选择设备和录音。");
                File dir = recordings().toFile();
                if (!dir.isDirectory() && !dir.mkdirs()) throw new IllegalStateException("无法创建录音目录。");
                RecordingSyncService.start(this,selectedDevice,segments.get(a.getInt("index")),dir,deviceConnection.take(selectedDevice.getAddress()));
                return syncStatus();
            }
            case "resume": {
                String saved=getSharedPreferences("companion_recording_sync",MODE_PRIVATE).getString("directory",null);
                if(saved==null||!saved.equals(recordings().getFileName().toString()))throw new java.io.IOException("原接收任务属于另一份资料，请先切回原资料。");
                String savedAddress=getSharedPreferences("companion_recording_sync",MODE_PRIVATE).getString("address",null);
                if(savedAddress==null)closeSelectedDevice();
                RecordingSyncService.resume(this,savedAddress==null?null:deviceConnection.take(savedAddress));return syncStatus();
            }
            case "pendingConfirmation": {
                boolean invalid=false; RecorderWire.Descriptor pending=null;
                try { pending=RecordingLibrary.pendingConfirmation(recordings()); } catch (java.io.IOException unreadable) { invalid=true; }
                JSONArray deferred=new JSONArray();
                for(RecordingLibrary.DeferredConfirmation item:RecordingLibrary.deferredConfirmations(recordings()))
                    deferred.put(new JSONObject().put("token",item.token).put("session",Long.toUnsignedString(item.descriptor.sessionId)));
                return new JSONObject().put("pending",pending!=null).put("invalid",invalid).put("deferred",deferred)
                    .put("unreadableCount",RecordingLibrary.unreadableConfirmations(recordings()).size());
            }
            case "deferConfirmation": {
                if(RecordingSyncService.isRunning())throw new IllegalStateException("请等待接收停止后再暂缓确认。");
                RecorderWire.Descriptor pending=RecordingLibrary.pendingConfirmation(recordings());
                if(pending==null)throw new IllegalStateException("没有待确认的录音。");
                RecordingLibrary.deferPendingConfirmation(recordings(),pending);return JSONObject.NULL;
            }
            case "deferUnreadableConfirmation": {
                if(RecordingSyncService.isRunning())throw new IllegalStateException("请等待接收停止后再处理确认资料。");
                RecordingLibrary.deferUnreadablePendingConfirmation(recordings());return JSONObject.NULL;
            }
            case "restoreDeferredConfirmation": {
                if(RecordingSyncService.isRunning())throw new IllegalStateException("请等待接收停止后再恢复确认。");
                String token=a.getString("token"); RecordingLibrary.DeferredConfirmation found=null;
                for(RecordingLibrary.DeferredConfirmation item:RecordingLibrary.deferredConfirmations(recordings()))if(item.token.equals(token)){found=item;break;}
                if(found==null)throw new IllegalStateException("找不到这条暂缓的确认记录，请重新读取。");
                RecordingLibrary.restoreDeferredConfirmation(recordings(),found.token,found.descriptor);return JSONObject.NULL;
            }
            case "resumeConfirmation": {
                if (selectedDevice == null) throw new IllegalStateException("请先选择原录音卡。");
                RecordingSyncService.resumePending(this,selectedDevice,recordings().toFile(),deviceConnection.take(selectedDevice.getAddress()));
                return syncStatus();
            }
            case "stopSync": RecordingSyncService.stop(this); return syncStatus();
            case "status": return syncStatus();
            case "licenses": {
                String[] files = {"www/document-engine/ThirdPartyNotices.txt", "ShadcnDashboardMIT.txt", "companion-android-native-notices.txt", "companion-asr-runtime-notices.txt", "companion-local-model-notices.txt", "companion-document-export-notices.txt", "companion-document-font-OFL.txt", "companion-asr-runtime/onnxruntime-LICENSE.txt", "companion-asr-runtime/onnxruntime-ThirdPartyNotices.txt", "companion-asr-runtime/sherpa-onnx-LICENSE.txt"};
                StringBuilder text = new StringBuilder();
                for (String file : files) {
                    text.append("\n\n--- ").append(file).append(" ---\n");
                    try (java.io.InputStream in = getAssets().open(file); java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
                        byte[] buffer = new byte[8192]; int count;
                        while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
                        text.append(out.toString("UTF-8"));
                    }
                }
                return text.toString();
            }
            case "controlInventory": {
                if (RecordingSyncService.isRunning()) return new JSONObject(RecordingSyncService.controlSessions(root().resolve("companion-control")));
                if (selectedDevice == null) throw new IllegalStateException("请先选择录音卡。");
                return withSelectedDevice(client->new JSONObject(client.controlSessions(root().resolve("companion-control"))));
            }
            case "control": {
                boolean receiving=RecordingSyncService.isRunning();
                if (!receiving && selectedDevice == null) throw new IllegalStateException("请先选择录音卡。");
                String action = a.getString("action");
                if (receiving && ("START".equals(action)||"ADOPT".equals(action)))
                    throw new IllegalStateException("接收期间不能开始或接管新的录音。");
                DeviceConnectionOwner.Operation<RecordingClient,JSONObject> operation=client->{
                    JSONObject inventory = new JSONObject(receiving ? RecordingSyncService.controlSessions(root().resolve("companion-control")) : client.controlSessions(root().resolve("companion-control")));
                    JSONArray saved = inventory.getJSONArray("sessions");
                    if (inventory.optInt("unreadableCount") > 0) throw new IllegalStateException("有录音控制记录无法读取，请保留原录音并先检查设备。");
                    if ("ADOPT".equals(action)) return recordingControlSnapshot(client,false,action,new JSONObject(client.adoptLocalControl(root().resolve("companion-control"))));
                    String host;
                    if ("START".equals(action) && !a.has("hostSession")) {
                        for (int i=0;i<saved.length();i++) if (!"stopped".equals(saved.getJSONObject(i).optString("state")))
                            throw new IllegalStateException("有尚未确认的录音，请先查询原录音状态。");
                        host = NativeRecordingControl.newSessionId();
                    } else {
                        host = a.getString("hostSession"); boolean found = false;
                        for (int i=0;i<saved.length();i++) {
                            JSONObject item=saved.getJSONObject(i);
                            if (host.equals(item.optString("hostSession"))) {
                                found=true;
                                if ("START".equals(action) && (item.optInt("pendingCommand", -1)!=1 || item.optInt("maxSeconds", -1)!=0))
                                    throw new IllegalStateException("这不是可重试的原开始请求。");
                                break;
                            }
                        }
                        if (!found) throw new IllegalStateException("找不到原录音控制记录，请重新读取。");
                    }
                    NativeRecordingControl.Action command=NativeRecordingControl.Action.valueOf(action);
                    JSONObject result=new JSONObject(receiving ? RecordingSyncService.control(root().resolve("companion-control"),host,command,0) : client.control(root().resolve("companion-control"),host,command,0));
                    return recordingControlSnapshot(client,receiving,action,result);
                };
                return receiving?operation.run(null):withSelectedDevice(operation);
            }
            case "library": {
                RecordingLibrary.Inventory inv = RecordingLibrary.inspect(recordings()); JSONArray rows = new JSONArray(); int titleProblems=0,searchProblems=0;
                JSONObject organization=null,organizationStatus=new JSONObject().put("available",true).put("libraryToken",libraries().token());
                try{organization=recordingOrganization().read();organizationStatus.put("revision",organization.getLong("revision"));}
                catch(Exception unreadable){organizationStatus.put("available",false).put("revision",0).put("error","分类资料暂不能读取，原文件保留；可以继续打开录音或先备份，分类操作暂停。");}
                String query=a.optString("query","").trim();
                MeetingLibrarySearch search=query.isEmpty()?null:new MeetingLibrarySearch(query,!"title".equals(a.optString("scope","all")));
                MeetingLibrarySearch.Reader reader=(key,source)->{
                    if("notes".equals(source)){
                        try{return new MeetingLibrarySearch.SavedText(RecordingNotes.searchableText(recordingNotes().read(key)),false);}
                        catch(java.io.IOException error){throw error;}
                        catch(Exception error){throw new java.io.IOException("人工备注暂不能读取，原文件保留。",error);}
                    }
                    if("transcript".equals(source)){
                        MeetingStore.Snapshot saved=store().load(key);
                        return saved==null?null:new MeetingLibrarySearch.SavedText(saved.transcript,false);
                    }
                    MeetingStore.Minutes saved=store().loadMinutes(key);if(saved==null)return null;
                    JSONObject content=MinutesHistoryAccess.content(saved.json);
                    Object markdown=content==null?null:content.opt("markdown");
                    if(!(markdown instanceof String))throw new java.io.IOException("保存的纪要无法读取");
                    return new MeetingLibrarySearch.SavedText((String)markdown,saved.sourceChanged||saved.sourceMissing);
                };
                for (RecordingLibrary.Session s : inv.sessions) {
                    RecorderWire.Descriptor d = s.imported==null?s.segments.get(0).descriptor:null;
                    String key=s.key();
                    JSONObject life;try{life=lifecycle().get(key);}catch(Exception unreadable){titleProblems++;continue;}
                    if(life.getLong("trashedAt")!=0)continue;
                    String title;try { title=recordingTitle(key,s); } catch (java.io.IOException error) {title=d==null?"导入录音 · 名称暂不可用":defaultRecordingTitle(d.sessionId,true);titleProblems++;}
                    MeetingLibrarySearch.Result found=search==null?null:search.find(key,title,reader);
                    if(found!=null){searchProblems+=found.unreadable;if(found.match==null)continue;}
                    boolean derived=false;if(s.imported!=null)try{derived=DerivedAudioPublication.read(s.imported)!=null;}catch(java.io.IOException unreadable){titleProblems++;}
                    JSONObject row=new JSONObject().put("key", key).put("title",title).put("session",d==null?(derived?"编辑录音":"文件导入"):Long.toUnsignedString(d.sessionId)).put("source",d==null?(derived?"derivedAudio":"importedAudio"):"recorder")
                            .put("state", s.state.name()).put("segments",s.imported==null?s.segments.size():s.imported.partCount()).put("lifecycle",life).put("libraryToken",libraries().token())
                            .put("recordedAtUnixSeconds",s.startedUnixSeconds>0?Long.valueOf(s.startedUnixSeconds):JSONObject.NULL);
                    long duration=completeAudioDurationMs(s);if(duration>0)row.put("durationMs",duration);
                    row.put("organization",organization==null?new JSONObject().put("folder","").put("tags",new JSONArray()):RecordingOrganization.item(organization,key));
                    if(found!=null)row.put("matchSource",found.match.source).put("matchSnippet",found.match.snippet)
                        .put("matchStart",found.match.start).put("matchEnd",found.match.end).put("matchStale",found.match.stale);
                    rows.put(row);
                }
                return new JSONObject().put("rows", rows).put("problems", inv.problems.size()+titleProblems).put("searchProblems",searchProblems)
                    .put("organization",organizationStatus)
                    .put("searchQuery",query).put("searchScope","title".equals(a.optString("scope","all"))?"title":"all");
            }
            case "detail": {
                String key = a.getString("key");RecordingLibrary.Session selected=session(key);
                JSONObject resume=savedPlaybackProgress(selected,key,completeAudioDurationMs(selected));
                return MeetingDetailAccess.read(store(),key,translations()).put("lifecycle",lifecycle().get(key)).put("libraryToken",libraries().token()).put("playback",resume);
            }
            case "minutesHistory": {
                String key=a.getString("key");session(key);
                return MinutesHistoryAccess.list(store(),key);
            }
            case "restoreMinutes": {
                String key=a.getString("key");session(key);
                return MinutesHistoryAccess.restore(store(),key,a.getLong("meetingRevision"),a.getLong("minutesRevision"),a.getString("historyId"));
            }
            case "rename": {
                String key=a.getString("key"); RecordingLibrary.Session original=session(key);
                String title=a.getString("title").trim();
                if (title.isEmpty() || title.length()>100) throw new IllegalArgumentException("请输入不超过100个字符的名称。");
                recordingTitle(key,original);
                java.nio.file.Files.createDirectories(libraries().meetings());
                android.util.AtomicFile file=titleFile(key);java.io.FileOutputStream out=null;
                try {out=file.startWrite();out.write(title.getBytes(java.nio.charset.StandardCharsets.UTF_8));file.finishWrite(out);}
                catch(java.io.IOException error){if(out!=null)file.failWrite(out);throw new java.io.IOException("名称未能保存，原名称已保留。",error);}
                return new JSONObject().put("title",recordingTitle(key,original));
            }
            case "transcribe": {
                String key = a.getString("key"); RecordingLibrary.Session s = session(key);
                MeetingStore ms = store(); MeetingStore.Snapshot prior = ms.load(key);
                if (prior != null && !prior.transcript.isEmpty()) throw new IllegalStateException("已有转写文字；为保护原文，此入口不会覆盖它。");
                if (cancelTranscription.get()) throw new java.util.concurrent.CancellationException("已停止转写；录音保留。");
                NativeAudio.PartsResult parts = ManagedAudioParts.prepare(s, root().resolve("companion-decoded-audio"));
                if (cancelTranscription.get()) throw new java.util.concurrent.CancellationException("已停止转写；录音保留。");
                Path models = root().resolve("companion-models");
                final long[] lastProgress = {-1};
                LocalModelPreparation.prepare(models, (downloaded,total) -> {
                    if (cancelTranscription.get()) throw new java.util.concurrent.CancellationException("已停止模型准备；录音保留，可重试。");
                    long percent = total > 0 ? downloaded * 100 / total : -1;
                    if (percent != lastProgress[0]) { lastProgress[0] = percent; progress("正在准备模型 " + (percent >= 0 ? percent + "%" : "")); }
                });
                if (cancelTranscription.get()) throw new java.util.concurrent.CancellationException("已停止转写；录音保留。");
                lastProgress[0] = -1;
                JSONObject detail = new JSONObject(NativeLocalTranscription.transcribeDetailedPartsWithProgress(s, parts.directory, models, root().resolve("companion-asr-cache").resolve(key), (done,total) -> {
                    long percent = total > 0 ? done * 100 / total : -1;
                    if (percent != lastProgress[0]) { lastProgress[0] = percent; progress("正在转写 " + (percent >= 0 ? percent + "%" : "")); }
                    return !cancelTranscription.get();
                }));
                String text = detail.getString("text");
                ms.saveTranscription(key, prior == null ? null : prior.transcript, text);
                List<MeetingStore.TranscriptWindow> windows = new ArrayList<>(); JSONArray source = detail.getJSONArray("segments");
                for (int i=0;i<source.length();i++) { JSONObject w=source.getJSONObject(i); windows.add(new MeetingStore.TranscriptWindow(w.getString("text"),w.getLong("startMs"),w.getLong("endMs"))); }
                List<MeetingStore.UnrecognizedRange> gaps = new ArrayList<>(); JSONArray missing=detail.getJSONArray("unrecognized");
                for (int i=0;i<missing.length();i++) { JSONObject g=missing.getJSONObject(i); gaps.add(new MeetingStore.UnrecognizedRange(g.getLong("startMs"),g.getLong("endMs"))); }
                ms.saveTranscriptTimingParts(key,text,s,parts.directory,detail.getLong("durationMs"),windows,gaps);
                return new JSONObject().put("text",text).put("gaps",gaps.size());
            }
            case "transcribeCloud": {
                String key=a.getString("key"); RecordingLibrary.Session s=session(key);
                MeetingStore ms=store(); MeetingStore.Snapshot prior=ms.load(key);
                if (prior!=null && !prior.transcript.isEmpty()) throw new IllegalStateException("已有转写文字；为保护原文，此入口不会覆盖它。");
                String appId=a.getString("appId").trim(),token=a.getString("token").trim(),resource=a.getString("resourceId").trim();
                if(appId.isEmpty()||token.isEmpty()||resource.isEmpty()) throw new IllegalArgumentException("请填写火山引擎转写服务的 App ID、令牌和资源 ID。");
                if(cancelTranscription.get()) throw new java.util.concurrent.CancellationException("已停止转写，未发送音频。");
                NativeAudio.PartsResult parts=ManagedAudioParts.prepare(s,root().resolve("companion-decoded-audio"));
                if(cancelTranscription.get()) throw new java.util.concurrent.CancellationException("已停止转写，未发送音频。");
                final long[] lastProgress={-1};
                String text=NativeTranscription.transcribePartsWithProgress(s,parts.directory,appId,token,resource,root().resolve("companion-cloud-asr-cache").resolve(key),(done,total)->{
                    long percent=total>0?done*100/total:-1;
                    if(percent!=lastProgress[0]){lastProgress[0]=percent;progress("正在云端转写 "+(percent>=0?percent+"%":""));}
                    return !cancelTranscription.get();
                });
                ms.saveTranscription(key,prior==null?null:prior.transcript,text);
                return new JSONObject().put("text",text);
            }
            case "play": {
                stopPlayback();
                String key=a.getString("key");RecordingLibrary.Session s = session(key);
                NativeAudio.PartsResult parts = ManagedAudioParts.prepare(s, root().resolve("companion-decoded-audio"));
                if (parts.parts.isEmpty()) throw new IllegalStateException("没有可回听的音频。");
                JSONObject resume=savedPlaybackProgress(s,key,parts.samples/16);
                long position=a.optBoolean("restart",false)?0:resume.getLong("positionMs");
                try{beginPlayback(s,key,parts,position,resume.getDouble("speed"));}catch(Exception error){stopPlayback();throw error;}
                return new JSONObject().put("complete", parts.captureComplete).put("durationMs", parts.samples / 16).put("positionMs",playbackPosition()).put("speed",playingSpeed);
            }
            case "bookmarks":{
                String key=a.getString("key");RecordingLibrary.Session selected=session(key);
                NativeAudio.VerifiedPrefix prefix;
                try{prefix=NativeAudio.inspectPrefix(selected);}catch(java.io.IOException error){throw new java.io.IOException("当前已保存分段暂不能读取重点，请完成接收后重试；原录音已保留。",error);}
                return RecordingBookmarkAccess.describe(key,libraries().token(),RecordingBookmarkAccess.binding(selected),prefix);
            }
            case "playBookmark":{
                if(!a.getString("libraryToken").equals(libraries().token()))throw new java.io.IOException("资料已切换，请重新打开这条录音。");
                RecordingLibrary.Session selected=session(a.getString("key"));
                if(!a.getString("binding").equals(RecordingBookmarkAccess.binding(selected)))throw new java.io.IOException("已保存的录音分段已更新，请重新读取重点后回听。");
                NativeAudio.PartsResult parts=ManagedAudioParts.prepare(selected,root().resolve("companion-decoded-audio"));
                RecordingBookmarkAccess.Playback target=RecordingBookmarkAccess.playback(parts,a.getString("sequence"),a.getLong("sourceSamples"),a.getLong("elapsedMs"));
                String key=a.getString("key");stopPlayback();JSONObject resume=savedPlaybackProgress(selected,key,parts.samples/16);
                try{beginPlayback(selected,key,parts,target.positionMs,resume.getDouble("speed"));}catch(Exception error){stopPlayback();throw error;}
                return new JSONObject().put("complete",parts.captureComplete).put("durationMs",parts.samples/16).put("positionMs",target.positionMs).put("speed",playingSpeed);
            }
            case "stopPlayback": stopPlayback(); return JSONObject.NULL;
            case "pausePlayback": {
                requirePlayback(a);if(!playbackPaused)player.pause();playbackPaused=true;savePlaybackProgress(true);
                return new JSONObject().put("positionMs",playbackPosition()).put("speed",playingSpeed);
            }
            case "resumePlayback": {
                requirePlayback(a);player.setPlaybackParams(new android.media.PlaybackParams().allowDefaults().setSpeed((float)playingSpeed).setPitch(1));playbackPaused=false;
                return new JSONObject().put("positionMs",playbackPosition()).put("speed",playingSpeed);
            }
            case "playbackStatus": {
                if (player == null || playingParts.isEmpty()) return new JSONObject().put("playing",false);
                NativeAudio.Part part = playingParts.get(playingIndex);
                boolean active=!playbackPaused&&player.isPlaying();savePlaybackProgress(false);
                return new JSONObject().put("playing",active).put("paused",playbackPaused).put("positionMs",playbackPosition()).put("speed",playingSpeed).put("key",playingKey).put("saveWarning",playbackSaveWarning==null?JSONObject.NULL:playbackSaveWarning);
            }
            case "setPlaybackSpeed":{
                requirePlayback(a);double rate=a.getDouble("speed");if(!PlaybackProgress.validSpeed(rate))throw new IllegalArgumentException("请选择支持的回听速度。");
                if(!playbackPaused)player.setPlaybackParams(new android.media.PlaybackParams().allowDefaults().setSpeed((float)rate).setPitch(1));
                playingSpeed=rate;savePlaybackProgress(true);return new JSONObject().put("speed",playingSpeed).put("paused",playbackPaused);
            }
            case "seekPlayback": {
                requirePlayback(a);seekPlayback(a.getLong("positionMs"));return new JSONObject().put("positionMs",playbackPosition()).put("speed",playingSpeed);
            }
            case "correct": {
                String key=a.getString("key"); session(key);
                MeetingStore.Snapshot saved=store().saveTranscriptCorrection(key,a.getLong("revision"),a.getString("text"));
                return new JSONObject().put("revision",saved.revision).put("text",saved.transcript);
            }
            case "timing": {
                String key=a.getString("key"); RecordingLibrary.Session s=session(key); MeetingStore ms=store();
                NativeAudio.PartsResult parts=ManagedAudioParts.prepare(s,root().resolve("companion-decoded-audio"));
                boolean original=ms.loadTranscriptBeforeCorrection(key)!=null;
                MeetingStore.TranscriptTiming timing=original ? ms.loadTranscriptBeforeCorrectionTimingParts(key,s,parts.directory) : ms.loadTranscriptTimingParts(key,s,parts.directory);
                if (timing==null) return new JSONObject().put("available",false).put("original",original);
                JSONArray windows=new JSONArray();
                for (MeetingStore.TranscriptWindow w:timing.windows) windows.put(new JSONObject().put("text",w.text).put("startMs",w.startMs).put("endMs",w.endMs));
                return new JSONObject().put("available",true).put("original",original).put("windows",windows)
                    .put("unrecognized",timing.unrecognized==null ? -1 : timing.unrecognized.size());
            }
            case "translate": {
                String key=a.getString("key"); session(key); MeetingStore.Snapshot m=store().load(key);
                if(m==null || m.transcript.trim().isEmpty()) throw new IllegalStateException("请先完成转写。");
                if(m.revision!=a.getLong("revision") || !m.transcript.equals(a.getString("source")))
                    throw new IllegalStateException("转写已更改，请重新打开录音后翻译。");
                String language=a.getString("language");
                String endpoint=a.getString("endpoint"),apiKey=a.getString("apiKey"),model=a.getString("model");
                String translated=TranslationChunks.run(m.transcript,chunk->{
                    JSONObject request=TranslationProtocol.request(chunk,language,model,endpoint);
                    String response=TranslationTransport.post(endpoint,apiKey,request.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
                    return TranslationProtocol.response(response);
                },(done,total)->progress("正在翻译 "+done+"/"+total));
                TranslationStore.Entry entry=new TranslationStore.Entry(key,language,m.transcript,m.revision,translated);
                JSONObject result=MeetingDetailAccess.translation(entry);
                try {
                    MeetingStore.Snapshot latest=store().load(key);
                    if(latest==null||!latest.transcript.equals(m.transcript))
                        throw new java.io.IOException("原文已变化，未覆盖已保存的译文；当前结果仍可复制。");
                    translations().save(entry);
                    result.put("saved",true);
                } catch(java.io.IOException error) {
                    result.put("saved",false).put("saveError","译文已生成，但尚未保存到本机；请先复制保留。" );
                }
                return result;
            }
            case "editMinutes": {
                String key=a.getString("key");session(key);MeetingStore ms=store();
                MeetingStore.Snapshot meeting=ms.load(key);MeetingStore.Minutes previous=ms.loadMinutes(key);
                if(meeting==null||previous==null)throw new IllegalStateException("请先打开已保存的纪要。");
                JSONObject content=MinutesHistoryAccess.content(previous.json);
                if(content==null||!a.getString("expectedMarkdown").equals(content.optString("markdown",null)))
                    throw new java.io.IOException("纪要已变化，请保留输入并重新打开录音核对。");
                boolean reviewed=a.optBoolean("reviewedCurrentSource",false);
                String edited=ManualMinutesEdits.apply(previous.json,a.getString("markdown"),a.optString("actionId",null),reviewed,meeting.revision);
                MeetingStore.Minutes saved;
                try{saved=ms.saveEditedMinutes(key,a.getLong("meetingRevision"),a.getLong("minutesRevision"),previous.json,edited,reviewed);}
                catch(java.io.IOException failure){throw new java.io.IOException("尚未确认保存，请保留输入并重新打开录音核对。",failure);}
                return new JSONObject().put("content",new JSONObject(saved.json)).put("revision",saved.revision).put("sourceChanged",saved.sourceChanged||saved.sourceMissing);
            }
            case "minutes": {
                String key=a.getString("key"); RecordingLibrary.Session s=session(key); MeetingStore ms=store();
                MeetingStore.Snapshot m=ms.load(key); if(m==null || m.transcript.trim().isEmpty()) throw new IllegalStateException("请先完成转写。");
                MeetingStore.Minutes old=ms.loadMinutes(key); long oldRevision=old==null?0:old.revision;
                JSONObject template=null;
                if(a.has("template")){
                    if(!a.getString("libraryToken").equals(libraries().token())||a.getLong("revision")!=m.revision||a.getLong("minutesRevision")!=oldRevision)throw new java.io.IOException("录音资料已更新，请重新打开后再整理；已有纪要仍保留。");
                    template=MinutesTemplateLibrary.template(a.getJSONObject("template"));
                }
                if(cancelMinutes.get()) throw new java.util.concurrent.CancellationException("已停止整理，未发送文字。");
                long samples=ManagedAudioParts.prepare(s, root().resolve("companion-decoded-audio")).samples;
                java.net.URI endpoint=new java.net.URI(a.getString("endpoint"));
                if (!"https".equalsIgnoreCase(endpoint.getScheme()) || endpoint.getHost()==null || endpoint.getUserInfo()!=null)
                    throw new IllegalArgumentException("请填写完整的 HTTPS 服务地址，地址中不要包含密钥。");
                JSONObject request=new JSONObject().put("sessionKey",key).put("title",recordingTitle(key,s))
                    .put("transcript",m.transcript).put("durationMillis",samples/16).put("endpoint",a.getString("endpoint")).put("model",a.getString("model"));
                if(cancelMinutes.get()) throw new java.util.concurrent.CancellationException("已停止整理，未发送文字。");
                if(template!=null)request.put("template",template);
                final long[] lastProgress={-1};
                String result=NativeMinutes.generateWithProgress(request.toString(),a.getString("apiKey"),root().resolve("companion-minutes-cache"),(done,total)->{
                    long percent=total>0?done*100/total:-1;
                    if(percent!=lastProgress[0]){lastProgress[0]=percent;progress("正在整理 " + (percent>=0?percent+"%":""));}
                    return !cancelMinutes.get();
                });
                ms.saveMinutes(key,m.revision,oldRevision,m.transcript,result); return new JSONObject(result);
            }
            default: throw new IllegalArgumentException("未知操作");
        }
    }
}
