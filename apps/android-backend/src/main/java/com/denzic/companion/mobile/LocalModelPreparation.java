package com.denzic.companion.mobile;

import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** User-initiated preparation of the pinned local transcription model. */
public final class LocalModelPreparation {
    private LocalModelPreparation() {}
    private static final String DIRECTORY="sherpa-onnx-sense-voice-2024-07-17";
    private static final String BASE="https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/2365baeacb507f821a0c8120fcee3d484dba7a07/";
    private static final Asset[] ASSETS={
        new Asset("model.int8.onnx",239_233_841L,"c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51"),
        new Asset("tokens.txt",315_894L,"f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc")
    };
    private static final Pattern CONTENT_RANGE=Pattern.compile("bytes (\\d+)-(\\d+)/(\\d+)");

    /** Runs on the calling worker thread; totals cover both pinned files. */
    public interface Progress {void onProgress(long downloadedBytes,long totalBytes);}
    static final class Asset {
        final String name,sha256;final long size;
        Asset(String name,long size,String sha256){
            if(name==null||name.contains("/")||name.contains("\\")||name.equals(".")||name.equals("..")||size<=0||sha256==null||!sha256.matches("[0-9a-f]{64}"))
                throw new IllegalArgumentException("invalid model asset");
            this.name=name;this.size=size;this.sha256=sha256;
        }
    }
    private static MessageDigest digest(){try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}}
    private static String hex(byte[] bytes){StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
    private static void interrupted()throws InterruptedIOException {if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("model preparation interrupted; retry to continue");}
    private static boolean verified(Path path,Asset asset)throws IOException {
        if(!Files.isRegularFile(path)||Files.size(path)!=asset.size)return false;
        MessageDigest hash=digest();byte[] buffer=new byte[64*1024];
        try(InputStream in=Files.newInputStream(path)){int n;while((n=in.read(buffer))!=-1){interrupted();hash.update(buffer,0,n);}}
        return hex(hash.digest()).equals(asset.sha256);
    }
    /** Verifies the local files without downloading; call on a worker thread. */
    public static boolean isPrepared(Path modelRoot)throws IOException {
        if(modelRoot==null)throw new IllegalArgumentException("model directory required");
        Path dir=modelRoot.resolve(DIRECTORY);
        return Files.isRegularFile(dir.resolve("ready"))&&verified(dir.resolve(ASSETS[0].name),ASSETS[0])&&verified(dir.resolve(ASSETS[1].name),ASSETS[1]);
    }
    /**
     * Explicitly download the public model on a worker thread. No audio is sent.
     * An interrupted partial download is reused on the next call when supported.
     */
    public static void prepare(Path modelRoot,Progress progress)throws IOException {
        prepare(modelRoot,new URL(BASE),ASSETS,progress);
    }
    // Package-private seam lets local tests exercise the real HTTP/file path.
    static void prepare(Path modelRoot,URL base,Asset[] assets,Progress progress)throws IOException {
        if(modelRoot==null||base==null||assets==null||assets.length!=2)throw new IllegalArgumentException("model directory and assets required");
        Files.createDirectories(modelRoot);Path dir=modelRoot.resolve(DIRECTORY);Files.createDirectories(dir);
        long total;
        try{total=Math.addExact(assets[0].size,assets[1].size);}catch(ArithmeticException error){throw new IOException("model size is invalid",error);}
        try(FileChannel channel=FileChannel.open(modelRoot.resolve(".sensevoice-prepare.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE)) {
            FileLock lock;try{lock=channel.tryLock();}catch(OverlappingFileLockException error){throw new IOException("model preparation is already running",error);}
            if(lock==null)throw new IOException("model preparation is already running");
            try {
                long completed=0;
                for(Asset asset:assets){
                    interrupted();Path destination=dir.resolve(asset.name),partial=dir.resolve("."+asset.name+".partial");
                    if(!verified(destination,asset)) {
                        // A stale marker must not make an incomplete model selectable.
                        Files.deleteIfExists(dir.resolve("ready"));
                        if(Files.exists(partial)&&Files.size(partial)>asset.size)Files.delete(partial);
                        if(Files.exists(partial)&&Files.size(partial)==asset.size&&!verified(partial,asset))Files.delete(partial);
                        if(!verified(partial,asset))download(new URL(base,asset.name+"?download=true"),partial,asset,completed,total,progress);
                        if(!verified(partial,asset))throw new IOException("downloaded model failed verification; retry preparation");
                        Files.move(partial,destination,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                    } else Files.deleteIfExists(partial);
                    completed+=asset.size;if(progress!=null)progress.onProgress(completed,total);
                }
                // Publish readiness only after both files have been verified.
                Path marker=dir.resolve(".ready-"+UUID.randomUUID()+".tmp");
                try{
                    try(FileOutputStream out=new FileOutputStream(marker.toFile())){out.write(assets[0].sha256.getBytes(StandardCharsets.US_ASCII));out.getFD().sync();}
                    Files.move(marker,dir.resolve("ready"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                }
                finally{Files.deleteIfExists(marker);}
            } finally {lock.release();}
        }
    }
    private static void download(URL url,Path partial,Asset asset,long completed,long total,Progress progress)throws IOException {
        for(int attempt=0;attempt<2;attempt++) {
            interrupted();long offset=Files.exists(partial)?Files.size(partial):0;
            HttpURLConnection connection=(HttpURLConnection)url.openConnection();
            connection.setConnectTimeout(15_000);connection.setReadTimeout(60_000);connection.setInstanceFollowRedirects(true);
            connection.setRequestProperty("Accept-Encoding","identity");
            if(offset>0)connection.setRequestProperty("Range","bytes="+offset+"-");
            try {
                int status=connection.getResponseCode();
                if(status==416&&offset>0&&attempt==0){Files.deleteIfExists(partial);continue;}
                if(status==200){offset=0;}
                else if(status==206){
                    String header=connection.getHeaderField("Content-Range");Matcher match=CONTENT_RANGE.matcher(header==null?"":header);
                    if(!match.matches())throw new IOException("invalid model download range");
                    try {
                        long start=Long.parseLong(match.group(1)),end=Long.parseLong(match.group(2)),size=Long.parseLong(match.group(3));
                        if(start!=offset||end<start||end>=asset.size||size!=asset.size)throw new IOException("invalid model download range");
                    } catch(NumberFormatException invalid){throw new IOException("invalid model download range",invalid);}
                } else throw new IOException("model download failed (HTTP "+status+")");
                try(InputStream in=connection.getInputStream();FileOutputStream out=new FileOutputStream(partial.toFile(),offset>0)) {
                    byte[] buffer=new byte[64*1024];long count=offset;int n;
                    if(progress!=null)progress.onProgress(completed+count,total);
                    while((n=in.read(buffer))!=-1){
                        interrupted();if(n>asset.size-count)throw new IOException("model download exceeded expected size");
                        out.write(buffer,0,n);count+=n;if(progress!=null)progress.onProgress(completed+count,total);
                    }
                    out.getFD().sync();
                    if(count!=asset.size)throw new IOException("model download incomplete; retry to continue");
                }
                return;
            } finally {connection.disconnect();}
        }
        throw new IOException("model download could not be resumed");
    }
}
