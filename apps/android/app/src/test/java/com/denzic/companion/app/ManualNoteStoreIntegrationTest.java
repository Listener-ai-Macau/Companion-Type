package com.denzic.companion.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import org.json.*;

/** Real note/document files; directory sync and raster decoding are not phone qualification. */
public final class ManualNoteStoreIntegrationTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    interface Attempt {void run()throws Exception;}
    static void reject(Attempt operation)throws Exception{boolean failed=false;try{operation.run();}catch(Exception expected){failed=true;}check(failed,"Expected source/revision rejection");}
    static JSONObject document(DocumentContextStore store,String key,String id)throws Exception{JSONArray rows=store.read(key).getJSONArray("rows");for(int i=0;i<rows.length();i++)if(id.equals(rows.getJSONObject(i).getString("id")))return rows.getJSONObject(i);throw new IOException("Source is not in the selected recording");}
    static ManualNoteContext.Verifier verifier(DocumentContextStore store,String key){return ref->{JSONObject list=store.read(key),doc=document(store,key,ref.getString("documentId"));ManualNoteContext.verifyDocument(ref,doc,store.extraction(key,list.getLong("revision"),ref.getString("documentId")));};}
    static JSONObject entry(JSONObject notes,int index)throws Exception{return notes.getJSONArray("entries").getJSONObject(index);}
    public static void main(String[] args)throws Exception {
        Path root=Paths.get(args[2]);Files.createDirectories(root);String key="0123456789abcdef0123456789abcdef:1:1",other="abcdef0123456789abcdef0123456789:2:2";
        JSONObject fixture=new JSONObject(new String(Files.readAllBytes(Paths.get(args[0])),StandardCharsets.UTF_8)),oldDoc=fixture.getJSONObject("doc"),extracted=fixture.getJSONObject("extracted");
        DocumentContextStore documents=new DocumentContextStore(root,p->{});RecordingNotes notes=new RecordingNotes(root,p->{});
        try(ZipFile archive=new ZipFile(args[1]);InputStream original=archive.getInputStream(archive.getEntry("meetings/"+oldDoc.getString("file")))){documents.add(key,0,oldDoc.getString("id"),oldDoc.getString("name"),original);}
        JSONObject doc=document(documents,key,oldDoc.getString("id"));check(doc.getString("sourceSha256").equals(oldDoc.getString("sourceSha256")),"Only the exact public original is used");documents.saveExtraction(key,1,doc.getString("id"),extracted);doc=document(documents,key,doc.getString("id"));
        JSONObject section=documents.extraction(key,2,doc.getString("id")).getJSONArray("sections").getJSONObject(0),row=section.getJSONArray("tableRows").getJSONObject(1);
        JSONObject reference=new JSONObject().put("id",UUID.randomUUID().toString()).put("kind","document").put("name",doc.getString("name")).put("sourceSha256",doc.getString("sourceSha256")).put("documentId",doc.getString("id")).put("extractionSha256",doc.getJSONObject("extraction").getString("sha256")).put("sectionId",section.getString("id")).put("sectionLabel",section.getString("label")).put("row",row.getLong("row")).put("quote",ManualNoteContext.tableQuote(row));
        JSONArray refs=new JSONArray().put(reference);JSONObject saved=notes.saveContext(key,0,"","",null,0,"note",refs,verifier(documents,key));String noteId=entry(saved,0).getString("id");check(entry(saved,0).getString("text").isEmpty(),"Source-only note is not filled with an invented conclusion");
        Path index=root.resolve(AiMaterialStore.hash(key)+".context.json");byte[] before=Files.readAllBytes(index);
        reject(()->notes.saveContext(key,0,noteId,"stale overwrite",null,0,"followup",refs,verifier(documents,key)));check(Arrays.equals(before,Files.readAllBytes(index)),"Stale revision must not rewrite the note");
        reject(()->notes.saveContext(other,0,"","wrong owner",null,0,"note",refs,verifier(documents,other)));check(!Files.exists(root.resolve(AiMaterialStore.hash(other)+".context.json")),"Foreign recording source must not create a note");
        JSONObject forged=new JSONObject(reference.toString()).put("quote","预算已经批准");reject(()->notes.saveContext(key,1,noteId,"invented evidence",null,0,"followup",new JSONArray().put(forged),verifier(documents,key)));check(Arrays.equals(before,Files.readAllBytes(index)),"Invalid evidence must leave exact original metadata bytes");
        byte[] rasterFixture=new byte[]{1,2,3,4};JSONObject imageSaved=notes.addImageContext(key,1,"- [ ] 核对预算，负责人待确认",null,0,"public-metadata-fixture.png","png",new ByteArrayInputStream(rasterFixture),p->{},"followup",refs,verifier(documents,key));JSONObject image=entry(imageSaved,1);String imageId=image.getString("id");check(image.getString("kind").equals("followup"),"Human follow-up kind retained");check(Arrays.equals(rasterFixture,Files.readAllBytes(notes.verifiedImage(key,image.getJSONObject("image")))),"Adding citations must not change the image bytes");
        JSONObject edited=notes.save(key,2,imageId,"- [x] 我已核对，仍不是会议决定",null,0);check(entry(edited,1).getString("kind").equals("followup")&&ManualNoteContext.same(entry(edited,1).getJSONArray("references").getJSONObject(0),reference),"Legacy text edits preserve existing context and image");
        check(RecordingNotes.text(edited).contains(reference.getString("quote"))&&RecordingNotes.text(edited).contains("人工跟进"),"Text export preserves literal references and explicit human kind");
        check(RecordingNotes.searchableText(edited).contains(reference.getString("quote")),"Saved citations remain searchable");
        ByteArrayOutputStream bundle=new ByteArrayOutputStream();notes.bundle(key,edited,"公开资料","原纪要保持",bundle);boolean htmlFound=false,jsonFound=false;try(ZipInputStream zip=new ZipInputStream(new ByteArrayInputStream(bundle.toByteArray()),StandardCharsets.UTF_8)){ZipEntry item;while((item=zip.getNextEntry())!=null){ByteArrayOutputStream body=new ByteArrayOutputStream();byte[] buffer=new byte[4096];int n;while((n=zip.read(buffer))!=-1)body.write(buffer,0,n);String content=new String(body.toByteArray(),StandardCharsets.UTF_8);if(item.getName().endsWith(".html"))htmlFound=content.contains("人工引用")&&content.contains("FALSE")&&content.contains("12,000.00");if(item.getName().equals("备注来源.json"))jsonFound=new JSONObject(content).getJSONArray("entries").getJSONObject(1).getString("kind").equals("followup");}}
        check(htmlFound&&jsonFound,"Portable bundle includes human evidence without pretending it is a new meeting decision");
        documents.remove(key,2,reference.getString("documentId"));JSONObject retained=notes.save(key,3,noteId,"来源入口移除后，我仍能编辑自己的便签。",null,0);check(ManualNoteContext.same(entry(retained,0).getJSONArray("references").getJSONObject(0),reference),"Removing a source does not erase saved evidence");reject(()->verifier(documents,key).verify(reference));
        before=Files.readAllBytes(index);reject(()->notes.saveContext(key,4,"","new quote from missing source",null,0,"note",refs,verifier(documents,key)));check(Arrays.equals(before,Files.readAllBytes(index)),"A new unresolvable citation must not advance metadata");
        Path restored=Paths.get(args[3]);Files.createDirectories(restored);try(java.util.stream.Stream<Path> files=Files.list(root)){for(Path file:(Iterable<Path>)files::iterator)if(Files.isRegularFile(file))Files.copy(file,restored.resolve(file.getFileName()));}
        JSONObject reopened=new RecordingNotes(restored,p->{}).read(key);check(ManualNoteContext.same(entry(reopened,0).getJSONArray("references").getJSONObject(0),reference),"References are portable without absolute paths or a library token");check(!reopened.toString().contains("libraryToken"),"No ephemeral token is persisted");
        System.out.println("PASS real public original/cache to durable human citations, exact rejection bytes, foreign-record refusal, image/context preservation, legacy edits, missing-source retention and new-root reopen. Not phone/backup/raster qualification.");
    }
}
