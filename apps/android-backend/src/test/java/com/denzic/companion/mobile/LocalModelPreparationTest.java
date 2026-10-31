package com.denzic.companion.mobile;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URL;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicInteger;

/** Real local HTTP and files, with small synthetic model assets. */
public final class LocalModelPreparationTest {
    private interface Checked {void run()throws Exception;}
    private static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    private static void expectFailure(Checked action)throws Exception {try{action.run();throw new AssertionError("unexpected success");}catch(IOException expected){}}
    private static String sha(byte[] bytes)throws Exception {StringBuilder out=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
    private static final class Server implements AutoCloseable {
        final byte[] model,tokens;final HttpServer server;final AtomicInteger requests=new AtomicInteger(),ranges=new AtomicInteger();
        volatile boolean cutOnce,ignoreRange,badRange,badContent,range416;
        Server(byte[] model,byte[] tokens)throws Exception {
            this.model=model;this.tokens=tokens;server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
            server.createContext("/",this::handle);server.start();
        }
        URL url()throws Exception{return new URL("http://127.0.0.1:"+server.getAddress().getPort()+"/");}
        void handle(HttpExchange request)throws IOException {
            requests.incrementAndGet();byte[] source=request.getRequestURI().getPath().endsWith("model.int8.onnx")?model:tokens;
            byte[] data=source;if(badContent&&source==model){data=source.clone();data[0]^=1;}
            String range=request.getRequestHeaders().getFirst("Range");int offset=0,status=200;
            if(range!=null){
                ranges.incrementAndGet();offset=Integer.parseInt(range.substring("bytes=".length(),range.length()-1));
                if(range416){range416=false;request.sendResponseHeaders(416,-1);request.close();return;}
                if(ignoreRange)offset=0;
                else {status=206;request.getResponseHeaders().set("Content-Range","bytes "+(badRange?offset+1:offset)+"-"+(data.length-1)+"/"+data.length);}
            }
            request.sendResponseHeaders(status,data.length-offset);
            try {
                if(cutOnce&&source==model&&range==null){cutOnce=false;request.getResponseBody().write(data,0,data.length/3);}
                else request.getResponseBody().write(data,offset,data.length-offset);
            } catch(IOException ignored) { /* the client may close after rejecting a range */ }
            finally{try{request.close();}catch(Exception ignored){}}
        }
        @Override public void close(){server.stop(0);}
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);Files.createDirectories(root);byte[] model=new byte[250_000],tokens=new byte[4096];
        for(int i=0;i<model.length;i++)model[i]=(byte)(i*31+7);for(int i=0;i<tokens.length;i++)tokens[i]=(byte)(i*17+2);
        LocalModelPreparation.Asset[] assets={new LocalModelPreparation.Asset("model.int8.onnx",model.length,sha(model)),new LocalModelPreparation.Asset("tokens.txt",tokens.length,sha(tokens))};
        String folder="sherpa-onnx-sense-voice-2024-07-17";
        try(Server server=new Server(model,tokens)) {
            Path normal=root.resolve("normal");long[] last={-1,-1};
            LocalModelPreparation.prepare(normal,server.url(),assets,(done,total)->{last[0]=done;last[1]=total;});
            Path dir=normal.resolve(folder);check(Arrays.equals(Files.readAllBytes(dir.resolve("model.int8.onnx")),model),"model bytes differ");
            check(Arrays.equals(Files.readAllBytes(dir.resolve("tokens.txt")),tokens)&&Files.isRegularFile(dir.resolve("ready")),"tokens or readiness missing");
            check(last[0]==model.length+tokens.length&&last[0]==last[1],"progress did not reach the total");
            int calls=server.requests.get();LocalModelPreparation.prepare(normal,server.url(),assets,null);check(server.requests.get()==calls,"verified model should not be downloaded again");

            Path resume=root.resolve("resume");server.cutOnce=true;expectFailure(()->LocalModelPreparation.prepare(resume,server.url(),assets,null));
            Path partial=resume.resolve(folder).resolve(".model.int8.onnx.partial");long partialLength=Files.size(partial);
            check(partialLength>0&&partialLength<model.length&&!Files.exists(resume.resolve(folder).resolve("ready")),"interrupted partial was not retained safely");
            int oldRanges=server.ranges.get();LocalModelPreparation.prepare(resume,server.url(),assets,null);
            check(server.ranges.get()>oldRanges&&Arrays.equals(Files.readAllBytes(resume.resolve(folder).resolve("model.int8.onnx")),model),"range resume failed");

            Path ignored=root.resolve("range-ignored");Files.createDirectories(ignored.resolve(folder));
            Files.write(ignored.resolve(folder).resolve(".model.int8.onnx.partial"),Arrays.copyOf(model,12000));server.ignoreRange=true;
            LocalModelPreparation.prepare(ignored,server.url(),assets,null);server.ignoreRange=false;
            check(Arrays.equals(Files.readAllBytes(ignored.resolve(folder).resolve("model.int8.onnx")),model),"full response was appended to an old partial");

            Path invalid=root.resolve("invalid-range");Files.createDirectories(invalid.resolve(folder));Path invalidPart=invalid.resolve(folder).resolve(".model.int8.onnx.partial");
            Files.write(invalidPart,Arrays.copyOf(model,9000));server.badRange=true;expectFailure(()->LocalModelPreparation.prepare(invalid,server.url(),assets,null));server.badRange=false;
            check(Files.size(invalidPart)==9000&&!Files.exists(invalid.resolve(folder).resolve("ready")),"bad range changed the partial or published readiness");
            LocalModelPreparation.prepare(invalid,server.url(),assets,null);

            Path corrupt=root.resolve("bad-content");Files.createDirectories(corrupt.resolve(folder));byte[] old="existing model".getBytes(StandardCharsets.UTF_8);Path oldModel=corrupt.resolve(folder).resolve("model.int8.onnx");Files.write(oldModel,old);Files.writeString(corrupt.resolve(folder).resolve("ready"),"stale");server.badContent=true;
            expectFailure(()->LocalModelPreparation.prepare(corrupt,server.url(),assets,null));server.badContent=false;
            check(Arrays.equals(Files.readAllBytes(oldModel),old)&&!Files.exists(corrupt.resolve(folder).resolve("ready")),"bad download replaced existing model");
            LocalModelPreparation.prepare(corrupt,server.url(),assets,null);check(Arrays.equals(Files.readAllBytes(oldModel),model),"retry after hash failure did not recover");

            Path rejected=root.resolve("range-416");Files.createDirectories(rejected.resolve(folder));Files.write(rejected.resolve(folder).resolve(".model.int8.onnx.partial"),Arrays.copyOf(model,8000));server.range416=true;
            LocalModelPreparation.prepare(rejected,server.url(),assets,null);check(Arrays.equals(Files.readAllBytes(rejected.resolve(folder).resolve("model.int8.onnx")),model),"range 416 did not restart safely");

            Path locked=root.resolve("locked");Files.createDirectories(locked);
            try(FileChannel channel=FileChannel.open(locked.resolve(".sensevoice-prepare.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);FileLock lock=channel.lock()) {
                expectFailure(()->LocalModelPreparation.prepare(locked,server.url(),assets,null));
            }
            Path interrupted=root.resolve("interrupted");Thread.currentThread().interrupt();
            try{expectFailure(()->LocalModelPreparation.prepare(interrupted,server.url(),assets,null));}finally{Thread.interrupted();}
            check(!Files.exists(interrupted.resolve(folder).resolve("ready")),"interrupted preparation published readiness");
        }
        System.out.println("PASS local model: prepare, resume, HTTP fallback, bad ranges, hash failure and interruption");
    }
}
