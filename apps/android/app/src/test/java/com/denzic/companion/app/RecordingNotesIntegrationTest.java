package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import org.json.*;

public final class RecordingNotesIntegrationTest {
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 interface Attempt{void run()throws Exception;}
 static void rejects(Attempt attempt)throws Exception{try{attempt.run();throw new AssertionError("Expected rejection");}catch(IOException expected){}}
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]),rec=root.resolve("recordings"),meet=root.resolve("meetings");Files.createDirectories(rec);Files.createDirectories(meet);
  ImportedAudio a=ImportedAudioIntegrationTest.create(root,rec,"notes-A",false),b=ImportedAudioIntegrationTest.create(root,rec,"notes-B",false);byte[] otherOriginal=Files.readAllBytes(b.original);RecordingNotes store=new RecordingNotes(meet,p->{});
  check(store.read(a.key).getLong("revision")==0,"Fresh recording notes not empty");JSONObject first=store.save(a.key,0,"","公开夹具：十点核对预算",1000L,3000);String id=first.getJSONArray("entries").getJSONObject(0).getString("id");
  rejects(()->store.save(a.key,0,id,"Stale overwrite",1000L,3000));rejects(()->store.save(a.key,1,"","Bad time",3000L,3000));check(store.read(a.key).getLong("revision")==1,"Rejected edit changed notes");
  byte[] image=new byte[]{1,2,3,4,5};JSONObject withImage=store.addImage(a.key,1,"白板上的计划 <script>alert(1)</script>",2000L,3000,"公开白板.png","png",new ByteArrayInputStream(image),p->{});JSONObject picture=withImage.getJSONArray("entries").getJSONObject(1),info=picture.getJSONObject("image");String imageId=picture.getString("id");check(Arrays.equals(image,Files.readAllBytes(store.verifiedImage(a.key,info))),"Original image changed");
  rejects(()->store.addImage(a.key,2,"",null,3000,"bad.png","png",new ByteArrayInputStream(new byte[0]),p->{}));rejects(()->store.addImage(a.key,2,"",null,3000,"bad.png","png",new ByteArrayInputStream(image),p->{throw new IOException("Invalid raster");}));check(store.read(a.key).getLong("revision")==2,"Rejected image changed metadata");
  JSONObject manual=store.save(a.key,2,id,"更新的人工补充",null,3000);check(manual.getJSONArray("entries").getJSONObject(0).isNull("atMs"),"Cannot remove time association");
  ExportContents.Source export=new ExportContents.Source(a.key,"公开笔记", "fixture",null,null,null,new JSONArray(),new JSONArray(),manual);check(export.info().getJSONObject("available").getBoolean("notes"),"Notes require a transcript");String binding=export.info().getString("binding");check(export.select(new JSONArray().put("notes")).get(0).text.contains("更新的人工补充"),"Notes absent in ordinary text export");
  ByteArrayOutputStream bundle=new ByteArrayOutputStream();store.bundle(a.key,manual,"公开 <>&\" 标题",RecordingNotes.text(manual),bundle);Set<String> names=new HashSet<>();String html="";int images=0;try(ZipInputStream zip=new ZipInputStream(new ByteArrayInputStream(bundle.toByteArray()))){ZipEntry e;while((e=zip.getNextEntry())!=null){names.add(e.getName());ByteArrayOutputStream data=new ByteArrayOutputStream();byte[] buffer=new byte[1024];int n;while((n=zip.read(buffer))!=-1)data.write(buffer,0,n);if(e.getName().startsWith("images/")){images++;check(Arrays.equals(data.toByteArray(),image),"ZIP changed original image");}if(e.getName().endsWith(".html"))html=new String(data.toByteArray(),"UTF-8");}}
  check(images==1&&names.contains("备注来源.json")&&html.contains("&lt;script&gt;")&&!html.contains("<script>"),"Portable bundle missing content or HTML escaping");
  ByteArrayOutputStream backup=new ByteArrayOutputStream();LibraryBackup.write(backup,rec,meet,null);Path restored=root.resolve("restored");LibraryBackup.restore(new ByteArrayInputStream(backup.toByteArray()),restored);RecordingNotes restoredStore=new RecordingNotes(restored.resolve("meetings"),p->{});check(restoredStore.read(a.key).toString().equals(manual.toString()),"Backup changed notes");check(Arrays.equals(image,Files.readAllBytes(restoredStore.verifiedImage(a.key,info))),"Backup lost original image");
  JSONObject removed=store.remove(a.key,3,imageId);check(removed.getJSONArray("entries").length()==1,"Remove note failed");check(!binding.equals(new ExportContents.Source(a.key,"公开笔记","fixture",null,null,null,new JSONArray(),new JSONArray(),removed).info().getString("binding")),"Export accepted stale notes");
  Path damaged=meet.resolve(AiMaterialStore.hash(a.key)+".context.json");byte[] bytes=Files.readAllBytes(damaged);bytes[bytes.length/2]^=1;Files.write(damaged,bytes);rejects(()->store.save(a.key,4,"","Must not replace damaged data",null,3000));check(Arrays.equals(bytes,Files.readAllBytes(damaged)),"Damaged notes overwritten");
  // Use the intact restored library to check ordinary trash/restore and exact permanent cleanup,
  // including an image whose entry had previously been removed.
  Files.copy(restored.resolve("meetings").resolve(damaged.getFileName()),damaged,StandardCopyOption.REPLACE_EXISTING);store.remove(a.key,3,imageId);
  store.save(b.key,0,"","Another recording",null,3000);byte[] otherNotes=Files.readAllBytes(meet.resolve(AiMaterialStore.hash(b.key)+".context.json"));
  LocalRecordingLifecycle life=new LocalRecordingLifecycle(root,rec,meet,p->{});life.change(a.key,0,"trash","公开笔记");life.change(a.key,1,"restore",null);check(store.read(a.key).getJSONArray("entries").length()==1,"Restore lost notes");life.change(a.key,2,"trash","公开笔记");JSONObject offer=life.preparePurge(a.key,3);life.purge(a.key,3,offer.getString("token"));check(!Files.exists(store.imagePath(a.key,info))&&!Files.exists(damaged),"Permanent purge left recording-owned notes/image");check(Arrays.equals(otherOriginal,Files.readAllBytes(b.original))&&Arrays.equals(otherNotes,Files.readAllBytes(meet.resolve(AiMaterialStore.hash(b.key)+".context.json"))),"Purge touched another recording");
  System.out.println("PASS recording context: optimistic revision, source time bounds, original image, invalid image rollback, independent text/export binding, escaped portable bundle, actual backup restore, corrupt metadata preservation and exact purge with other-source protection. JVM fixtures; raster/native phone not claimed.");
 }
}
