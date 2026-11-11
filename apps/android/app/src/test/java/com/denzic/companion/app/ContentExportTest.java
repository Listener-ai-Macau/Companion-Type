package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import org.json.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.io.*;

public final class ContentExportTest {
    interface Work{void run()throws Exception;}
    static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    static void rejects(Work action)throws Exception{try{action.run();}catch(IOException expected){return;}throw new AssertionError("Expected rejection");}
    public static void main(String[] args)throws Exception{
        Path root=Paths.get(args[0]);Files.createDirectories(root);MeetingStore store=new MeetingStore(root.resolve("meetings"));String original="# 原话不是标题\n- 原话不是项目\n```text\n原话 & <标签> 😀\n`````";
        MeetingStore.Snapshot meeting=store.save("public",0,original,"独立补充",Arrays.asList(new MeetingStore.Task("a","核对事项","小王","下周一",false)));
        MeetingStore.Minutes minutes=store.saveMinutes("public",meeting.revision,0,original,new JSONObject().put("markdown","## 讨论结论\n- 核对接口").put("manualReview",new JSONObject()).put("processing",new JSONObject().put("complete",false)).toString());
        TranslationStore.Entry translation=new TranslationStore.Entry("public","en","older source",meeting.revision,"# literal translation\nEnglish & <quote>");
        ExportContents.Source source=new ExportContents.Source("public","公开录音","library-original",meeting,minutes,translation,new JSONArray());JSONObject info=source.info();check(info.getBoolean("minutesDraft")&&info.getBoolean("minutesManual")&&info.getBoolean("translationStale"),"draft/manual/stale flags");
        List<MeetingDocumentSections.Section> sections=source.select(new JSONArray().put("transcript").put("translation").put("notes"));String plain=MeetingDocumentSections.plain(sections),md=MeetingDocumentSections.markdown(sections);
        check(plain.contains(original)&&plain.contains(translation.text)&&plain.contains("小王")&&plain.contains("下周一"),"all selected literal source preserved");check(!plain.contains("核对接口"),"unselected minutes excluded");check(md.contains("``````text\n"+original+"\n``````"),"literal Markdown uses collision-safe fence");check(plain.contains("较早"),"stale translation notice retained");
        rejects(()->source.select(new JSONArray().put("other")));rejects(()->source.select(new JSONArray().put("transcript").put("transcript")));rejects(()->source.select(new JSONArray()));
        ExportContents.Source later=new ExportContents.Source("public","重命名","library-original",meeting,minutes,translation,new JSONArray());check(!later.info().getString("binding").equals(info.getString("binding")),"rename invalidates stale preparation");
        ExportContents.Source other=new ExportContents.Source("public","公开录音","another-library",meeting,minutes,translation,new JSONArray());check(!other.info().getString("binding").equals(info.getString("binding")),"library binding");
        Path wav=root.resolve("source.wav");Files.write(wav,"public timing source".getBytes(StandardCharsets.UTF_8));MeetingStore.Snapshot timed=store.save("timed",0,"第一段\n第二段","",Collections.emptyList());store.saveTranscriptTiming("timed",timed.transcript,wav,2100,Arrays.asList(new MeetingStore.TranscriptWindow("第一段",0,1000),new MeetingStore.TranscriptWindow("第二段",1100,2100)));
        String srt=ExportContents.srt(store.loadTranscriptTiming("timed",wav));check(srt.contains("00:00:01,100 --> 00:00:02,100")&&srt.endsWith("第二段\n\n"),"real saved segment times retained");store.saveTranscriptCorrection("timed",timed.revision,"修改后的转写");rejects(()->ExportContents.srt(store.loadTranscriptTiming("timed",wav)));
        PreparedExports exports=new PreparedExports(root.resolve("cache"));JSONObject meta=new JSONObject().put("key","public").put("title","公开录音").put("libraryToken","library-original").put("warnings",new JSONArray());
        PreparedExports.Entry fixed=exports.create(meta,"公开-原文.txt","text/plain",plain,out->out.write(plain.getBytes(StandardCharsets.UTF_8)));String id=fixed.id();check(new String(Files.readAllBytes(fixed.file),StandardCharsets.UTF_8).equals(plain),"prepared snapshot content exact");
        PreparedExports.Entry reopened=new PreparedExports(root.resolve("cache")).load(id,true);check(exports.copyText(reopened).equals(plain),"copy same prepared text after process/repository reopen");rejects(()->exports.requireLibrary(reopened,"another-library"));ByteArrayOutputStream saved=new ByteArrayOutputStream();exports.write(reopened,saved);check(Arrays.equals(saved.toByteArray(),plain.getBytes(StandardCharsets.UTF_8)),"save fixed bytes");
        rejects(()->exports.load("../meetings",true));rejects(()->exports.load(UUID.randomUUID().toString(),true));byte[] content=Files.readAllBytes(fixed.file);Files.write(fixed.file,new byte[content.length]);rejects(()->exports.load(id,true));Files.write(fixed.file,content);check(exports.load(id,true).dto().getBoolean("copyAllowed"),"tamper rejected; exact known version reusable");
        char[] largeChars=new char[PreparedExports.COPY_LIMIT+1];Arrays.fill(largeChars,'A');String large=new String(largeChars);PreparedExports.Entry largeFile=exports.create(meta,"large.txt","text/plain",large,out->out.write(large.getBytes(StandardCharsets.UTF_8)));check(!largeFile.dto().getBoolean("copyAllowed"),"large clipboard disabled but file available");rejects(()->exports.copyText(largeFile));
        check(DocumentRecovery.isPickerFormat("prepared")&&DocumentRecovery.isPickerFormat("audioZip"),"new/old picker recovery formats retained");
        String one="11111111-1111-4111-8111-111111111111",two="22222222-2222-4222-8222-222222222222";
        JSONObject reference=new JSONObject().put("id","33333333-3333-4333-8333-333333333333").put("kind","transcript").put("name","会议转写").put("quote",original).put("sourceSha256",MinutesTemplateLibrary.hash(original.getBytes(StandardCharsets.UTF_8)));
        JSONObject first=new JSONObject().put("id",one).put("text","- [x] 阅读资料\n- [ ] 预算 FALSE 0 待核对").put("kind","followup").put("atMs",JSONObject.NULL).put("createdAt",1).put("updatedAt",2).put("references",new JSONArray().put(reference));
        JSONObject second=new JSONObject().put("id",two).put("text","其它个人备注不得随本张清单导出").put("atMs",JSONObject.NULL).put("createdAt",1).put("updatedAt",1).put("image",new JSONObject().put("name","其它备注的原图.png"));
        JSONObject notes=new JSONObject().put("schema",1).put("key","public").put("revision",4).put("entries",new JSONArray().put(first).put(second));
        String untouched=notes.toString();ExportContents.Source selectedNote=new ExportContents.Source("public","公开录音","library-original",meeting,minutes,translation,new JSONArray(),new JSONArray(),notes);
        JSONObject noteInfo=selectedNote.info();check(noteInfo.getJSONArray("manualNotes").length()==2,"all individually selectable notes described");
        JSONArray justOne=new JSONArray().put("note:"+one);String chosen=MeetingDocumentSections.plain(selectedNote.select(justOne));
        check(chosen.contains(first.getString("text"))&&chosen.contains(original)&&chosen.contains("人工跟进")&&chosen.contains("不是"),"selected text, checked marker, literal evidence and human authorship retained");
        check(!chosen.contains(second.getString("text"))&&!chosen.contains("其它备注的原图.png")&&!chosen.contains("独立补充")&&!chosen.contains("下周一"),"neither other note/image nor legacy whole-meeting supplement leaks");
        JSONObject filtered=selectedNote.notesForBundle(justOne);check(filtered.getJSONArray("entries").length()==1&&filtered.getJSONArray("entries").getJSONObject(0).getString("id").equals(one),"bundle consumes exactly selected note entries");
        check(notes.toString().equals(untouched),"selection does not mutate original snapshot");
        rejects(()->selectedNote.select(new JSONArray().put("note:"+one).put("note:"+one)));rejects(()->selectedNote.select(new JSONArray().put("note:foreign")));
        rejects(()->selectedNote.select(new JSONArray().put("notes").put("note:"+one)));
        check(MeetingDocumentSections.plain(selectedNote.select(new JSONArray().put("notes"))).contains(second.getString("text")),"explicit all-notes legacy selection still works");
        JSONObject changed=new JSONObject(notes.toString());changed.getJSONArray("entries").getJSONObject(0).put("text","修订后的个人清单");
        ExportContents.Source changedNote=new ExportContents.Source("public","公开录音","library-original",meeting,minutes,translation,new JSONArray(),new JSONArray(),changed);
        check(!changedNote.info().getString("binding").equals(noteInfo.getString("binding")),"a note revision invalidates prepared selection");
        char[] previewChars=new char[3000];Arrays.fill(previewChars,'人');String longPreview=new String(previewChars)+"😀 完整依据尾句";
        PreparedExports.Entry visible=exports.create(meta,"preview.txt","text/plain",longPreview,out->out.write(longPreview.getBytes(StandardCharsets.UTF_8)));
        check(visible.dto().getString("preview").equals(longPreview)&&visible.dto().getBoolean("previewComplete"),"single note has complete preview past former350-character snippet");
        char[] boundary=new char[63999];Arrays.fill(boundary,'A');String withEmoji=new String(boundary)+"😀尾句";
        PreparedExports.Entry bounded=exports.create(meta,"bounded.txt","text/plain",withEmoji,out->out.write(withEmoji.getBytes(StandardCharsets.UTF_8)));JSONObject boundedDto=bounded.dto();String snippet=boundedDto.getString("preview");
        check(!boundedDto.getBoolean("previewComplete")&&snippet.length()==63999&&!Character.isHighSurrogate(snippet.charAt(snippet.length()-1)),"large preview is labelled partial and never splits emoji");
        check(exports.copyText(bounded).equals(withEmoji),"preview budget does not truncate exported/copied full text");
        System.out.println("PASS content exports: actual store/revisions; exact literal sections; unselected exclusion; stale/draft/manual flags; fence collision; SRT persisted time and corrected-source rejection; immutable files; clipboard budget; cross-library/tamper/path guard; recovery. No model calls.");
    }
}
