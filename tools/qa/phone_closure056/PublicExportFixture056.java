package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;
/** Explicit synthetic text/export fixture. Never uploaded to the recorder,
 * played, scored as ASR, or represented as a real meeting. */
public final class PublicExportFixture056 {
    static String hash(String s)throws Exception{StringBuilder b=new StringBuilder();for(byte v:MessageDigest.getInstance("SHA-256").digest(s.getBytes("UTF-8")))b.append(String.format(Locale.ROOT,"%02x",v&255));return b.toString();}
    public static void main(String[] args)throws Exception{
        Path out=Paths.get(args[0]),root=out.resolve("source"),recordings=root.resolve("recordings"),meetings=root.resolve("meetings"),control=root.resolve("control");Files.createDirectories(recordings);Files.createDirectories(meetings);Files.createDirectories(control);
        String key=FixtureRecording056.create(out,recordings);
        String title="公开虚构导出验收056 · 非真实会议",transcript="【公开虚构的导出验收文字，不是录音转写或真实会议】\n小陈在11月8日前核对报价，追加20%的费用尚未批准。\n小林负责整理交付清单，收到书面确认后再安排付款。\n原样符号：# literal **keep** <A&B> 😀\n=HYPERLINK(\"https://example.invalid\",\"literal only\")";
        String notes="公开虚构补充：这份资料只验证选择、保存、复制与分享。不要把未批准的预算写成已批准。";
        String markdown="# 公开虚构导出验收\n\n本页是人工编写的公开测试资料，未调用AI，也不代表真实会议。\n\n## 结论\n- 追加20%的费用尚未批准。\n- 付款以书面确认作为前提。\n\n## 行动事项\n- 小陈：11月8日前核对报价。\n- 小林：整理交付清单。\n\n## 待确认\n- 是否接受新的交付日期？";
        MeetingStore store=new MeetingStore(meetings);store.save(key,0,transcript,notes,Collections.emptyList());JSONObject minutes=new JSONObject().put("markdown",markdown).put("quality","draft").put("processing",new JSONObject().put("complete",true));store.saveMinutes(key,1,0,transcript,minutes.toString());Files.write(meetings.resolve(hash(key)+".title"),title.getBytes("UTF-8"));
        String body="## 公开虚构跟进材料\n追加20%的费用尚未批准，请先取得书面确认。\n小陈在11月8日前核对报价。\n原样符号：<A&B> 😀";
        JSONObject result=new JSONObject().put("incomplete",true).put("items",new JSONArray().put(new JSONObject().put("citation",new JSONObject().put("title",title).put("quote","小陈在11月8日前核对报价，追加20%的费用尚未批准。"))));
        new AiMaterialStore(meetings).save("05600000-0000-4000-8000-000000000001",key,"公开虚构材料 · 人工编写与未完成提示","仅验证导出",body,new JSONArray(),result,true);
        try(OutputStream file=Files.newOutputStream(out.resolve("Companion-公开虚构导出验收056.zip"))){LibraryBackup.write(file,recordings,meetings,control);}
        Path restored=out.resolve("restored-check");try(InputStream in=Files.newInputStream(out.resolve("Companion-公开虚构导出验收056.zip"))){LibraryBackup.restore(in,restored);}if(!new MeetingStore(restored.resolve("meetings")).load(key).transcript.equals(transcript))throw new IOException("Fixture roundtrip failed");
        JSONObject expected=new JSONObject().put("title",title).put("key",key).put("transcript",transcript).put("notes",notes).put("markdown",markdown).put("materialBody",body).put("materialId","05600000-0000-4000-8000-000000000001").put("recordingSynthetic",true).put("realMeeting",false).put("audioPlaybackAllowedForThisFixture",false);
        Files.write(out.resolve("expected.json"),expected.toString(2).getBytes("UTF-8"));System.out.println(expected.toString());
    }
}
