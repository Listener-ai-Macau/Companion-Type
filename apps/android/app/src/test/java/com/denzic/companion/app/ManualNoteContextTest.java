package com.denzic.companion.app;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.json.*;

public final class ManualNoteContextTest {
    interface Attempt {void run()throws Exception;}
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static void reject(Attempt operation)throws Exception{boolean rejected=false;try{operation.run();}catch(Exception expected){rejected=true;}check(rejected,"Invalid/stale evidence must be rejected");}
    static JSONObject copy(JSONObject source){return new JSONObject(source.toString());}
    public static void main(String[] args)throws Exception {
        JSONObject fixture=new JSONObject(new String(Files.readAllBytes(Paths.get(args[0])),StandardCharsets.UTF_8));
        JSONObject document=fixture.getJSONObject("doc"),extraction=fixture.getJSONObject("extracted"),section=extraction.getJSONArray("sections").getJSONObject(0),row=section.getJSONArray("tableRows").getJSONObject(1);
        JSONObject ref=new JSONObject().put("id",UUID.randomUUID().toString()).put("kind","document").put("name",document.getString("name")).put("sourceSha256",document.getString("sourceSha256")).put("documentId",document.getString("id")).put("extractionSha256",document.getJSONObject("extraction").getString("sha256")).put("sectionId",section.getString("id")).put("sectionLabel",section.getString("label")).put("row",row.getLong("row")).put("quote",ManualNoteContext.tableQuote(row));
        ManualNoteContext.verifyDocument(ref,document,extraction);check(ref.getString("quote").contains("FALSE")&&ref.getString("quote").contains("12,000.00"),"Real retained reader values must remain literal");
        reject(()->ManualNoteContext.verifyDocument(copy(ref).put("quote",ref.getString("quote").replace("FALSE","TRUE")),document,extraction));
        reject(()->ManualNoteContext.verifyDocument(copy(ref).put("extractionSha256",new String(new char[64]).replace('\0','0')),document,extraction));
        reject(()->ManualNoteContext.verifyDocument(copy(ref).put("documentId",UUID.randomUUID().toString()),document,extraction));
        reject(()->ManualNoteContext.validate(new JSONArray().put(copy(ref).put("row",2.5))));
        reject(()->ManualNoteContext.validate(new JSONArray().put(copy(ref).put("quote",12000))));
        reject(()->ManualNoteContext.validate(new JSONArray().put(copy(ref).put("sectionLabel",9))));
        reject(()->ManualNoteContext.validate(new JSONArray().put(ref).put(copy(ref))));
        reject(()->ManualNoteContext.validate(new JSONArray().put(copy(ref).put("path","/another-library/private-file"))));
        String previous=new JSONArray().put(ref).toString();int[] checked={0};JSONArray kept=ManualNoteContext.prepare(new JSONArray(previous),new JSONArray(previous),r->{checked[0]++;throw new Exception("Source later unavailable");});check(checked[0]==0,"An unchanged older quote remains editable even after the source changes");
        kept.getJSONObject(0).put("quote","local caller mutation");check(new JSONArray(previous).getJSONObject(0).getString("quote").equals(ref.getString("quote")),"Returned metadata is independent of the saved input");
        reject(()->ManualNoteContext.prepare(new JSONArray(previous),new JSONArray().put(copy(ref).put("quote","invented approval")),r->ManualNoteContext.verifyDocument(r,document,extraction)));
        String transcript="嗯，项目还未批准。🙂\n负责人待确认。";JSONObject speech=new JSONObject().put("id",UUID.randomUUID().toString()).put("kind","transcript").put("name","会议转写").put("sourceSha256",ManualNoteContext.hash(transcript)).put("quote","项目还未批准");ManualNoteContext.verifyTranscript(speech,transcript);
        reject(()->ManualNoteContext.verifyTranscript(speech,transcript+"\n已补充新内容。"));reject(()->ManualNoteContext.verifyTranscript(copy(speech).put("quote","项目已经批准"),transcript));
        check(ManualNoteContext.kind(new JSONObject()).equals("note"),"Old note format remains valid");check(ManualNoteContext.references(new JSONObject()).length()==0,"Old notes have no implicit references");reject(()->ManualNoteContext.kind(new JSONObject().put("kind","aiDecision")));
        System.out.println("PASS actual retained XLSX literal evidence, owner/hash/row/unknown-path rejection, unchanged stale citation preservation, defensive copies and exact transcript source binding.");
    }
}
