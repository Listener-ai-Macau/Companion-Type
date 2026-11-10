package com.denzic.companion.mobile;

import org.json.*;
import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Original external media plus verified lossless speech WAVs. Never a device descriptor. */
public final class ImportedAudio {
    public interface DirectorySync {void sync(Path directory)throws IOException;}
    public final Path directory,original;
    public final String key,name,mime;
    public final long samples,originalBytes;
    private final String originalHash;
    private final List<Long> sizes;
    private final List<String> hashes;
    private final byte[] fingerprint;
    private ImportedAudio(Path path,JSONObject json,byte[] raw,boolean staged)throws Exception {
        directory=path.toAbsolutePath().normalize();key=json.getString("key");
        if(json.getInt("version")!=1||!"importedAudio".equals(json.getString("kind"))||!validKey(key)||(!staged&&!directory.getFileName().toString().equals(folder(key))))throw new IOException("导入录音身份不符，原文件保留。");
        name=json.getString("name");mime=json.getString("mime");originalBytes=json.getLong("originalBytes");originalHash=json.getString("originalSha256");original=directory.resolve("original.audio");
        if(name.isEmpty()||name.length()>256||mime.length()>256||originalBytes<=0||originalBytes>2L*1024*1024*1024||!originalHash.matches("[0-9a-f]{64}"))throw new IOException("导入原文件信息无效。");
        JSONArray parts=json.getJSONArray("parts");if(parts.length()<1||parts.length()>24)throw new IOException("导入录音分段无效。");
        sizes=new ArrayList<>();hashes=new ArrayList<>();long total=0;
        for(int i=0;i<parts.length();i++){JSONObject p=parts.getJSONObject(i);long count=p.getLong("samples");String hash=p.getString("sha256");if(count<=0||count>57_600_000L||!hash.matches("[0-9a-f]{64}"))throw new IOException("导入音频分段无效。");sizes.add(count);hashes.add(hash);total=Math.addExact(total,count);}
        samples=total;if(json.getLong("samples")!=total)throw new IOException("导入音频时长不符。");
        fingerprint=MessageDigest.getInstance("SHA-256").digest(raw);
        for(Path p:ownedFiles()){if(Files.isSymbolicLink(p)||!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS))throw new IOException("导入音频缺少文件，已有资料保留。");}
        if(Files.size(original)!=originalBytes)throw new IOException("导入原文件大小变化。");
        for(int i=0;i<sizes.size();i++)if(Files.size(part(directory,i))!=44+sizes.get(i)*2)throw new IOException("导入音频分段不完整。");
    }
    public static boolean validKey(String key){return key!=null&&key.matches("[0-9a-f]{64}:1:1");}
    public static String folder(String key)throws IOException {if(!validKey(key))throw new IOException("导入录音身份无效。");return "import-"+hash(key.getBytes(StandardCharsets.UTF_8));}
    public static Path part(Path directory,int index){return directory.resolve(String.format(Locale.ROOT,"part-%08d.wav",index));}
    public int partCount(){return sizes.size();}
    public byte[] fingerprint(){return fingerprint.clone();}
    public List<Path> ownedFiles(){List<Path> files=new ArrayList<>();files.add(original);for(int i=0;i<sizes.size();i++)files.add(part(directory,i));files.add(directory.resolve("import.json"));return Collections.unmodifiableList(files);}
    public static String hash(byte[] bytes){try{return hex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception e){throw new AssertionError(e);}}
    private static String hex(byte[] bytes){StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
    public static String fileHash(Path file)throws IOException {try{MessageDigest d=MessageDigest.getInstance("SHA-256");byte[] b=new byte[65536];try(InputStream in=Files.newInputStream(file)){int n;while((n=in.read(b))!=-1)d.update(b,0,n);}return hex(d.digest());}catch(java.security.NoSuchAlgorithmException e){throw new AssertionError(e);}}
    public static ImportedAudio read(Path directory)throws IOException {
        try{if(Files.isSymbolicLink(directory)||!Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS))throw new IOException("导入目录无效。");Path manifest=directory.resolve("import.json");if(Files.isSymbolicLink(manifest)||!Files.isRegularFile(manifest,LinkOption.NOFOLLOW_LINKS)||Files.size(manifest)>65536)throw new IOException("导入录音资料无法读取。");byte[] raw=Files.readAllBytes(manifest);return new ImportedAudio(directory,new JSONObject(new String(raw,StandardCharsets.UTF_8)),raw,false);}catch(IOException e){throw e;}catch(Exception e){throw new IOException("导入录音资料无法核对，原文件保留。",e);}
    }
    public NativeAudio.PartsResult verifiedParts()throws IOException {
        if(!fileHash(original).equals(originalHash))throw new IOException("导入原文件校验失败，已有资料保留。");
        List<NativeAudio.Part> parts=new ArrayList<>();long offset=0;
        for(int i=0;i<sizes.size();i++){Path file=part(directory,i);long count=sizes.get(i);byte[] h=new byte[44];try(InputStream in=Files.newInputStream(file)){new DataInputStream(in).readFully(h);}if(!Arrays.equals(h,DecodedAudioParts.expectedHeader(count))||!fileHash(file).equals(hashes.get(i)))throw new IOException("导入音频分段校验失败，原文件保留。");parts.add(new NativeAudio.Part(file,offset,count));offset+=count;}
        return new NativeAudio.PartsResult(directory,samples,true,parts,Collections.emptyList(),fingerprint);
    }
    /** Finish all files and publish the entire directory with one atomic rename. */
    public static ImportedAudio publish(Path stage,Path recordings,String key,String name,String mime,long bytes,String sourceHash,List<Long> counts,DirectorySync sync)throws IOException {
        try{
            if(!validKey(key)||Files.isSymbolicLink(stage)||!Files.isDirectory(stage,LinkOption.NOFOLLOW_LINKS)||counts.isEmpty()||counts.size()>24)throw new IOException("导入尚未完整保存。");
            JSONArray parts=new JSONArray();long total=0;for(int i=0;i<counts.size();i++){long n=counts.get(i);parts.put(new JSONObject().put("samples",n).put("sha256",fileHash(part(stage,i))));total=Math.addExact(total,n);}
            JSONObject json=new JSONObject().put("version",1).put("kind","importedAudio").put("key",key).put("name",name).put("mime",mime).put("originalBytes",bytes).put("originalSha256",sourceHash).put("samples",total).put("parts",parts);
            Path metadata=stage.resolve("import.json");try(FileOutputStream stream=new FileOutputStream(metadata.toFile())){stream.write(json.toString().getBytes(StandardCharsets.UTF_8));stream.getFD().sync();}
            Files.createDirectories(recordings);if(Files.isSymbolicLink(recordings))throw new IOException("录音目录无效。");sync.sync(stage);Path destination=recordings.resolve(folder(key));if(Files.exists(destination,LinkOption.NOFOLLOW_LINKS))throw new IOException("导入身份已存在，请重试。");
            new ImportedAudio(stage,json,json.toString().getBytes(StandardCharsets.UTF_8),true).verifiedParts();
            Files.move(stage,destination,StandardCopyOption.ATOMIC_MOVE);sync.sync(recordings);return read(destination);
        }catch(IOException e){throw e;}catch(Exception e){throw new IOException("录音未能完整保存，请重试；所选原文件未改变。",e);}
    }
}
