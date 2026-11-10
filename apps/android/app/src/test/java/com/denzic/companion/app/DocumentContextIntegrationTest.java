package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.json.*;

public final class DocumentContextIntegrationTest {
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 interface Attempt{void run()throws Exception;}
 static void rejects(Attempt attempt)throws Exception{try{attempt.run();throw new AssertionError("Expected rejection");}catch(IOException expected){}}
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]),fixtures=Paths.get(args[1]),rec=root.resolve("recordings"),meet=root.resolve("meetings");Files.createDirectories(rec);Files.createDirectories(meet);
  ImportedAudio a=ImportedAudioIntegrationTest.create(root,rec,"document-A",false),b=ImportedAudioIntegrationTest.create(root,rec,"document-B",false);byte[] otherOriginal=Files.readAllBytes(b.original),audio=Files.readAllBytes(a.original),original=Files.readAllBytes(fixtures.resolve("material.docx"));
  DocumentContextStore store=new DocumentContextStore(meet,p->{});check(store.read(a.key).getLong("revision")==0,"Fresh context not empty");String id=UUID.randomUUID().toString();
  JSONObject added=store.add(a.key,0,id,"material.docx",new ByteArrayInputStream(original));check(added.getLong("revision")==1,"Original not committed");Path owned=store.original(a.key,1,id);check(Arrays.equals(original,Files.readAllBytes(owned)),"Original bytes changed");
  check(store.add(a.key,0,id,"material.docx",new ByteArrayInputStream(original)).getLong("revision")==1,"Lost reply retry duplicated original");
  rejects(()->store.add(a.key,0,UUID.randomUUID().toString(),"material.docx",new ByteArrayInputStream(original)));rejects(()->store.add(a.key,1,UUID.randomUUID().toString(),"script.exe",new ByteArrayInputStream(original)));rejects(()->store.add(a.key,1,UUID.randomUUID().toString(),"empty.txt",new ByteArrayInputStream(new byte[0])));rejects(()->store.chunk(a.key,1,id,1));
  JSONObject chunk=store.chunk(a.key,1,id,0);check(Arrays.equals(Base64.getDecoder().decode(chunk.getString("base64")),original),"Chunk bridge altered source");
  JSONObject extracted=new JSONObject(new String(Files.readAllBytes(fixtures.resolve("material.docx.extraction.json")),StandardCharsets.UTF_8));JSONObject wrong=new JSONObject(extracted.toString()).put("sourceSha256",String.join("",Collections.nCopies(64,"0")));rejects(()->store.saveExtraction(a.key,1,id,wrong));check(store.read(a.key).getLong("revision")==1,"Invalid extraction published");
  JSONObject saved=store.saveExtraction(a.key,1,id,extracted);check(saved.getLong("revision")==2,"Extraction not committed");check(store.extraction(a.key,2,id).toString().equals(extracted.toString()),"Extraction changed on reopen");
  JSONObject ai=store.aiDocument(a.key,id);check(ai.getString("title").startsWith("补充材料 · ")&&ai.getString("kind").equals("supplement")&&ai.getString("text").contains("不是会议录音")&&ai.getString("text").contains("附注：人工提供"),"AI source loses role or source content");
  ByteArrayOutputStream backup=new ByteArrayOutputStream();LibraryBackup.write(backup,rec,meet,null);Path restored=root.resolve("restored");LibraryBackup.restore(new ByteArrayInputStream(backup.toByteArray()),restored);DocumentContextStore restoredStore=new DocumentContextStore(restored.resolve("meetings"),p->{});check(Arrays.equals(original,Files.readAllBytes(restoredStore.original(a.key,2,id))),"Backup lost original");check(restoredStore.extraction(a.key,2,id).toString().equals(extracted.toString()),"Backup lost extracted sections");
  JSONObject other=store.add(b.key,0,UUID.randomUUID().toString(),"other.txt",new ByteArrayInputStream("另场人工材料".getBytes(StandardCharsets.UTF_8)));Path otherFile=store.original(b.key,1,other.getJSONArray("rows").getJSONObject(0).getString("id"));byte[] otherDocument=Files.readAllBytes(otherFile);
  store.remove(a.key,2,id);check(Files.exists(owned),"Remove prematurely destroys original");rejects(()->store.aiDocument(a.key,id));check(Arrays.equals(audio,Files.readAllBytes(a.original)),"Document operations edited source audio");
  LocalRecordingLifecycle life=new LocalRecordingLifecycle(root,rec,meet,p->{});life.change(a.key,0,"trash","公开材料");life.change(a.key,1,"restore",null);check(store.read(a.key).getJSONArray("rows").length()==0,"Restore resurrected removed material");life.change(a.key,2,"trash","公开材料");JSONObject offer=life.preparePurge(a.key,3);life.purge(a.key,3,offer.getString("token"));check(!Files.exists(owned),"Permanent purge left removed owned document");check(Arrays.equals(otherOriginal,Files.readAllBytes(b.original))&&Arrays.equals(otherDocument,Files.readAllBytes(otherFile)),"Purge touched another recording or its document");
  System.out.println("PASS independently parsed document original/extraction storage, idempotent original retry, role-labelled AI source, stale/invalid rejection, exact backup restore, retained removed originals and scoped purge. JVM scope; phone picker not claimed.");
 }
}
