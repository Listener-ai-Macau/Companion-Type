package com.denzic.companion.app;

import android.app.Instrumentation;
import android.os.Bundle;
import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.denzic.companion.mobile.LibraryBackup;

/** Self-targeted test package. Never opens Companion storage, Bluetooth or UI. */
public final class LifecycleQa071 extends Instrumentation {
 private Bundle args;
 @Override public void onCreate(Bundle value){args=value;start();}
 private static void check(boolean condition,String error)throws IOException{if(!condition)throw new IOException(error);}
 private static void sync(Path path)throws IOException{
  java.io.FileDescriptor fd=null;
  try{fd=android.system.Os.open(path.toString(),android.system.OsConstants.O_RDONLY|android.system.OsConstants.O_CLOEXEC|android.system.OsConstants.O_NOFOLLOW,0);check(android.system.OsConstants.S_ISDIR(android.system.Os.fstat(fd).st_mode),"not a directory");android.system.Os.fsync(fd);}
  catch(android.system.ErrnoException error){throw new IOException(error);}finally{if(fd!=null)try{android.system.Os.close(fd);}catch(android.system.ErrnoException ignored){}}
 }
 private static String sha(Path p)throws Exception{StringBuilder out=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
 private static final String KEY="0102030405060708090a0b0c:1:2",OTHER="1102030405060708090a0b0c:1:2";
 private static List<Path> files(Path r,Path m,String key)throws Exception{
  String prefix=key.replace(':','-')+"-0-123-"+String.join("",Collections.nCopies(64,"a")),digest=LocalRecordingLifecycle.hash(key);
  return Arrays.asList(r.resolve(prefix+".cop1"),r.resolve(prefix+".meta"),m.resolve(digest+".meeting"),m.resolve(digest+".minutes"),m.resolve(digest+".title"),m.resolve("translations").resolve(digest+".translation"));
 }
 private static void writeFixtures(Path r,Path m,String key)throws Exception{for(Path p:files(r,m,key)){Files.createDirectories(p.getParent());Files.write(p,("公开虚构验收 "+key+" "+p.getFileName()).getBytes("UTF-8"));}}
 private static void expectRefusal(Action action)throws Exception{try{action.run();throw new AssertionError("operation should be refused");}catch(IOException expected){}}
 private interface Action{void run()throws Exception;}
 @Override public void onStart(){
  Bundle result=new Bundle();
  try{
   String run=args.getString("run"),stage=args.getString("stage");check(run!=null&&run.matches("[0-9a-f-]{36}"),"invalid synthetic run id");
   Path base=getTargetContext().getFilesDir().toPath().resolve("public-lifecycle-"+run),r=base.resolve("recordings"),m=base.resolve("meetings");
   JSONObject receipt=new JSONObject().put("stage",stage).put("run",run).put("pid",android.os.Process.myPid()).put("target",getTargetContext().getPackageName()).put("syntheticOnly",true).put("ownerCompanionDataOpened",false).put("bluetoothUsed",false).put("uiOpened",false);
   if(stage.equals("create")){
    check(!Files.exists(base),"preserve previous synthetic fixture");Files.createDirectories(r);Files.createDirectories(m);writeFixtures(r,m,KEY);writeFixtures(r,m,OTHER);
    JSONObject hashes=new JSONObject();for(Path p:files(r,m,KEY))hashes.put(base.relativize(p).toString(),sha(p));for(Path p:files(r,m,OTHER))hashes.put(base.relativize(p).toString(),sha(p));Files.write(base.resolve("before.json"),hashes.toString().getBytes("UTF-8"));
    LocalRecordingLifecycle life=new LocalRecordingLifecycle(r,m,LifecycleQa071::sync);
    life.change(KEY,0,"protect","");expectRefusal(()->life.change(KEY,1,"trash","公开测试"));life.change(KEY,1,"unprotect","");life.change(KEY,2,"trash","公开虚构会议");expectRefusal(()->life.requireVisible(KEY));
    check(life.trash().getJSONArray("rows").length()==1,"trash missing");receipt.put("result","PROTECTION_AND_DURABLE_TRASH_CREATED");
   }else{
    check(Files.isRegularFile(base.resolve("before.json")),"synthetic fixture missing");LocalRecordingLifecycle life=new LocalRecordingLifecycle(r,m,LifecycleQa071::sync);
    JSONObject hashes=new JSONObject(new String(Files.readAllBytes(base.resolve("before.json")),"UTF-8"));
    if(stage.equals("reopen")){
     check(life.get(KEY).getLong("revision")==3&&life.get(KEY).getLong("trashedAt")>0,"trash lost across process");life.change(KEY,3,"restore","");life.requireVisible(KEY);
     for(Iterator<String> it=hashes.keys();it.hasNext();){String path=it.next();check(sha(base.resolve(path)).equals(hashes.getString(path)),"restore changed original bytes");}
     life.change(KEY,4,"trash","公开虚构会议");life.change(OTHER,0,"protect","");ByteArrayOutputStream bytes=new ByteArrayOutputStream();LibraryBackup.write(bytes,r,m,null);Path restored=base.resolve("backup-reopened");LibraryBackup.restore(new ByteArrayInputStream(bytes.toByteArray()),restored);
     LocalRecordingLifecycle copy=new LocalRecordingLifecycle(restored.resolve("recordings"),restored.resolve("meetings"),LifecycleQa071::sync);check(copy.get(OTHER).getBoolean("protected")&&copy.get(KEY).getLong("trashedAt")>0,"backup lost lifecycle");
     receipt.put("result","NEW_PROCESS_RESTORE_BYTES_AND_ANDROID_BACKUP_PASSED");
    }else if(stage.equals("interrupt")){
     JSONObject plan=life.preparePurge(KEY,5);final int[] calls={0};LocalRecordingLifecycle partial=new LocalRecordingLifecycle(r,m,LifecycleQa071::sync,path->{if(++calls[0]==2)throw new IOException("synthetic interruption");return Files.deleteIfExists(path);});
     expectRefusal(()->partial.purge(KEY,5,plan.getString("token")));check(life.get(KEY).getBoolean("purging")&&life.get(KEY).getLong("revision")==6,"partial deletion status not durable");expectRefusal(()->life.change(KEY,6,"restore",""));
     receipt.put("result","PARTIAL_CLEAR_RETAINED_FOR_NEXT_PROCESS_RETRY");
    }else if(stage.equals("retry")){
     check(life.get(KEY).getBoolean("purging"),"partial clear lost after process restart");JSONObject plan=life.preparePurge(KEY,6);life.purge(KEY,6,plan.getString("token"));
     for(Path p:files(r,m,KEY))check(!Files.exists(p),"owned original remains");for(Path p:files(r,m,OTHER))check(sha(p).equals(hashes.getString(base.relativize(p).toString())),"other recording changed");
     check(life.get(OTHER).getBoolean("protected")&&life.trash().getJSONArray("rows").length()==0,"other protection changed or cleared row retained");expectRefusal(()->life.change(KEY,0,"protect",""));receipt.put("result","NEW_PROCESS_SCOPED_CLEAR_RETRY_AND_OTHER_RECORDING_BYTES_PASSED");
    }else throw new IOException("unknown test stage");
   }
   result.putString("resultJson",receipt.toString());finish(android.app.Activity.RESULT_OK,result);
  }catch(Throwable error){result.putString("error",android.util.Log.getStackTraceString(error));finish(android.app.Activity.RESULT_CANCELED,result);}
 }
}
