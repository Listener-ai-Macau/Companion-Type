package com.denzic.companion.mobile;

import java.io.FileOutputStream;
import java.io.ByteArrayOutputStream;
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
    private static final Asset[] ASSETS={
        new Asset("model.int8.onnx",239_233_841L,"c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51"),
        new Asset("tokens.txt",315_894L,"f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc")
    };
    private static final String OFFICIAL_DIRECTORY="funasr-paraformer-large-zh-2024";
    private static final String OFFICIAL_BASE="https://huggingface.co/funasr/Paraformer-large/resolve/6843c899b177f325d4bbdad8c08d85d5b1321f00/";
    private static final String MIRROR_BASE="https://hf-mirror.com/funasr/Paraformer-large/resolve/6843c899b177f325d4bbdad8c08d85d5b1321f00/";
    private static final Asset OFFICIAL_RAW=new Asset("model_quant.onnx",237_653_364L,"0418089a74ae93556db7802cacc7ea42d9ca55902cf90dfc2c3374bc248c7414");
    private static final Asset OFFICIAL_MODEL=new Asset("model.int8.onnx",237_664_716L,"8234905d74db17f7466a1cd110ce20f57c1ff9c1fc95db0615d8931955da5c54");
    private static final Asset OFFICIAL_TOKENS=new Asset("tokens.txt",75_756L,"59aba8873a2ed1e122c25fee421e25f283b63290efbde85c1f01a853d83cb6e6");
    private static final String LEGACY_DIRECTORY="sherpa-onnx-paraformer-zh-small-2024-03-09";
    private static final Asset[] LEGACY_ASSETS={
        new Asset("model.int8.onnx",81_828_675L,"3ef6c19369b912f7caf3cef8e545c5ccd1a33d9d7ec792a46668dc41c4b229ec"),
        new Asset("tokens.txt",75_352L,"4b2d964e18b9cf139b473003b6698fb2ed9a2a5ec55b93daa677b28f578897aa")
    };
    private static final Pattern CONTENT_RANGE=Pattern.compile("bytes (\\d+)-(\\d+)/(\\d+)");

    /** Runs on the calling worker thread; totals cover the model download. */
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
    private static boolean legacyPrepared(Path root)throws IOException {
        Path dir=root.resolve(LEGACY_DIRECTORY);
        return verified(dir.resolve(LEGACY_ASSETS[0].name),LEGACY_ASSETS[0])&&verified(dir.resolve(LEGACY_ASSETS[1].name),LEGACY_ASSETS[1]);
    }
    /** Verifies an available pinned model without downloading; call on a worker thread. */
    public static boolean isPrepared(Path modelRoot)throws IOException {
        if(modelRoot==null)throw new IllegalArgumentException("model directory required");
        IOException preferredError=null;Path dir=modelRoot.resolve(DIRECTORY);
        try {
            Path official=modelRoot.resolve(OFFICIAL_DIRECTORY);
            if(Files.isRegularFile(official.resolve("ready"))&&verified(official.resolve(OFFICIAL_MODEL.name),OFFICIAL_MODEL)&&verified(official.resolve(OFFICIAL_TOKENS.name),OFFICIAL_TOKENS))return true;
        } catch(IOException error) {if(Thread.currentThread().isInterrupted())throw error;preferredError=error;}
        try {
            if(Files.isRegularFile(dir.resolve("ready"))&&verified(dir.resolve(ASSETS[0].name),ASSETS[0])&&verified(dir.resolve(ASSETS[1].name),ASSETS[1]))return true;
        } catch(IOException error) {if(Thread.currentThread().isInterrupted())throw error;if(preferredError==null)preferredError=error;else preferredError.addSuppressed(error);}
        try {if(legacyPrepared(modelRoot))return true;}
        catch(IOException error){if(preferredError==null)preferredError=error;else preferredError.addSuppressed(error);}
        if(preferredError!=null)throw preferredError;
        return false;
    }
    /**
     * Explicitly download the public model on a worker thread. No audio is sent.
     * An interrupted partial download is reused on the next call when supported.
     * If the download fails, a verified existing model can remain usable.
     */
    public static void prepare(Path modelRoot,Progress progress)throws IOException {
        try {prepareOfficial(modelRoot,new URL(OFFICIAL_BASE),new URL(MIRROR_BASE),OFFICIAL_RAW,resource("metadata.bin"),OFFICIAL_MODEL,resource("tokens.txt"),OFFICIAL_TOKENS,progress);}
        catch(IOException error) {
            if(Thread.currentThread().isInterrupted())throw error;
            try {if(modelRoot==null||!isPrepared(modelRoot))throw error;}
            catch(IOException fallbackError){if(fallbackError!=error)error.addSuppressed(fallbackError);throw error;}
        }
        preparePunctuation(modelRoot,progress);
    }
    private static void preparePunctuation(Path modelRoot,Progress progress)throws IOException {
        Asset asset=new Asset("model.onnx",294_372_519L,"e93593a6dbd69a07f8734ef269dbe861a379755f8d1c8354719432116f2c44bd");
        Path dir=modelRoot.resolve("ct-transformer-punctuation-zh-en-2024");Files.createDirectories(dir);
        try(FileChannel channel=FileChannel.open(modelRoot.resolve(".punctuation-prepare.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE)) {
            FileLock lock;try{lock=channel.tryLock();}catch(OverlappingFileLockException error){throw new IOException("model preparation is already running",error);}
            if(lock==null)throw new IOException("model preparation is already running");
            try {
                Path destination=dir.resolve(asset.name),partial=dir.resolve(".model.onnx.partial");
                if(verified(destination,asset))return;
                if(Files.exists(partial)&&Files.size(partial)>=asset.size&&!verified(partial,asset))Files.delete(partial);
                String relative="csukuangfj/sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12/resolve/432aeba669265e7aeb06b9359753419683b38597/model.onnx";
                if(!verified(partial,asset)) {
                    try {download(new URL("https://huggingface.co/"+relative),partial,asset,0,asset.size,progress);}
                    catch(IOException first){if(Thread.currentThread().isInterrupted())throw first;try{download(new URL("https://hf-mirror.com/"+relative),partial,asset,0,asset.size,progress);}catch(IOException second){second.addSuppressed(first);throw second;}}
                }
                if(!verified(partial,asset))throw new IOException("punctuation model failed verification; retry preparation");
                Files.move(partial,destination,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            } finally {lock.release();}
        }
    }
    private static byte[] resource(String name)throws IOException {
        // Absolute path stays valid if the host obfuscates this class's package.
        try(InputStream in=LocalModelPreparation.class.getResourceAsStream("/com/denzic/companion/mobile/"+name)) {
            if(in==null)throw new IOException("local model metadata is missing");
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;
            while((n=in.read(buffer))!=-1){if(out.size()+n>128*1024)throw new IOException("local model metadata is invalid");out.write(buffer,0,n);}
            return out.toByteArray();
        }
    }
    // Append only the publisher-derived ONNX metadata; model weights stay intact.
    static void prepareOfficial(Path modelRoot,URL base,Asset raw,byte[] metadata,Asset model,byte[] vocabulary,Asset tokens,Progress progress)throws IOException {
        prepareOfficial(modelRoot,base,null,raw,metadata,model,vocabulary,tokens,progress);
    }
    static void prepareOfficial(Path modelRoot,URL base,URL mirror,Asset raw,byte[] metadata,Asset model,byte[] vocabulary,Asset tokens,Progress progress)throws IOException {
        if(modelRoot==null||base==null||raw==null||metadata==null||model==null||vocabulary==null||tokens==null)throw new IllegalArgumentException("model assets required");
        Files.createDirectories(modelRoot);Path dir=modelRoot.resolve(OFFICIAL_DIRECTORY);Files.createDirectories(dir);
        try(FileChannel channel=FileChannel.open(modelRoot.resolve(".official-prepare.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE)) {
            FileLock lock;try{lock=channel.tryLock();}catch(OverlappingFileLockException error){throw new IOException("model preparation is already running",error);}
            if(lock==null)throw new IOException("model preparation is already running");
            try {
                Path destination=dir.resolve(model.name),tokenFile=dir.resolve(tokens.name);
                if(Files.isRegularFile(dir.resolve("ready"))&&verified(destination,model)&&verified(tokenFile,tokens))return;
                Files.deleteIfExists(dir.resolve("ready"));
                Path partial=dir.resolve("."+raw.name+".partial");
                if(Files.exists(partial)&&Files.size(partial)>=raw.size&&!verified(partial,raw))Files.delete(partial);
                if(!verified(partial,raw)) {
                    try {
                        download(new URL(base,raw.name+"?download=true"),partial,raw,0,raw.size,progress);
                        if(!verified(partial,raw))throw new IOException("downloaded model failed verification");
                    } catch(IOException first) {
                        if(mirror==null||Thread.currentThread().isInterrupted())throw first;
                        // A complete but invalid partial must not be resumed.
                        if(Files.exists(partial)&&Files.size(partial)>=raw.size)Files.delete(partial);
                        try {download(new URL(mirror,raw.name+"?download=true"),partial,raw,0,raw.size,progress);}
                        catch(IOException second){second.addSuppressed(first);throw second;}
                    }
                }
                if(!verified(partial,raw))throw new IOException("downloaded model failed verification; retry preparation");
                Path staged=dir.resolve(".model-"+UUID.randomUUID()+".tmp"),stagedTokens=dir.resolve(".tokens-"+UUID.randomUUID()+".tmp"),marker=dir.resolve(".ready-"+UUID.randomUUID()+".tmp");
                try {
                    Files.copy(partial,staged);
                    try(FileOutputStream out=new FileOutputStream(staged.toFile(),true)){out.write(metadata);out.getFD().sync();}
                    try(FileOutputStream out=new FileOutputStream(stagedTokens.toFile())){out.write(vocabulary);out.getFD().sync();}
                    if(!verified(staged,model)||!verified(stagedTokens,tokens))throw new IOException("local model metadata failed verification");
                    Files.move(staged,destination,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                    Files.move(stagedTokens,tokenFile,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                    try(FileOutputStream out=new FileOutputStream(marker.toFile())){out.write(model.sha256.getBytes(StandardCharsets.US_ASCII));out.getFD().sync();}
                    Files.move(marker,dir.resolve("ready"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                    Files.deleteIfExists(partial);if(progress!=null)progress.onProgress(raw.size,raw.size);
                } finally {Files.deleteIfExists(staged);Files.deleteIfExists(stagedTokens);Files.deleteIfExists(marker);}
            } finally {lock.release();}
        }
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
