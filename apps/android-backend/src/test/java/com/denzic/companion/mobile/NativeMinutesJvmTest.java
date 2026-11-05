package com.denzic.companion.mobile;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Paths;

public final class NativeMinutesJvmTest {
    public static void main(String[] args) throws Exception {
        HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/chat/completions",exchange->{
            String request=new String(exchange.getRequestBody().readAllBytes(),StandardCharsets.UTF_8);
            String content;
            if(request.contains("请综合下列全部分段结果"))
                content="{\"summary\":[\"Quote cancelled\"],\"decisions\":[\"Cancel quote\"],\"actionItems\":[],\"questions\":[],\"keywords\":[],\"markdown\":\"Combined\"}";
            else if(request.contains("第1段，共1段"))
                content="{\"summary\":[\"Send quote Friday\"],\"decisions\":[],\"actionItems\":[],\"questions\":[],\"keywords\":[],\"markdown\":\"Chapter\",\"evidence\":[{\"field\":\"summary\",\"index\":0,\"quote\":\"Send quote Friday\"}]}";
            else content="{\"summary\":[\"Test task\"],\"decisions\":[],\"actionItems\":[],\"questions\":[],\"keywords\":[],\"markdown\":\"Test task\",\"questionClassification\":[{\"sourceId\":1,\"kind\":\"statement\"}]}";
            String body="{\"choices\":[{\"finish_reason\":\"stop\",\"message\":{\"content\":\""+content.replace("\\","\\\\").replace("\"","\\\"")+"\"}}]}";
            byte[] bytes=body.getBytes(StandardCharsets.UTF_8);exchange.sendResponseHeaders(200,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
        });server.start();
        try {
            String request="{\"sessionKey\":\"synthetic\",\"title\":\"Test\",\"transcript\":\"Test task.\",\"durationMillis\":10000,\"endpoint\":\"http://127.0.0.1:"+server.getAddress().getPort()+"/chat/completions\",\"model\":\"synthetic\"}";
            String response=NativeMinutes.generate(request,"synthetic",Paths.get(args[0]));
            if(!response.contains("\"source\":\"llm_deepseek\"")||!response.contains("Test task"))throw new AssertionError("missing service-backed minutes");
            if(NativeMinutes.supplementStatus(response,java.util.Collections.emptyList())!=NativeMinutes.SupplementStatus.CURRENT)throw new AssertionError("new original-only result must record empty source");
            if(NativeMinutes.supplementStatus("{\"summary\":[]}",java.util.Collections.emptyList())!=NativeMinutes.SupplementStatus.UNKNOWN)throw new AssertionError("legacy result must remain unknown");
            String longRequest="{\"sessionKey\":\"synthetic-long\",\"title\":\"Test\",\"transcript\":\"Send quote Friday.\",\"durationMillis\":7200000,\"supplements\":[\"Cancel quote.\"],\"endpoint\":\"http://127.0.0.1:"+server.getAddress().getPort()+"/chat/completions\",\"model\":\"synthetic\"}";
            String combined=NativeMinutes.generate(longRequest,"synthetic",Paths.get(args[0]));
            if(!combined.contains("\"quality\":\"final\"")||!combined.contains("Quote cancelled")||!combined.contains("\"sourceSupplements\":[\"Cancel quote.\"]"))throw new AssertionError("long-meeting supplement not combined");
            if(NativeMinutes.supplementStatus(combined,java.util.List.of("Cancel quote."))!=NativeMinutes.SupplementStatus.CURRENT)throw new AssertionError("immutable current sources should match");
            MeetingStore store=new MeetingStore(Paths.get(args[0]).resolveSibling("minutes-source-store"));
            MeetingStore.Snapshot meeting=store.save("synthetic-long",0,"Send quote Friday.","Cancel quote.",java.util.Collections.emptyList());
            store.saveMinutes("synthetic-long",meeting.revision,0,meeting.transcript,combined);
            MeetingStore.Minutes saved=store.loadMinutes("synthetic-long");
            if(NativeMinutes.supplementStatus(saved.json,java.util.Collections.singletonList(meeting.notes))!=NativeMinutes.SupplementStatus.CURRENT)throw new AssertionError("saved source should match");
            meeting=store.save("synthetic-long",meeting.revision,meeting.transcript,"Postpone quote.",meeting.tasks);
            saved=new MeetingStore(Paths.get(args[0]).resolveSibling("minutes-source-store")).loadMinutes("synthetic-long");
            if(saved.sourceChanged||NativeMinutes.supplementStatus(saved.json,java.util.Collections.singletonList(meeting.notes))!=NativeMinutes.SupplementStatus.CHANGED)throw new AssertionError("changed notes not detected independently of transcript");
            java.nio.file.Path backupRoot=Paths.get(args[0]).resolveSibling("source-backup-proof");java.nio.file.Files.createDirectories(backupRoot);
            java.nio.file.Path recordings=java.nio.file.Files.createDirectory(backupRoot.resolve("recordings"));
            java.io.ByteArrayOutputStream archive=new java.io.ByteArrayOutputStream();
            LibraryBackup.write(archive,recordings,Paths.get(args[0]).resolveSibling("minutes-source-store"),null);
            java.nio.file.Path restored=backupRoot.resolve("restored");LibraryBackup.restore(new java.io.ByteArrayInputStream(archive.toByteArray()),restored);
            MeetingStore restoredStore=new MeetingStore(restored.resolve("meetings"));
            if(NativeMinutes.supplementStatus(restoredStore.loadMinutes("synthetic-long").json,java.util.Collections.singletonList(restoredStore.load("synthetic-long").notes))!=NativeMinutes.SupplementStatus.CHANGED)throw new AssertionError("backup lost supplement provenance");
            System.out.println("NativeMinutes JNI test passed");
        } finally {server.stop(0);}
    }
}
