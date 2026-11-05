package com.denzic.companion.app;
import org.json.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.io.*;
import com.denzic.companion.mobile.LibraryBackup;

public final class MinutesTemplateLibraryTest {
    interface Work{void run()throws Exception;}
    static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    static void rejects(Work action)throws Exception{try{action.run();}catch(IOException expected){return;}throw new AssertionError("Expected rejection");}
    static JSONObject custom(String text)throws Exception{return new JSONObject().put("id","custom").put("name","项目复盘").put("instructions",text);}
    public static void main(String[] args)throws Exception{
        Path root=Paths.get(args[0]);Files.createDirectories(root);Path meetings=root.resolve("meetings"),recordings=root.resolve("recordings"),control=root.resolve("control");Files.createDirectories(recordings);Files.createDirectories(control);
        MinutesTemplateLibrary store=new MinutesTemplateLibrary(meetings);JSONObject empty=store.load();check(empty.getJSONArray("items").length()==0,"empty library");
        JSONObject first=store.change(empty.getString("etag"),"save",custom("突出风险和原文已明确的下一步"),null);String firstEtag=first.getString("etag");
        check(first.getJSONObject("selected").getString("name").equals("项目复盘"),"selected saved");
        JSONObject duplicate=store.change(firstEtag,"save",custom("突出风险和原文已明确的下一步"),null);check(duplicate.getJSONArray("items").length()==1,"exact duplicate deduped");
        JSONObject second=store.change(duplicate.getString("etag"),"save",custom("按客户的问题和对应回答整理"),null);check(second.getJSONArray("items").length()==2,"same-name distinct versions retained");
        rejects(()->store.change(firstEtag,"select",new JSONObject().put("id","lecture"),null));check(store.load().getJSONArray("items").length()==2,"stale save does not overwrite");
        JSONObject reopened=new MinutesTemplateLibrary(meetings).load();check(reopened.getJSONObject("selected").getString("instructions").contains("客户"),"restart persists selected custom");
        JSONObject preset=store.change(reopened.getString("etag"),"select",new JSONObject().put("id","lecture"),null);check(new MinutesTemplateLibrary(meetings).load().getJSONObject("selected").getString("id").equals("lecture"),"preset preference survives restart");
        JSONObject transcript=new JSONObject().put("id","custom").put("name","原话结构").put("instructions","保留【风险】与负责人；不补造事实");
        JSONObject request=new JSONObject().put("template",MinutesTemplateLibrary.template(transcript));check(request.getJSONObject("template").getString("instructions").equals(transcript.getString("instructions")),"request retains complete instructions");
        rejects(()->MinutesTemplateLibrary.template(new JSONObject().put("id","other")));
        rejects(()->MinutesTemplateLibrary.template(custom(" ")));
        StringBuilder longName=new StringBuilder();for(int i=0;i<86;i++)longName.append("字");
        rejects(()->MinutesTemplateLibrary.template(custom("valid").put("name",longName.toString())));
        rejects(()->store.change(preset.getString("etag"),"select",transcript,null));
        // Saved templates are carried by the existing whole-library archive without any AI credentials.
        ByteArrayOutputStream archive=new ByteArrayOutputStream();LibraryBackup.write(archive,recordings,meetings,control);
        Path restore=root.resolve("restored");LibraryBackup.restore(new ByteArrayInputStream(archive.toByteArray()),restore);
        JSONObject restored=new MinutesTemplateLibrary(restore.resolve("meetings")).load();check(restored.getJSONArray("items").length()==2&&restored.getJSONObject("selected").getString("id").equals("lecture"),"backup restore retains both versions and preference");
        String selectedKey=restored.getJSONArray("items").getJSONObject(1).getString("key");
        restored=new MinutesTemplateLibrary(restore.resolve("meetings")).change(restored.getString("etag"),"select",restored.getJSONArray("items").getJSONObject(1),null);
        JSONObject removed=new MinutesTemplateLibrary(restore.resolve("meetings")).change(restored.getString("etag"),"delete",null,selectedKey);
        check(removed.getJSONArray("items").length()==1&&removed.getJSONObject("selected").getString("id").equals("meeting"),"remove selected custom returns to meeting");
        check(store.load().getJSONArray("items").length()==2,"restore/remove never touches original library");
        Path file=meetings.resolve("minutes-templates-v1.json");byte[] original=Files.readAllBytes(file);Files.write(file,"broken".getBytes(StandardCharsets.UTF_8));byte[] bad=Files.readAllBytes(file);
        rejects(()->store.load());rejects(()->store.change("empty","save",custom("new"),null));check(Arrays.equals(bad,Files.readAllBytes(file)),"corrupt source preserved instead of overwritten");Files.write(file,original);
        check(store.load().getJSONArray("items").length()==2,"known-good version still usable");
        System.out.println("PASS templates: presets/custom UTF8 validation; immutable same-name versions; restart; dedup; stale/CAS rejection; request fields; remove isolation; real backup/restore; corrupt-file preservation. No model calls.");
    }
}
