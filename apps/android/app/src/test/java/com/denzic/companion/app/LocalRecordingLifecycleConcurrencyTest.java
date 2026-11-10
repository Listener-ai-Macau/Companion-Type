package com.denzic.companion.app;
import java.nio.file.*;
import java.util.concurrent.*;
import org.json.JSONObject;

/** The WebView asset reader and bridge worker are distinct threads/instances. */
public final class LocalRecordingLifecycleConcurrencyTest {
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]),rec=root.resolve("recordings"),meet=root.resolve("meetings");Files.createDirectories(rec);Files.createDirectories(meet);
  String key="5055423131304d324d455421:f0110a:1100901";
  CountDownLatch published=new CountDownLatch(1),release=new CountDownLatch(1),readerStarted=new CountDownLatch(1);
  LocalRecordingLifecycle writer=new LocalRecordingLifecycle(root,rec,meet,path->{published.countDown();try{if(!release.await(5,TimeUnit.SECONDS))throw new java.io.IOException("Test release missing");}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}});
  LocalRecordingLifecycle reader=new LocalRecordingLifecycle(root,rec,meet,path->{});
  ExecutorService workers=Executors.newFixedThreadPool(2);
  try{
   Future<JSONObject> saving=workers.submit(()->writer.change(key,0,"protect",null));
   if(!published.await(3,TimeUnit.SECONDS))throw new AssertionError("Writer did not reach held durable publication");
   Future<JSONObject> reading=workers.submit(()->{readerStarted.countDown();return reader.get(key);});
   if(!readerStarted.await(1,TimeUnit.SECONDS))throw new AssertionError("Reader did not start");
   try{reading.get(300,TimeUnit.MILLISECONDS);throw new AssertionError("Reader must observe the completed protected operation, not run through its lock");}
   catch(TimeoutException expected){}
   release.countDown();saving.get(3,TimeUnit.SECONDS);JSONObject state=reading.get(3,TimeUnit.SECONDS);
   if(!state.getBoolean("protected")||state.getLong("revision")!=1)throw new AssertionError("Reader did not observe durable latest metadata");
   try{reader.change(key,0,"unprotect",null);throw new AssertionError("Stale write accepted after serialization");}catch(java.io.IOException expected){if(!expected.getMessage().contains("已变化"))throw expected;}
   reader.change(key,1,"unprotect",null);reader.change(key,2,"trash","Public lifecycle concurrency fixture");
   try{reader.requireVisible(key);throw new AssertionError("Trashed recording became visible");}catch(java.io.IOException expected){if(!expected.getMessage().contains("回收站"))throw expected;}
   reader.change(key,3,"restore",null);reader.requireVisible(key);
   System.out.println("PASS distinct same-process bridge/asset instances serialize lifecycle reads with durable writes; stale revision and trash visibility guards retained.");
  }finally{release.countDown();workers.shutdownNow();workers.awaitTermination(3,TimeUnit.SECONDS);}
 }
}
