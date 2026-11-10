package com.denzic.companion.app;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import com.denzic.companion.mobile.ImportedAudio;
import com.denzic.companion.mobile.RecordingSyncService;
import com.denzic.companion.mobile.RecordingLibrary;
import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** User-selected media import continues with a visible, cancellable notification. */
public final class AudioImportService extends Service {
 private static final String CHANNEL="companion-file-import",CANCEL="com.denzic.companion.app.CANCEL_FILE_IMPORT";private static final int NOTIFICATION=1434;
 private static final AtomicBoolean RUNNING=new AtomicBoolean(),CANCELLED=new AtomicBoolean(),COMMITTING=new AtomicBoolean();private static volatile JSONObject current;private static volatile AudioImportService instance;
 private PowerManager.WakeLock wake;private volatile Thread job;
 static boolean isRunning(){return RUNNING.get();}
 static void cancel(){if(RUNNING.get()&&!COMMITTING.get())CANCELLED.set(true);}
 private static android.content.SharedPreferences preferences(Context context){return context.getSharedPreferences("companion-file-import",MODE_PRIVATE);}
 static synchronized JSONObject status(Context context)throws Exception {
  if(current!=null){JSONObject result=new JSONObject(current.toString());if(RUNNING.get()&&!result.optBoolean("running"))result.put("running",true).put("state","finishing").put("retryAvailable",false).put("message","正在完成最后的本机保存与收尾…");return result;}String saved=preferences(context).getString("job",null);if(saved==null)return new JSONObject().put("running",false).put("state","idle");JSONObject record=new JSONObject(saved);
  if(record.optBoolean("running")){
   // A process restart has no in-memory worker. Recover only its exact owned stage.
   if(RUNNING.get())return new JSONObject().put("running",true).put("state","starting");
   Path root=context.getFilesDir().toPath().toAbsolutePath().normalize(),stage=root.resolve(record.getString("stage"));retireStage(root,stage);
   Path target=root.resolve(record.getString("target"));String key=record.getString("key");boolean committed=false;
   if(target.getParent().equals(root)&&target.getFileName().toString().matches("companion-recordings(?:-[0-9a-f-]{36})?")){
    if("derive".equals(record.optString("operation"))){int recoveredCount=AudioDerivationJob.recover(record,target,AudioImportService::syncDirectory);committed=recoveredCount==record.getJSONObject("request").getJSONArray("outputs").length();}
    else{Path finalPath=target.resolve(ImportedAudio.folder(key));if(Files.exists(finalPath,LinkOption.NOFOLLOW_LINKS))try{ImportedAudio.read(finalPath).verifiedParts();committed=true;}catch(IOException ignored){}}
   }
   boolean derived="derive".equals(record.optString("operation"));record.put("running",false).put("state",committed?"complete":"interrupted").put("message",derived?(committed?"编辑片段已完整保存在本机，请在录音库查看。":"上次录音编辑已中断，原录音及已保存片段保留，可重试未完成片段。"):(committed?"录音已导入并保留，请在录音库查看。":"上次导入已中断，所选原文件未改变，请重新导入。"));preferences(context).edit().putString("job",record.toString()).commit();
  }
  current=publicStatus(record);return new JSONObject(current.toString());
 }
 private static JSONObject publicStatus(JSONObject value)throws Exception {JSONObject result="derive".equals(value.optString("operation"))?AudioDerivationJob.publicDetails(value):new JSONObject(value.toString());result.remove("stage");result.remove("target");return result;}
 static AudioDerivationAccess derivationAccess(Context context,LocalLibraryBackups library)throws IOException {
  Path root=context.getFilesDir().toPath(),recordings=library.recordings();LocalRecordingLifecycle lifecycle=new LocalRecordingLifecycle(root,recordings,library.meetings(),AudioImportService::syncDirectory);
  return new AudioDerivationAccess(root,recordings,root.resolve("companion-decoded-audio"),new AudioDerivationAccess.Library(){
   public String token()throws Exception{return library.token();}
   public RecordingLibrary.Session visible(String key)throws Exception {lifecycle.requireVisible(key);List<RecordingLibrary.Session> sessions=RecordingLibrary.inspectSession(recordings,key).sessions;if(sessions.size()!=1)throw new IOException("找不到这条完整本机录音，请重新选择。");return sessions.get(0);}
  });
 }
 static void startDerivation(Context context,JSONObject request)throws Exception {launchDerivation(context,AudioDerivationJob.create(request));}
 static void retryDerivation(Context context,String id)throws Exception {
  synchronized(AudioImportService.class){if(RUNNING.get())throw new IOException("已有录音任务正在进行，请等完成或取消。");status(context);String saved=preferences(context).getString("job",null);if(saved==null)throw new IOException("找不到上次编辑，请重新选择录音。");JSONObject record=new JSONObject(saved);if(!"derive".equals(record.optString("operation"))||!id.equals(record.optString("id"))||!AudioDerivationJob.publicDetails(record).optBoolean("retryAvailable"))throw new IOException("上次编辑状态已变化，请刷新后重试。");launchDerivation(context,record);}
 }
 private static void launchDerivation(Context context,JSONObject record)throws Exception {
  synchronized(AudioImportService.class){if(RUNNING.get())throw new IOException("已有录音任务正在进行，请等完成或取消。");status(context);if(!record.getJSONObject("request").getString("libraryToken").equals(new LocalLibraryBackups(context.getFilesDir().toPath()).token()))throw new IOException("资料库已切换，请重新选择录音编辑。");record.put("running",true).put("state","starting").put("message","正在准备录音编辑");current=publicStatus(record);RUNNING.set(true);CANCELLED.set(false);COMMITTING.set(false);}
  try{context.startForegroundService(new Intent(context,AudioImportService.class).putExtra("derivationJob",record.toString()));}catch(Exception error){RUNNING.set(false);current=null;throw error;}
 }
 static void start(Context context,Uri uri,String token)throws Exception {
  synchronized(AudioImportService.class){if(RUNNING.get())throw new IOException("已有文件正在导入，请等完成或取消。");status(context);RUNNING.set(true);CANCELLED.set(false);COMMITTING.set(false);current=new JSONObject().put("running",true).put("state","starting").put("message","正在准备导入…");}
  try{Intent intent=new Intent(context,AudioImportService.class).setData(uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION).putExtra("libraryToken",token);context.startForegroundService(intent);}catch(Exception error){RUNNING.set(false);current=null;throw error;}
 }
 @Override public void onCreate(){super.onCreate();instance=this;NotificationManager manager=getSystemService(NotificationManager.class);manager.createNotificationChannel(new NotificationChannel(CHANNEL,"文件导入",NotificationManager.IMPORTANCE_LOW));}
 @Override public int onStartCommand(Intent intent,int flags,int startId){
  if(intent!=null&&CANCEL.equals(intent.getAction())){cancel();if(!RUNNING.get())stopSelf();return START_NOT_STICKY;}
  if(job!=null)return START_NOT_STICKY;
  try{startForeground(NOTIFICATION,notification("正在导入录音"));wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"Companion:media-import");wake.acquire(60L*60*1000);}catch(Exception error){RUNNING.set(false);try{current=new JSONObject().put("running",false).put("state","failed").put("message","暂不能在后台导入，请保持应用打开后重试。");}catch(Exception ignored){}stopSelf();return START_NOT_STICKY;}
  String derivation=intent==null?null:intent.getStringExtra("derivationJob");if(intent==null||(intent.getData()==null&&derivation==null)){RUNNING.set(false);stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();return START_NOT_STICKY;}
  RUNNING.set(true);Uri uri=intent.getData();String token=intent.getStringExtra("libraryToken");job=new Thread(()->{if(derivation!=null)runDerivation(derivation);else runImport(uri,token);},"Companion-media-import");job.setPriority(Thread.MIN_PRIORITY+1);job.start();return START_NOT_STICKY;
 }
 private Notification notification(String message){boolean derived=current!=null&&"derive".equals(current.optString("operation"));PendingIntent cancel=PendingIntent.getService(this,0,new Intent(this,AudioImportService.class).setAction(CANCEL),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);Intent open=getPackageManager().getLaunchIntentForPackage(getPackageName());PendingIntent content=PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);return new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.stat_sys_download).setContentTitle(derived?"正在整理录音":"正在导入录音").setContentText(message).setOngoing(true).setOnlyAlertOnce(true).setContentIntent(content).addAction(new Notification.Action.Builder(null,derived?"取消整理":"取消导入",cancel).build()).build();}
 private void runImport(Uri uri,String token){Path stage=null;boolean locked=false;JSONObject record=null;
  try{
   if(RecordingSyncService.isRunning()||DeviceUpdateService.isRunning())throw new IOException("正在接收或升级录音卡，请等完成后再导入。");
   if(LocalLibraryBackups.BUSY.get())throw new IOException("正在操作本机资料，请稍后导入。");
   Path root=getFilesDir().toPath();LocalLibraryBackups library=new LocalLibraryBackups(root);if(token==null||!token.equals(library.token()))throw new IOException("当前资料库已变化，请重新选择导入文件。");
   String name="导入的录音",mime=getContentResolver().getType(uri);long expected=-1;
   try(android.database.Cursor c=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE},null,null,null)){if(c!=null&&c.moveToFirst()){int n=c.getColumnIndex(OpenableColumns.DISPLAY_NAME),s=c.getColumnIndex(OpenableColumns.SIZE);if(n>=0&&!c.isNull(n))name=c.getString(n);if(s>=0&&!c.isNull(s))expected=c.getLong(s);}}
   name=name==null?"导入的录音":name.replaceAll("[\\p{Cntrl}]"," ").trim();if(name.isEmpty())name="导入的录音";if(name.length()>256)name=name.substring(0,256);if(mime==null||mime.length()>256)mime="application/octet-stream";
   if(expected>2L*1024*1024*1024)throw new IOException("单个原文件最多支持2GB，请先分成较短的文件。");
   String id=UUID.randomUUID().toString(),key=ImportedAudio.hash(id.getBytes(java.nio.charset.StandardCharsets.UTF_8))+":1:1";stage=root.resolve(".companion-audio-import-"+id);Files.createDirectory(stage);Path target=library.recordings();
   record=new JSONObject().put("id",id).put("key",key).put("name",name).put("running",true).put("state","copying").put("message","正在保留原文件").put("stage",stage.getFileName().toString()).put("target",target.getFileName().toString());
   if(!preferences(this).edit().putString("job",record.toString()).commit())throw new IOException("导入任务尚未保存，请重试。");current=publicStatus(record);
   final JSONObject active=record;final Path work=stage;long total=0,lastNotice=0;
   try(InputStream in=getContentResolver().openInputStream(uri);FileOutputStream out=new FileOutputStream(stage.resolve("original.audio").toFile())){if(in==null)throw new IOException("无法读取所选文件，请重新选择。");byte[] bytes=new byte[65536];int n;while((n=in.read(bytes))!=-1){checkCancel();total+=n;if(total>2L*1024*1024*1024)throw new IOException("原文件超过2GB，请先分成较短的文件。");if(work.toFile().getUsableSpace()<n+16L*1024*1024)throw new IOException("手机存储空间不足，所选原文件未改变。");out.write(bytes,0,n);long now=SystemClock.elapsedRealtime();if(now-lastNotice>400){progress(active,"正在保留原文件",total,expected);lastNotice=now;}}out.getFD().sync();}
   if(total<=0||expected>=0&&total!=expected)throw new IOException("所选文件为空或读取不完整，请重新获取原文件。");checkCancel();String sourceHash=ImportedAudio.fileHash(stage.resolve("original.audio"));final long[] notice={0};
   List<Long> parts=PlatformMediaImport.decode(stage.resolve("original.audio"),stage,(phase,done,length)->{checkCancel();long now=SystemClock.elapsedRealtime();if(now-notice[0]>400){progress(active,phase,done,length);notice[0]=now;}});
   checkCancel();long waiting=SystemClock.elapsedRealtime();
   while(!LocalLibraryBackups.BUSY.compareAndSet(false,true)){checkCancel();progress(active,"等待当前资料操作完成",0,0);if(SystemClock.elapsedRealtime()-waiting>600000)throw new IOException("当前资料操作尚未完成，请稍后重新导入。");Thread.sleep(300);}
   locked=true;checkCancel();if(!token.equals(library.token()))throw new IOException("资料库已变化，本次没有提交导入。");
   COMMITTING.set(true);checkCancel();record.put("state","committing").put("message","正在校验并完成保存");current=publicStatus(record);
   ImportedAudio saved=ImportedAudio.publish(stage,target,key,name,mime,total,sourceHash,parts,AudioImportService::syncDirectory);stage=null;
   record.put("running",false).put("state","complete").put("message","录音已保存在本机，可回听或开始转写。").put("durationMs",saved.samples/16).put("originalBytes",saved.originalBytes).put("parts",saved.partCount());current=publicStatus(record);preferences(this).edit().putString("job",record.toString()).commit();
  }catch(Exception error){try{if(record==null)record=new JSONObject().put("id",UUID.randomUUID().toString());record.put("running",false).put("state",CANCELLED.get()?"cancelled":"failed").put("message",CANCELLED.get()?"已取消导入，所选原文件未改变。":importError(error));current=publicStatus(record);preferences(this).edit().putString("job",record.toString()).commit();}catch(Exception ignored){}
  }finally{finishJob(stage,locked);}
 }
 private void persistDerivation(JSONObject record,boolean committing)throws Exception {
  COMMITTING.set(committing);current=publicStatus(record);if(!preferences(this).edit().putString("job",record.toString()).commit())throw new IOException("编辑进度尚未安全保存，请稍后重试；已保存片段保留。");
  getSystemService(NotificationManager.class).notify(NOTIFICATION,notification(record.optString("message","正在整理录音")));
 }
 private void runDerivation(String serialized){Path stage=null,target=null;boolean locked=false;JSONObject record=null;
  try{
   record=new JSONObject(serialized);if(!"derive".equals(record.getString("operation")))throw new IOException("编辑任务类型无效。");
   if(RecordingSyncService.isRunning()||DeviceUpdateService.isRunning())throw new IOException("正在接收或升级录音卡，请等完成后再编辑。");
   if(!LocalLibraryBackups.BUSY.compareAndSet(false,true))throw new IOException("正在操作本机资料，请稍后重试编辑。");locked=true;
   Path root=getFilesDir().toPath();LocalLibraryBackups library=new LocalLibraryBackups(root);String token=record.getJSONObject("request").getString("libraryToken");if(!token.equals(library.token()))throw new IOException("资料库已切换，本次没有提交新的录音。");
   stage=Files.createDirectory(root.resolve(".companion-audio-import-"+UUID.randomUUID()));target=library.recordings();Files.createDirectories(target);
   record.put("stage",stage.getFileName().toString()).put("target",target.getFileName().toString()).put("key",record.getJSONObject("request").getJSONArray("outputs").getJSONObject(0).getString("key"));persistDerivation(record,false);
   final JSONObject active=record;final long[] last={0};AudioDerivationAccess access=derivationAccess(this,library);
   try(java.nio.channels.FileChannel channel=java.nio.channels.FileChannel.open(root.resolve(".companion-library.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);java.nio.channels.FileLock held=channel.tryLock()){
    if(held==null)throw new IOException("资料库正在更新，请稍后重试编辑。");
    AudioDerivationJob.run(active,stage,target,access,(done,total)->{checkCancel();long now=SystemClock.elapsedRealtime();if(now-last[0]>400)try{active.put("processed",done).put("total",total);current=publicStatus(active);getSystemService(NotificationManager.class).notify(NOTIFICATION,notification(active.optString("message","正在整理录音")));last[0]=now;}catch(Exception e){throw new IOException("编辑进度暂不能读取，请重试。",e);}},AudioImportService::syncDirectory,this::persistDerivation);
   }
   record.put("running",false).put("state","complete").put("message","编辑片段已保存在本机。原录音和原纪要保留，新片段可独立回听、转写。");persistDerivation(record,false);
  }catch(Exception error){
   try{
    if(record==null)record=new JSONObject().put("id",UUID.randomUUID().toString()).put("operation","derive");boolean recovered=false;
    if(target!=null&&record.has("request"))try{int count=AudioDerivationJob.recover(record,target,AudioImportService::syncDirectory);recovered=count==record.getJSONObject("request").getJSONArray("outputs").length();}catch(Exception ignored){}
    record.put("running",false).put("state",recovered?"complete":CANCELLED.get()?"cancelled":"interrupted");
    String detail=error.getMessage();if(detail==null||!detail.matches("(?s).*[\\u4e00-\\u9fff].*"))detail="录音编辑未完成。";
    record.put("message",recovered?"片段已完整保存在本机，上次保存结果现已核对。":detail+" 原录音和已确认保存的片段保留；重试会先核对保存结果，只处理未完成片段。");current=publicStatus(record);preferences(this).edit().putString("job",record.toString()).commit();
   }catch(Exception ignored){}
  }finally{finishJob(stage,locked);}
 }
 private void finishJob(Path stage,boolean locked){
  if(stage!=null)try{retireStage(getFilesDir().toPath(),stage);}catch(IOException ignored){}if(locked)LocalLibraryBackups.BUSY.set(false);
  // Publish availability only after the old foreground job has fully retired.
  // Otherwise a new accepted edit can reach the still-present old job thread.
  synchronized(AudioImportService.class){if(wake!=null&&wake.isHeld())wake.release();stopForeground(STOP_FOREGROUND_REMOVE);job=null;COMMITTING.set(false);RUNNING.set(false);stopSelf();}
 }
 private static String importError(Exception error){String text=error.getMessage();if(text!=null&&text.matches("(?s).*[\\u4e00-\\u9fff].*"))return text;if(text!=null&&text.toLowerCase(java.util.Locale.ROOT).contains("codec"))return "此设备暂不支持这个音频编码，请转换为MP3、M4A或WAV后重试。所选原文件未改变。";return "无法读取这个音频或视频文件，请确认文件完整且包含可用音轨，或转换为MP3、M4A、WAV后重试。所选原文件未改变。";}
 private void progress(JSONObject record,String message,long done,long total)throws IOException {try{record.put("state","processing").put("message",message).put("processed",done).put("total",total);current=publicStatus(record);getSystemService(NotificationManager.class).notify(NOTIFICATION,notification(message));}catch(Exception e){throw new IOException("导入进度暂不能保存，请重试。",e);}}
 private static void checkCancel()throws IOException {if(CANCELLED.get())throw new IOException("已取消导入，所选原文件未改变。");}
 static void syncDirectory(Path directory)throws IOException {java.io.FileDescriptor fd=null;try{fd=android.system.Os.open(directory.toString(),android.system.OsConstants.O_RDONLY|android.system.OsConstants.O_CLOEXEC|android.system.OsConstants.O_NOFOLLOW,0);android.system.Os.fsync(fd);}catch(android.system.ErrnoException e){throw new IOException("导入文件尚未安全保存。",e);}finally{if(fd!=null)try{android.system.Os.close(fd);}catch(android.system.ErrnoException ignored){}}}
 private static void retireStage(Path root,Path stage)throws IOException {root=root.toAbsolutePath().normalize();stage=stage.toAbsolutePath().normalize();if(!stage.getParent().equals(root)||!stage.getFileName().toString().matches("\\.companion-audio-import-[0-9a-f-]{36}")||Files.isSymbolicLink(stage))throw new IOException("导入临时目录无效，已保留。");if(!Files.exists(stage,LinkOption.NOFOLLOW_LINKS))return;try(java.util.stream.Stream<Path> paths=Files.walk(stage)){Path[] all=paths.sorted(Comparator.reverseOrder()).toArray(Path[]::new);for(Path p:all){if(Files.isSymbolicLink(p)||!p.normalize().startsWith(stage))throw new IOException("导入临时目录含未知路径，已保留。");Files.delete(p);}}}
 @Override public void onTimeout(int startId,int fgsType){cancel();}
 @Override public IBinder onBind(Intent intent){return null;}
 @Override public void onDestroy(){instance=null;if(wake!=null&&wake.isHeld())wake.release();super.onDestroy();}
}
