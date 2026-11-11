package com.denzic.companion.app;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Immutable app-owned export copies. The provider never resolves arbitrary app files. */
final class PreparedExports {
    static final long LIFETIME=24L*60*60*1000;static final int COPY_LIMIT=256*1024;
    private static String previewPrefix(String text,int limit){if(text==null)return "";int end=Math.min(text.length(),limit);if(end<text.length()&&end>0&&Character.isHighSurrogate(text.charAt(end-1))&&Character.isLowSurrogate(text.charAt(end)))end--;return text.substring(0,end);}
    interface Writer{void write(OutputStream out)throws Exception;}
    final Path root;
    PreparedExports(Path cache){root=cache.resolve("companion-shared").toAbsolutePath().normalize();}
    static String hash(Path file)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");try(InputStream in=Files.newInputStream(file)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)d.update(b,0,n);}StringBuilder s=new StringBuilder();for(byte b:d.digest())s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
    static boolean validId(String id){try{return id!=null&&UUID.fromString(id).toString().equals(id);}catch(IllegalArgumentException e){return false;}}
    static String filename(String title,String suffix,String extension){String base=DocumentNames.audio(title,false);base=base.substring(0,base.length()-4);return base+"-"+suffix+"."+extension;}
    static final class Entry{
        final JSONObject meta;final Path file,copy;Entry(JSONObject m,Path f,Path c){meta=m;file=f;copy=c;}
        String id()throws JSONException{return meta.getString("id");}
        JSONObject dto()throws Exception{
            long copyBytes=meta.getLong("copyBytes");String preview=meta.optString("preview","");boolean complete=copyBytes==0&&preview.isEmpty();
            if(copyBytes>0&&copyBytes<=COPY_LIMIT){if(Files.size(copy)!=copyBytes||!hash(copy).equals(meta.getString("copySha256")))throw new IOException("预览副本已变化，请重新准备。");String full=new String(Files.readAllBytes(copy),StandardCharsets.UTF_8);preview=previewPrefix(full,64000);complete=preview.length()==full.length();}
            return new JSONObject().put("id",id()).put("filename",meta.getString("filename")).put("mime",meta.getString("mime")).put("bytes",meta.getLong("bytes")).put("copyAllowed",copyBytes>0&&copyBytes<=COPY_LIMIT).put("preview",preview).put("previewComplete",complete).put("previewCharacters",preview.codePointCount(0,preview.length())).put("warnings",meta.optJSONArray("warnings"));
        }
    }
    Entry create(JSONObject source,String filename,String mime,String text,Writer writer)throws Exception{
        Files.createDirectories(root);cleanup();String id=UUID.randomUUID().toString();Path stage=Files.createTempDirectory(root,".prepare-");boolean published=false;
        try{
            if(!filename.equals(Paths.get(filename).getFileName().toString())||filename.indexOf('/')>=0||filename.indexOf('\\')>=0||filename.equals(".")||filename.equals(".."))throw new IOException("无效的文件名。");
            Path content=stage.resolve(filename);try(OutputStream out=Files.newOutputStream(content,StandardOpenOption.CREATE_NEW)){writer.write(out);}
            if(Files.size(content)<=0)throw new IOException("没有可保存的内容。");
            byte[] copy=text==null?new byte[0]:text.getBytes(StandardCharsets.UTF_8);Files.write(stage.resolve("copy.txt"),copy,StandardOpenOption.CREATE_NEW);
            JSONObject meta=new JSONObject(source.toString()).put("version",1).put("id",id).put("filename",filename).put("mime",mime).put("bytes",Files.size(content)).put("sha256",hash(content)).put("copyBytes",copy.length).put("copySha256",hash(stage.resolve("copy.txt"))).put("createdAt",System.currentTimeMillis()).put("preview",previewPrefix(text,350));
            Files.write(stage.resolve("manifest.json"),meta.toString().getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
            Files.move(stage,root.resolve(id),StandardCopyOption.ATOMIC_MOVE);published=true;return load(id,true);
        }finally{if(!published)remove(stage);}
    }
    Entry load(String id,boolean verify)throws Exception{
        if(!validId(id))throw new IOException("分享文件已失效，请重新准备。");Path dir=root.resolve(id);
        if(Files.isSymbolicLink(dir)||!Files.isDirectory(dir,LinkOption.NOFOLLOW_LINKS))throw new IOException("临时文件已不可用，请重新准备。");
        Path manifest=dir.resolve("manifest.json");if(!Files.isRegularFile(manifest,LinkOption.NOFOLLOW_LINKS)||Files.size(manifest)>64000)throw new IOException("文件信息不可用。");
        JSONObject m=new JSONObject(new String(Files.readAllBytes(manifest),StandardCharsets.UTF_8));String name=m.getString("filename");
        if(m.getInt("version")!=1||!id.equals(m.getString("id"))||name.contains("/")||name.contains("\\")||name.equals(".")||name.equals("..")||System.currentTimeMillis()-m.getLong("createdAt")>LIFETIME)throw new IOException("分享文件已失效，请重新准备。");
        Path file=dir.resolve(name),copy=dir.resolve("copy.txt");
        if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)||Files.size(file)!=m.getLong("bytes")||!Files.isRegularFile(copy,LinkOption.NOFOLLOW_LINKS)||Files.size(copy)!=m.getLong("copyBytes"))throw new IOException("临时文件已变化，请重新准备。");
        if(verify&&(!hash(file).equals(m.getString("sha256"))||!hash(copy).equals(m.getString("copySha256"))))throw new IOException("文件校验失败，请重新准备。");return new Entry(m,file,copy);
    }
    void requireLibrary(Entry entry,String token)throws Exception{if(!token.equals(entry.meta.getString("libraryToken")))throw new IOException("资料已切换，请重新选择内容。");}
    String copyText(Entry entry)throws Exception{if(entry.meta.getLong("copyBytes")<=0||entry.meta.getLong("copyBytes")>COPY_LIMIT)throw new IOException("内容较长，请保存或分享文件。");return new String(Files.readAllBytes(entry.copy),StandardCharsets.UTF_8);}
    void write(Entry entry,OutputStream output)throws Exception{Files.copy(entry.file,output);}
    private void remove(Path path)throws IOException{if(!path.getParent().equals(root))throw new IOException("Unexpected export cache path");try(java.util.stream.Stream<Path> paths=Files.walk(path)){Iterator<Path> iterator=paths.sorted(Comparator.reverseOrder()).iterator();while(iterator.hasNext())Files.deleteIfExists(iterator.next());}}
    void cleanup()throws IOException{if(!Files.isDirectory(root))return;try(DirectoryStream<Path> dirs=Files.newDirectoryStream(root)){for(Path path:dirs){String name=path.getFileName().toString();if(!validId(name)&&!name.startsWith(".prepare-"))continue;if(!Files.isSymbolicLink(path)&&Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS)&&System.currentTimeMillis()-Files.getLastModifiedTime(path).toMillis()>LIFETIME)remove(path);}}}
}
