package com.denzic.companion.app;

import com.denzic.companion.mobile.MeetingStore;
import java.nio.file.*;
import java.util.*;
import java.io.IOException;
import java.security.MessageDigest;

public final class MeetingLibrarySearchTest {
    static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    static Map<String,String> hashes(Path root)throws Exception{
        Map<String,String> result=new TreeMap<>();
        try(java.util.stream.Stream<Path> files=Files.list(root)){
            for(Path file:(Iterable<Path>)files.filter(Files::isRegularFile)::iterator)result.put(file.getFileName().toString(),Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(file))));
        }
        return result;
    }
    public static void main(String[] args)throws Exception{
        Path root=Files.createTempDirectory(Paths.get(args[0]),"meeting-library-search-");
        MeetingStore store=new MeetingStore(root);
        MeetingStore.Snapshot first=store.save("meeting-a",0,"周五补充土豆。字面 .* [1]。😀 预算不变。İstanbul 开会。","",Collections.emptyList());
        store.save("meeting-b",0,"本周讨论文具。","",Collections.emptyList());
        MeetingLibrarySearch.Reader reader=(key,source)->"transcript".equals(source)?new MeetingLibrarySearch.SavedText(store.load(key).transcript,false):new MeetingLibrarySearch.SavedText("负责人说明：下周核对日历。",true);
        MeetingLibrarySearch.Result body=new MeetingLibrarySearch("土豆",true).find("meeting-a","运营复盘",reader);
        check(body.match!=null&&body.match.source.equals("transcript"),"body-only keyword not found");
        check(body.match.snippet.substring(body.match.start,body.match.end).equals("土豆"),"snippet offsets lost original characters");
        check(new MeetingLibrarySearch("土豆",false).find("meeting-a","运营复盘",reader).match==null,"title-only search read the body");
        check(new MeetingLibrarySearch("运营",false).find("meeting-a","运营复盘",reader).match.source.equals("title"),"title match missing");
        check(new MeetingLibrarySearch(".*",true).find("meeting-a","运营复盘",reader).match.snippet.contains(".*"),"literal query treated as pattern");
        check(new MeetingLibrarySearch("[1]",true).find("meeting-a","运营复盘",reader).match!=null,"bracket query lost");
        check(new MeetingLibrarySearch("ISTANBUL",true).find("meeting-a","运营复盘",reader).match!=null,"Unicode case matching failed");
        MeetingLibrarySearch.Result minutes=new MeetingLibrarySearch("日历",true).find("meeting-a","运营复盘",reader);
        check(minutes.match!=null&&minutes.match.source.equals("minutes")&&minutes.match.stale,"older minutes source lost its status");
        MeetingLibrarySearch.Reader damaged=(key,source)->{if(source.equals("transcript"))throw new IOException("damaged");return new MeetingLibrarySearch.SavedText("日历仍可读取",false);};
        MeetingLibrarySearch.Result partial=new MeetingLibrarySearch("日历",true).find("meeting-a","运营复盘",damaged);
        check(partial.match!=null&&partial.unreadable==1,"one unreadable component hid another match");
        check(new MeetingLibrarySearch("不存在",true).find("meeting-a","运营复盘",reader).match==null,"fabricated match");
        store.saveTranscriptCorrection("meeting-a",first.revision,"现在改为番茄，旧关键词不再存在。");
        check(new MeetingLibrarySearch("土豆",true).find("meeting-a","运营复盘",reader).match==null,"search used old recognition instead of saved correction");
        check(new MeetingLibrarySearch("番茄",true).find("meeting-a","运营复盘",reader).match!=null,"new correction missing");
        Map<String,String> before=hashes(root);
        for(String query:new String[]{"番茄","日历","无结果"})new MeetingLibrarySearch(query,true).find("meeting-a","运营复盘",reader);
        check(before.equals(hashes(root)),"search altered stored files");
        StringBuilder longText=new StringBuilder();for(int i=0;i<80;i++)longText.append("😀甲");longText.append("目标关键词");for(int i=0;i<80;i++)longText.append("乙😀");
        MeetingLibrarySearch.Reader unicode=(key,source)->new MeetingLibrarySearch.SavedText(longText.toString(),false);
        MeetingLibrarySearch.Match match=new MeetingLibrarySearch("目标关键词",true).find("x","x",unicode).match;
        check(match.snippet.substring(match.start,match.end).equals("目标关键词"),"clipped snippet lost match offsets");
        check(!Character.isLowSurrogate(match.snippet.charAt(1)),"snippet began inside an emoji");
        try{new MeetingLibrarySearch(" ",true);throw new AssertionError("empty query accepted");}catch(IllegalArgumentException expected){}
        System.out.println("PASS local title/transcript/minutes search, literal and Unicode snippets, saved corrections, partial unreadability and unchanged stored payloads");
    }
}
