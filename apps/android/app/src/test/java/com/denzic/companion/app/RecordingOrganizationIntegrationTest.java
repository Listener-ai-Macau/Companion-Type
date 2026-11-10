package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.json.*;

public final class RecordingOrganizationIntegrationTest {
 interface Attempt{void run()throws Exception;}
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 static void rejects(Attempt attempt)throws Exception{try{attempt.run();throw new AssertionError("Expected rejection");}catch(IOException expected){}}
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]),rec=root.resolve("recordings"),meet=root.resolve("meetings");Files.createDirectories(rec);Files.createDirectories(meet);
  ImportedAudio a=ImportedAudioIntegrationTest.create(root,rec,"organization-A",false),b=ImportedAudioIntegrationTest.create(root,rec,"organization-B",false);
  byte[] soundA=Files.readAllBytes(a.original),soundB=Files.readAllBytes(b.original);Set<String> visible=new HashSet<>(Arrays.asList(a.key,b.key));JSONArray both=new JSONArray().put(a.key).put(b.key);
  RecordingOrganization store=new RecordingOrganization(meet,p->{});check(store.read().getLong("revision")==0,"Fresh metadata must be empty");
  JSONObject moved=store.change(0,both,"move"," 客户 / 项目A ",null,visible);check(moved.getLong("revision")==1&&RecordingOrganization.item(moved,a.key).getString("folder").equals("客户/项目A"),"Batch move or folder normalization failed");
  JSONArray labels=new JSONArray().put("需跟进").put("PROJECT");JSONObject tagged=store.change(1,both,"addTags",null,labels,visible);
  JSONObject same=store.change(2,both,"addTags",null,new JSONArray().put("project"),visible);check(same.getLong("revision")==2&&RecordingOrganization.item(same,a.key).getJSONArray("tags").length()==2,"Repeated tag add must not duplicate tags or lose the original label");
  Path file=meet.resolve("recording-organization.json");byte[] before=Files.readAllBytes(file);
  rejects(()->store.change(0,both,"move","stale",null,visible));rejects(()->store.change(2,new JSONArray().put(b.key).put("abcdefabcdefabcdef:1:1"),"move","wrong",null,visible));rejects(()->store.change(2,both,"move","../wrong",null,visible));check(Arrays.equals(before,Files.readAllBytes(file)),"Rejected selection/stale/path operation wrote metadata");
  JSONArray twenty=new JSONArray();for(int i=0;i<20;i++)twenty.put("标签"+i);store.change(2,new JSONArray().put(a.key),"setTags",null,twenty,visible);before=Files.readAllBytes(file);
  rejects(()->store.change(3,new JSONArray().put(b.key).put(a.key),"addTags",null,new JSONArray().put("NEW"),visible));check(Arrays.equals(before,Files.readAllBytes(file)),"Later over-limit target partially changed the first selected recording");
  JSONObject intact=store.read();ByteArrayOutputStream backup=new ByteArrayOutputStream();LibraryBackup.write(backup,rec,meet,null);Path restored=root.resolve("restored");LibraryBackup.restore(new ByteArrayInputStream(backup.toByteArray()),restored);
  check(Arrays.equals(before,Files.readAllBytes(restored.resolve("meetings/recording-organization.json"))),"Backup changed classification bytes");
  RecordingOrganization restoredStore=new RecordingOrganization(restored.resolve("meetings"),p->{});check(restoredStore.read().toString().equals(intact.toString()),"Restored folders/tags/revision differ");
  byte[] damaged=before.clone();damaged[damaged.length/2]^=1;Files.write(file,damaged);rejects(()->store.change(3,both,"move","must not replace",null,visible));check(Arrays.equals(damaged,Files.readAllBytes(file)),"Corrupt metadata was overwritten");
  LocalRecordingLifecycle life=new LocalRecordingLifecycle(root,rec,meet,p->{});life.change(a.key,0,"trash","公开分类夹具A");rejects(()->life.preparePurge(a.key,1));check(Arrays.equals(soundA,Files.readAllBytes(a.original)),"Unverified classification allowed audio deletion");
  Files.write(file,before);JSONObject offer=life.preparePurge(a.key,1);life.purge(a.key,1,offer.getString("token"));JSONObject after=store.read();check(!after.getJSONObject("entries").has(a.key),"Permanent purge retained target folder/tags");check(RecordingOrganization.item(after,b.key).toString().equals(RecordingOrganization.item(intact,b.key).toString())&&Arrays.equals(soundB,Files.readAllBytes(b.original)),"Permanent purge changed another recording");
  long revision=after.getLong("revision");RecordingOrganization uncertain=new RecordingOrganization(meet,p->{throw new IOException("Injected directory sync failure after publication");});rejects(()->uncertain.change(revision,new JSONArray().put(b.key),"move","待确认",null,visible));check(RecordingOrganization.item(store.read(),b.key).getString("folder").equals("待确认"),"Lost acknowledgement must remain readable and not roll back a published change");rejects(()->store.change(revision,new JSONArray().put(b.key),"move","stale retry",null,visible));
  System.out.println("PASS atomic multi-record folder/tag edits, stale/foreign/late-limit rejection without partial writes, exact backup restore, corrupt-file preservation, purge-only-target metadata and original audio protection, and uncertain-write recovery. JVM public fixtures; ordinary phone UI not claimed.");
 }
}
