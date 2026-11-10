package com.denzic.companion.app;
import java.nio.file.*;
import org.json.JSONObject;
public final class PlaybackLifecycleTest {
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]),meet=root.resolve("meetings"),rec=root.resolve("recordings");Files.createDirectories(meet);Files.createDirectories(rec);
  String a="5055423131304d324d455421:f0110a:1100901",b="5055423131304d324d455421:f0110a:1100902",binding=new String(new char[64]).replace('\0','d');
  PlaybackProgress progress=new PlaybackProgress(meet,p->{});progress.save(a,binding,123450,1.5,false);progress.save(b,binding,7890,.75,false);
  LocalRecordingLifecycle life=new LocalRecordingLifecycle(root,rec,meet,p->{});
  life.change(a,0,"trash","Explicit fictional checkpoint lifecycle test");
  if(progress.load(a,binding,1000000).getLong("positionMs")!=123450)throw new AssertionError("Trash must keep playback progress");
  life.change(a,1,"restore",null);
  if(progress.load(a,binding,1000000).getLong("positionMs")!=123450)throw new AssertionError("Restore lost playback progress");
  // A process killed between temp fsync and atomic publish may leave this file.
  // It must retain the same ownership prefix so exact-record purge also owns it.
  StringBuilder digest=new StringBuilder();for(byte value:java.security.MessageDigest.getInstance("SHA-256").digest(a.getBytes(java.nio.charset.StandardCharsets.UTF_8)))digest.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
  Path pending=meet.resolve(digest+".playback.json.pending-explicit-test.tmp");Files.write(pending,new byte[]{1,2,3});
  life.change(a,2,"trash","Explicit fictional checkpoint lifecycle test");JSONObject plan=life.preparePurge(a,3);
  if(plan.getInt("files")!=2)throw new AssertionError("Exact-record purge must own checkpoint and crash temporary, and no other recording");
  life.purge(a,3,plan.getString("token"));
  if(progress.load(a,binding,1000000).getBoolean("saved"))throw new AssertionError("Permanently deleted checkpoint remains");
  if(Files.exists(pending))throw new AssertionError("Owned interrupted-write metadata remains after permanent deletion");
  if(progress.load(b,binding,1000000).getLong("positionMs")!=7890)throw new AssertionError("Purge damaged another recording's progress");
  System.out.println("PASS unchanged LocalRecordingLifecycle retains checkpoint through trash/restore, permanently removes only the selected checkpoint and preserves the other recording.");
 }
}
