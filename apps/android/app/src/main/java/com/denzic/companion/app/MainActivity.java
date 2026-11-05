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
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private List<BluetoothDevice> devices = new ArrayList<>();
    private List<RecorderWire.Descriptor> segments = new ArrayList<>();
    private BluetoothDevice selectedDevice;
    private MediaPlayer player;
    private List<NativeAudio.Part> playingParts = new ArrayList<>();
    private int playingIndex;
    private final AtomicBoolean cancelTranscription = new AtomicBoolean();
    private final AtomicBoolean cancelMinutes = new AtomicBoolean();
    private long documentRequestId;
    private String documentKey, documentFormat;
    // A restored Activity has a new WebView, so its old JavaScript request ID is no longer valid.
    private boolean documentRequestRestored;
    private long libraryRequestId;
    private String libraryRequestKind,libraryRequestToken,documentLibraryToken;
    private boolean libraryRequestRestored;
    private Path root() { return getFilesDir().toPath(); }
    private LocalLibraryBackups libraries(){return new LocalLibraryBackups(root());}
    private Path recordings() throws java.io.IOException { return libraries().recordings(); }
    private MeetingStore store() throws java.io.IOException { return new MeetingStore(libraries().meetings()); }
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
        return defaultRecordingTitle(session.segments.get(0).descriptor.sessionId, false);
    }

    private static String defaultRecordingTitle(long sessionId, boolean unreadable) {
        String id=Long.toUnsignedString(sessionId);
        String suffix=id.substring(Math.max(0,id.length()-6));
        return (unreadable?"名称暂不可用 · ":"未命名录音 · ")+suffix;
    }
    private static long completeAudioDurationMs(RecordingLibrary.Session session) {
        if(session.state!=RecordingLibrary.SessionState.COMPLETE)return -1;
        long samples=0;
        try { for(RecordingLibrary.Entry entry:session.segments) samples=Math.addExact(samples,entry.descriptor.sampleCount); }
        catch(ArithmeticException invalid) { return -1; }
        long ms=samples/16;
        return ms>0 && ms<=9007199254740991L ? ms : -1;
    }

    @SuppressLint("SetJavaScriptEnabled") @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) {
            libraryRequestId=state.getLong("libraryRequestId",0);libraryRequestKind=state.getString("libraryRequestKind");libraryRequestToken=state.getString("libraryRequestToken");
            libraryRequestRestored=libraryRequestId!=0;documentLibraryToken=state.getString("documentLibraryToken");
            long pendingId=state.getLong("documentRequestId",0);
            String pendingKey=state.getString("documentKey"), pendingFormat=state.getString("documentFormat");
            if (pendingId!=0 && pendingKey!=null && DocumentRecovery.isPickerFormat(pendingFormat)) {
                documentRequestId=pendingId;documentKey=pendingKey;documentFormat=pendingFormat;documentRequestRestored=true;
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
                if (segments.isEmpty() || !"www".equals(segments.get(0))) return blockedAsset();
                StringBuilder name = new StringBuilder();
                for (String part : segments) {
                    if (part.isEmpty() || part.equals(".") || part.equals("..") || part.contains("/") || part.contains("\\")) return blockedAsset();
                    if (name.length() > 0) name.append('/');
                    name.append(part);
                }
                String asset = name.toString();
                String mime = asset.endsWith(".js") ? "text/javascript" : asset.endsWith(".css") ? "text/css" : asset.endsWith(".html") ? "text/html" : "application/octet-stream";
                try { return new WebResourceResponse(mime, "UTF-8", getAssets().open(asset)); }
                catch (java.io.IOException error) { return blockedAsset(); }
            }
        });
        web.addJavascriptInterface(new Bridge(), "CompanionNative");
        setContentView(content);
        web.loadUrl("https://appassets.androidplatform.net/www/index.html");
    }
    private static WebResourceResponse blockedAsset() {
        return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", java.util.Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        state.putLong("libraryRequestId",libraryRequestId);state.putString("libraryRequestKind",libraryRequestKind);state.putString("libraryRequestToken",libraryRequestToken);state.putString("documentLibraryToken",documentLibraryToken);
        if (documentRequestId!=0) {
            state.putLong("documentRequestId",documentRequestId);
            state.putString("documentKey",documentKey);
            state.putString("documentFormat",documentFormat);
        }
    }
    @Override protected void onResume() {
        super.onResume();
        if(libraryRequestRestored&&libraryRequestId!=0){libraryRequestId=0;libraryRequestKind=null;libraryRequestToken=null;libraryRequestRestored=false;android.widget.Toast.makeText(this,"备份文件选择已中断，原资料仍保留，请重新操作。",android.widget.Toast.LENGTH_LONG).show();}
        // If a restored picker never delivers a result, do not block future exports.
        // Android delivers an activity result before the following onResume.
        if (documentRequestRestored && documentRequestId!=0) {
            documentRequestId=0;documentKey=null;documentFormat=null;documentRequestRestored=false;
            android.widget.Toast.makeText(this,"文件选择已中断，请检查保存位置后重试。",android.widget.Toast.LENGTH_LONG).show();
        }
    }
    @Override protected void onDestroy() {
        worker.execute(this::stopPlayback);
        web.removeJavascriptInterface("CompanionNative");
        worker.shutdown();
        super.onDestroy();
    }
    @Override public void onBackPressed() { web.evaluateJavascript("window.companionBack()", null); }
    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if(requestCode==32){finishLibraryPicker(resultCode,data);return;}
        if (requestCode != 31) return;
        final long id=documentRequestId; final String key=documentKey, format=documentFormat;
        final boolean restored=documentRequestRestored;
        final String libraryToken=documentLibraryToken;documentLibraryToken=null;
        documentRequestId=0; documentKey=null; documentFormat=null;documentRequestRestored=false;
        if (id==0 || key==null || !DocumentRecovery.isPickerFormat(format)) return;
        if (resultCode!=RESULT_OK || data==null || data.getData()==null) { replyDocument(id,false,null,restored); return; }
        android.net.Uri destination=data.getData();
        worker.execute(() -> {
            try {
                if(LocalLibraryBackups.BUSY.get()||libraryToken==null||!libraryToken.equals(libraries().token()))throw new java.io.IOException("资料已切换，请重新选择要导出的录音。");
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
    private void requireLibraryIdle() throws Exception {
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
        @JavascriptInterface public void libraryArchive(long id,String kind,String token){
            worker.execute(()->{
                try{
                    requireLibraryIdle();if(LocalLibraryBackups.BUSY.get())throw new java.io.IOException("资料操作正在进行，请稍后重试。");
                    if(!token.equals(libraries().token()))throw new java.io.IOException("资料已变化，请刷新备份页面后重试。");
                    if(!("backup".equals(kind)||"restore".equals(kind)))throw new java.io.IOException("不支持的资料操作。");
                    runOnUiThread(()->{
                        if(isFinishing()||isDestroyed())return;
                        if(documentRequestId!=0||libraryRequestId!=0){reply(id,null,"已有文件选择操作正在进行。");return;}
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
        @JavascriptInterface public void openBluetoothSettings() {
            runOnUiThread(() -> {
                try { startActivity(new Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS)); }
                catch (android.content.ActivityNotFoundException error) { android.widget.Toast.makeText(MainActivity.this,"无法打开手机蓝牙设置，请在系统设置中配对。",android.widget.Toast.LENGTH_LONG).show(); }
            });
        }
        @JavascriptInterface public void exportDocument(long id, String key, String format) {
            runOnUiThread(() -> {
                if (documentRequestId!=0||libraryRequestId!=0||LocalLibraryBackups.BUSY.get()) { reply(id,null,"已有文件选择或资料操作正在进行。"); return; }
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
        @JavascriptInterface public void exportAudio(long id,String key) {
            runOnUiThread(() -> {
                if (documentRequestId!=0||libraryRequestId!=0||LocalLibraryBackups.BUSY.get()) { reply(id,null,"已有文件选择或资料操作正在进行。");return; }
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
        @JavascriptInterface public void call(long id, String method, String json) {
            if ("transcribe".equals(method) || "transcribeCloud".equals(method)) cancelTranscription.set(false);
            if ("minutes".equals(method)) cancelMinutes.set(false);
            worker.execute(() -> {
                try { reply(id, execute(method, new JSONObject(json)), null); }
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
        for (RecordingLibrary.Session s : RecordingLibrary.inspect(recordings()).sessions)
            if (!s.segments.isEmpty() && MeetingStore.sessionKey(s.segments.get(0).descriptor).equals(key)) return s;
        throw new IllegalStateException("找不到这条本机录音，请刷新列表。");
    }
    private JSONObject syncStatus() throws Exception {
        RecordingSyncStatus s = RecordingSyncService.status(this);
        String saved=getSharedPreferences("companion_recording_sync",MODE_PRIVATE).getString("directory",null);
        if(!s.running&&saved!=null&&!saved.equals(recordings().getFileName().toString()))return new JSONObject().put("state","idle").put("detail","原接收任务保留在另一份资料中；切回该资料后可继续。").put("running",false).put("hasSavedTask",false);
        return new JSONObject().put("state", s.state).put("detail", s.detail).put("running", s.running).put("hasSavedTask", s.hasSavedTask);
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
        if (player != null) { player.release(); player = null; }
        playingParts = new ArrayList<>();
    }
    private void playPart() throws Exception { playPart(0); }
    private void playPart(int positionMs) throws Exception { playPart(positionMs, true); }
    private void playPart(int positionMs, boolean startImmediately) throws Exception {
        if (playingIndex >= playingParts.size()) { stopPlayback(); playbackEvent("stopped", "回听结束"); return; }
        MediaPlayer next = new MediaPlayer();
        try {
            next.setDataSource(playingParts.get(playingIndex).path.toString());
            next.setOnCompletionListener(done -> {
                if(worker.isShutdown())return;
                try { worker.execute(() -> {
                    if (player != done) return;
                    done.release(); player = null; playingIndex++;
                    try { playPart(); } catch (Exception e) { stopPlayback(); playbackEvent("stopped", "回听失败：" + e.getMessage()); }
                }); } catch(java.util.concurrent.RejectedExecutionException ignored) { /* Activity is closing. */ }
            });
            next.prepare(); player = next;
            if (positionMs > 0) next.seekTo(positionMs);
            if (startImmediately) next.start();
        } catch (Exception error) { next.release(); throw error; }
    }
    private Object execute(String method, JSONObject a) throws Exception {
        if(LocalLibraryBackups.BUSY.get()&&!"status".equals(method))throw new IllegalStateException("正在备份或恢复资料，请等待完成。");
        switch (method) {
            case "libraryStatus":return libraries().status();
            case "minutesTemplates":return new MinutesTemplateLibrary(libraries().meetings()).load().put("libraryToken",libraries().token());
            case "minutesTemplateChange":{
                if(!a.getString("libraryToken").equals(libraries().token()))throw new java.io.IOException("资料已切换，请重新读取模板。");
                return new MinutesTemplateLibrary(libraries().meetings()).change(a.getString("etag"),a.getString("action"),a.optJSONObject("template"),a.optString("key","")).put("libraryToken",libraries().token());
            }
            case "libraryActivate":{
                requireLibraryIdle();if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new java.io.IOException("资料操作正在进行。");
                try{stopPlayback();JSONObject result=libraries().activate(a.getString("id"),a.getString("token"));selectedDevice=null;segments=new ArrayList<>();return result;}finally{LocalLibraryBackups.BUSY.set(false);}
            }
            case "devices": {
                if (!bluetoothGranted()) throw new IllegalStateException("请先允许附近设备权限，再重新读取。");
                devices = CompanionAndroidBackend.pairedDevices(this); segments = new ArrayList<>(); selectedDevice = null;
                JSONArray out = new JSONArray();
                for (int i = 0; i < devices.size(); i++) {
                    BluetoothDevice d = devices.get(i);
                    out.put(new JSONObject().put("index", i).put("name", d.getName() == null ? "未命名设备" : d.getName()).put("address", d.getAddress()));
                }
                return out;
            }
            case "catalog": {
                if (RecordingSyncService.isRunning()) throw new IllegalStateException("正在接收录音，请先等待接收结束。");
                selectedDevice = devices.get(a.getInt("index")); segments = new ArrayList<>();
                try (RecordingClient client = CompanionAndroidBackend.connect(this, selectedDevice)) { segments = client.listRecordings(); }
                JSONArray out = new JSONArray();
                for (int i = 0; i < segments.size(); i++) {
                    RecorderWire.Descriptor d = segments.get(i);
                    out.put(new JSONObject().put("index", i).put("session", Long.toUnsignedString(d.sessionId))
                            .put("segment", d.segmentIndex).put("bytes", d.encodedLength));
                }
                return out;
            }
            case "sync": {
                if (selectedDevice == null) throw new IllegalStateException("请重新选择设备和录音。");
                File dir = recordings().toFile();
                if (!dir.isDirectory() && !dir.mkdirs()) throw new IllegalStateException("无法创建录音目录。");
                RecordingSyncService.start(this, selectedDevice, segments.get(a.getInt("index")), dir);
                return syncStatus();
            }
            case "resume": {
                String saved=getSharedPreferences("companion_recording_sync",MODE_PRIVATE).getString("directory",null);
                if(saved==null||!saved.equals(recordings().getFileName().toString()))throw new java.io.IOException("原接收任务属于另一份资料，请先切回原资料。");
                RecordingSyncService.resume(this);return syncStatus();
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
                RecordingSyncService.resumePending(this, selectedDevice, recordings().toFile());
                return syncStatus();
            }
            case "stopSync": RecordingSyncService.stop(this); return syncStatus();
            case "status": return syncStatus();
            case "licenses": {
                String[] files = {"ShadcnDashboardMIT.txt", "companion-android-native-notices.txt", "companion-asr-runtime-notices.txt", "companion-local-model-notices.txt", "companion-document-export-notices.txt", "companion-document-font-OFL.txt", "companion-asr-runtime/onnxruntime-LICENSE.txt", "companion-asr-runtime/onnxruntime-ThirdPartyNotices.txt", "companion-asr-runtime/sherpa-onnx-LICENSE.txt"};
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
                try (RecordingClient client = CompanionAndroidBackend.connect(this, selectedDevice)) {
                    return new JSONObject(client.controlSessions(root().resolve("companion-control")));
                }
            }
            case "control": {
                boolean receiving=RecordingSyncService.isRunning();
                if (!receiving && selectedDevice == null) throw new IllegalStateException("请先选择录音卡。");
                String action = a.getString("action");
                if (receiving && ("START".equals(action)||"ADOPT".equals(action)))
                    throw new IllegalStateException("接收期间不能开始或接管新的录音。");
                try (RecordingClient client = receiving ? null : CompanionAndroidBackend.connect(this, selectedDevice)) {
                    JSONObject inventory = new JSONObject(receiving ? RecordingSyncService.controlSessions(root().resolve("companion-control")) : client.controlSessions(root().resolve("companion-control")));
                    JSONArray saved = inventory.getJSONArray("sessions");
                    if (inventory.optInt("unreadableCount") > 0) throw new IllegalStateException("有录音控制记录无法读取，请保留原录音并先检查设备。");
                    if ("ADOPT".equals(action)) return new JSONObject(client.adoptLocalControl(root().resolve("companion-control")));
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
                    return new JSONObject(receiving ? RecordingSyncService.control(root().resolve("companion-control"),host,command,0) : client.control(root().resolve("companion-control"),host,command,0));
                }
            }
            case "library": {
                RecordingLibrary.Inventory inv = RecordingLibrary.inspect(recordings()); JSONArray rows = new JSONArray(); int titleProblems=0,searchProblems=0;
                String query=a.optString("query","").trim();
                MeetingLibrarySearch search=query.isEmpty()?null:new MeetingLibrarySearch(query,!"title".equals(a.optString("scope","all")));
                MeetingLibrarySearch.Reader reader=(key,source)->{
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
                    if (s.segments.isEmpty()) continue;
                    RecorderWire.Descriptor d = s.segments.get(0).descriptor;
                    String key=MeetingStore.sessionKey(d);
                    String title;try { title=recordingTitle(key,s); } catch (java.io.IOException error) {title=defaultRecordingTitle(d.sessionId,true);titleProblems++;}
                    MeetingLibrarySearch.Result found=search==null?null:search.find(key,title,reader);
                    if(found!=null){searchProblems+=found.unreadable;if(found.match==null)continue;}
                    JSONObject row=new JSONObject().put("key", key).put("title",title).put("session", Long.toUnsignedString(d.sessionId))
                            .put("state", s.state.name()).put("segments", s.segments.size());
                    long duration=completeAudioDurationMs(s);if(duration>0)row.put("durationMs",duration);
                    if(found!=null)row.put("matchSource",found.match.source).put("matchSnippet",found.match.snippet)
                        .put("matchStart",found.match.start).put("matchEnd",found.match.end).put("matchStale",found.match.stale);
                    rows.put(row);
                }
                return new JSONObject().put("rows", rows).put("problems", inv.problems.size()+titleProblems).put("searchProblems",searchProblems)
                    .put("searchQuery",query).put("searchScope","title".equals(a.optString("scope","all"))?"title":"all");
            }
            case "detail": {
                String key = a.getString("key"); session(key);
                return MeetingDetailAccess.read(store(),key,translations());
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
                RecordingLibrary.Session s = session(a.getString("key"));
                NativeAudio.PartsResult parts = ManagedAudioParts.prepare(s, root().resolve("companion-decoded-audio"));
                if (parts.parts.isEmpty()) throw new IllegalStateException("没有可回听的音频。");
                playingParts = parts.parts; playingIndex = 0; playPart();
                return new JSONObject().put("complete", parts.captureComplete).put("durationMs", parts.samples / 16);
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
                stopPlayback();playingParts=parts.parts;playingIndex=target.part;
                try{playPart(target.offsetMs);}catch(Exception error){stopPlayback();throw error;}
                return new JSONObject().put("complete",parts.captureComplete).put("durationMs",parts.samples/16).put("positionMs",target.positionMs);
            }
            case "stopPlayback": stopPlayback(); return JSONObject.NULL;
            case "pausePlayback": {
                if (player == null || playingParts.isEmpty()) throw new IllegalStateException("请先播放录音。");
                if (player.isPlaying()) player.pause();
                return new JSONObject().put("positionMs",playingParts.get(playingIndex).firstSample/16 + player.getCurrentPosition());
            }
            case "resumePlayback": {
                if (player == null || playingParts.isEmpty()) throw new IllegalStateException("回听已结束，请重新播放。");
                if (!player.isPlaying()) player.start();
                return JSONObject.NULL;
            }
            case "playbackStatus": {
                if (player == null || playingParts.isEmpty()) return new JSONObject().put("playing",false);
                NativeAudio.Part part = playingParts.get(playingIndex);
                boolean active=player.isPlaying();
                return new JSONObject().put("playing",active).put("paused",!active).put("positionMs",part.firstSample/16 + player.getCurrentPosition());
            }
            case "seekPlayback": {
                if (player == null || playingParts.isEmpty()) throw new IllegalStateException("请先播放录音。");
                long target = Math.max(0,a.getLong("positionMs"));
                int index = playingParts.size()-1;
                for (int i=0;i<playingParts.size();i++) {
                    NativeAudio.Part part = playingParts.get(i);
                    if (target < (part.firstSample+part.samples)/16) { index=i; break; }
                }
                NativeAudio.Part part = playingParts.get(index);
                int within = (int)Math.max(0,Math.min(Math.max(0,part.samples/16-1),target-part.firstSample/16));
                if (index == playingIndex) player.seekTo(within);
                else { boolean wasPlaying=player.isPlaying(); player.release(); player=null; playingIndex=index; playPart(within,wasPlaying); }
                return JSONObject.NULL;
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
                    JSONObject request=TranslationProtocol.request(chunk,language,model);
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
