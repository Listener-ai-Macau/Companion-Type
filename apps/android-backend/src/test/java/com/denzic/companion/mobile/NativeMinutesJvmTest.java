package com.denzic.companion.mobile;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Paths;

public final class NativeMinutesJvmTest {
    public static void main(String[] args) throws Exception {
        HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/chat/completions",exchange->{
            exchange.getRequestBody().transferTo(java.io.OutputStream.nullOutputStream());
            String body="{\"choices\":[{\"finish_reason\":\"stop\",\"message\":{\"content\":\"{\\\"summary\\\":[\\\"Test task\\\"],\\\"decisions\\\":[],\\\"actionItems\\\":[],\\\"questions\\\":[],\\\"keywords\\\":[],\\\"markdown\\\":\\\"Test task\\\",\\\"questionClassification\\\":[{\\\"sourceId\\\":1,\\\"kind\\\":\\\"statement\\\"}]}\"}}]}";
            byte[] bytes=body.getBytes(StandardCharsets.UTF_8);exchange.sendResponseHeaders(200,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
        });server.start();
        try {
            String request="{\"sessionKey\":\"synthetic\",\"title\":\"Test\",\"transcript\":\"Test task.\",\"durationMillis\":10000,\"endpoint\":\"http://127.0.0.1:"+server.getAddress().getPort()+"/chat/completions\",\"model\":\"synthetic\"}";
            String response=NativeMinutes.generate(request,"synthetic",Paths.get(args[0]));
            if(!response.contains("\"source\":\"llm_deepseek\"")||!response.contains("Test task"))throw new AssertionError("missing service-backed minutes");
            System.out.println("NativeMinutes JNI test passed");
        } finally {server.stop(0);}
    }
}
