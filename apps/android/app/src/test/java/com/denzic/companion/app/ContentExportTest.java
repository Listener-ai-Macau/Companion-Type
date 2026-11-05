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
        System.out.println("PASS content exports: actual store/revisions; exact literal sections; unselected exclusion; stale/draft/manual flags; fence collision; SRT persisted time and corrected-source rejection; immutable files; clipboard budget; cross-library/tamper/path guard; recovery. No model calls.");
    }
}
