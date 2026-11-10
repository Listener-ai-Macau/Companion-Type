package com.denzic.companion.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import org.json.*;

/** User context is independent of ASR and AI facts. Flat recording-owned files use the
 * existing library backup and exact lifecycle ownership, for recorder and file sources. */
final class RecordingNotes {
    static final long MAX_IMAGE=20L*1024*1024;
    private final Path directory;
    private final PlaybackProgress.DirectorySync sync;
    RecordingNotes(Path directory,PlaybackProgress.DirectorySync sync){this.directory=directory;this.sync=sync;}
    private static String digest(String value)throws Exception{return AiMaterialStore.hash(value);}
    private Path file(String key)throws Exception{return directory.resolve(digest(key)+".context.json");}
    private void safe(Path p)throws IOException{
        if(Files.isSymbolicLink(p)||!p.toAbsolutePath().normalize().getParent().equals(directory.toAbsolutePath().normalize()))throw new IOException("备注文件位置无效，原资料保留。");
    }
    private static void key(String key)throws IOException{
        // MeetingStore.sessionKey encodes recorder epoch/session as unsigned hex;
        // imported audio also uses this bounded identity shape (hash:1:1).
        if(key==null||!key.matches("[0-9a-f]{24,64}:[0-9a-f]{1,16}:[0-9a-f]{1,16}"))throw new IOException("录音标识无效。");
    }
    JSONObject read(String key)throws Exception{
        synchronized(RecordingNotes.class){
            key(key);Path p=file(key);safe(p);
            if(!Files.exists(p,LinkOption.NOFOLLOW_LINKS))return new JSONObject().put("key",key).put("revision",0).put("entries",new JSONArray());
            if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.size(p)>4*1024*1024)throw new IOException("备注资料无法读取，原文件保留，请先备份后检查。");
            try{
                JSONObject envelope=new JSONObject(new String(Files.readAllBytes(p),StandardCharsets.UTF_8));String body=envelope.getString("body");
                if(!digest(body).equals(envelope.getString("sha256")))throw new IOException("备注校验失败，原文件保留。");
                JSONObject value=new JSONObject(body);if(value.getInt("schema")!=1||!key.equals(value.getString("key"))||value.getLong("revision")<1)throw new IOException("备注身份不符，原文件保留。");
                JSONArray entries=value.getJSONArray("entries");if(entries.length()>500)throw new IOException("备注数量无效。");Set<String> seen=new HashSet<>();
                for(int i=0;i<entries.length();i++){JSONObject entry=entries.getJSONObject(i);validate(entry);if(!seen.add(entry.getString("id")))throw new IOException("备注标识重复。");if(entry.has("image"))imagePath(key,entry.getJSONObject("image"));}
                return value;
            }catch(JSONException e){throw new IOException("备注资料损坏，原文件保留，请先备份后检查。",e);}
        }
    }
    private static void validate(JSONObject entry)throws Exception{
        if(!entry.getString("id").matches("[0-9a-f-]{36}")||entry.getString("text").length()>4000||entry.getLong("createdAt")<=0||entry.getLong("updatedAt")<entry.getLong("createdAt"))throw new IOException("备注内容无效。");
        if(!entry.isNull("atMs")&&(entry.getLong("atMs")<0||entry.getLong("atMs")>86400000))throw new IOException("备注时间无效。");
        if(entry.getString("text").trim().isEmpty()&&!entry.has("image"))throw new IOException("请填写备注或选择图片。");
    }
    private JSONObject expected(String key,long revision)throws Exception{
        JSONObject current=read(key);if(current.getLong("revision")!=revision)throw new IOException("备注已更新，请重新读取后再保存；当前输入仍可保留。");return current;
    }
    private void write(String key,JSONObject value)throws Exception{
        Files.createDirectories(directory);if(Files.isSymbolicLink(directory))throw new IOException("备注目录无效。");
        value.put("schema",1);String body=value.toString();byte[] bytes=new JSONObject().put("body",body).put("sha256",digest(body)).toString().getBytes(StandardCharsets.UTF_8);
        if(bytes.length>4*1024*1024)throw new IOException("备注过大，请减少内容后重试。");
        Path temp=Files.createTempFile(directory,".context-",".tmp");
        try{try(FileChannel out=FileChannel.open(temp,StandardOpenOption.WRITE)){java.nio.ByteBuffer buffer=java.nio.ByteBuffer.wrap(bytes);while(buffer.hasRemaining())out.write(buffer);out.force(true);}Files.move(temp,file(key),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);sync.sync(directory);}finally{Files.deleteIfExists(temp);}
    }
    JSONObject save(String key,long revision,String id,String text,Long atMs,long durationMs)throws Exception{
        synchronized(RecordingNotes.class){
            JSONObject value=expected(key,revision);JSONArray entries=value.getJSONArray("entries");JSONObject entry=null;
            if(id!=null&&!id.isEmpty()){for(int i=0;i<entries.length();i++)if(id.equals(entries.getJSONObject(i).getString("id")))entry=entries.getJSONObject(i);if(entry==null)throw new IOException("这条备注已不存在，请重新读取。");}
            if(atMs!=null&&(durationMs<=0||atMs<0||atMs>=durationMs))throw new IOException("请选择已保存音频内的时间点。");
            if(entry==null){if(entries.length()>=500)throw new IOException("每条录音最多保存500条备注。");entry=new JSONObject().put("id",UUID.randomUUID().toString()).put("createdAt",System.currentTimeMillis());entries.put(entry);}
            entry.put("text",text==null?"":text.trim()).put("atMs",atMs==null?JSONObject.NULL:atMs).put("updatedAt",System.currentTimeMillis());validate(entry);
            value.put("revision",revision+1);write(key,value);return value;
        }
    }
    interface ImageCheck { void validate(Path file)throws Exception; }
    JSONObject addImage(String key,long revision,String text,Long atMs,long durationMs,String originalName,String extension,InputStream source,ImageCheck check)throws Exception{
        synchronized(RecordingNotes.class){
            JSONObject value=expected(key,revision);JSONArray entries=value.getJSONArray("entries");if(entries.length()>=500)throw new IOException("每条录音最多保存500条备注。");
            if(!Arrays.asList("jpg","png","webp").contains(extension))throw new IOException("请选择JPEG、PNG或WebP图片。");
            if(atMs!=null&&(durationMs<=0||atMs<0||atMs>=durationMs))throw new IOException("请选择已保存音频内的时间点。");
            Files.createDirectories(directory);String id=UUID.randomUUID().toString(),name=digest(key)+".context-"+id+"."+extension;Path target=directory.resolve(name),temp=Files.createTempFile(directory,".context-image-",".tmp");boolean committed=false;
            try{
                long count=0;java.security.MessageDigest hash=java.security.MessageDigest.getInstance("SHA-256");try(FileOutputStream out=new FileOutputStream(temp.toFile())){byte[] buffer=new byte[65536];int n;while((n=source.read(buffer))!=-1){if(n==0)continue;count+=n;if(count>MAX_IMAGE)throw new IOException("图片超过20MB，请选择较小的图片。");out.write(buffer,0,n);hash.update(buffer,0,n);}out.getFD().sync();}
                if(count==0)throw new IOException("所选图片为空。");check.validate(temp);StringBuilder sha=new StringBuilder();for(byte b:hash.digest())sha.append(String.format(Locale.ROOT,"%02x",b&255));
                String display=originalName==null?"图片":originalName.replaceAll("[\\r\\n\\x00-\\x1f]"," ");if(display.length()>200)display=display.substring(0,200);
                JSONObject image=new JSONObject().put("file",name).put("name",display).put("bytes",count).put("sha256",sha.toString());
                JSONObject entry=new JSONObject().put("id",id).put("text",text==null?"":text.trim()).put("atMs",atMs==null?JSONObject.NULL:atMs).put("image",image).put("createdAt",System.currentTimeMillis()).put("updatedAt",System.currentTimeMillis());validate(entry);
                Files.move(temp,target,StandardCopyOption.ATOMIC_MOVE);sync.sync(directory);entries.put(entry);value.put("revision",revision+1);write(key,value);committed=true;return value;
            }finally{Files.deleteIfExists(temp);if(!committed){/* A failed directory sync can follow a durable metadata rename. Keep a possibly referenced image. */}}
        }
    }
    JSONObject remove(String key,long revision,String id)throws Exception{
        synchronized(RecordingNotes.class){JSONObject value=expected(key,revision);JSONArray entries=value.getJSONArray("entries"),next=new JSONArray();boolean found=false;
            for(int i=0;i<entries.length();i++){JSONObject e=entries.getJSONObject(i);if(id.equals(e.getString("id")))found=true;else next.put(e);}if(!found)throw new IOException("这条备注已不存在，请重新读取。");
            value.put("entries",next).put("revision",revision+1);write(key,value);
            // Unreferenced originals remain recording-owned until the recording is permanently
            // purged. This permits atomic metadata publication without deleting live images.
            return value;
        }
    }
    Path imagePath(String key,JSONObject image)throws Exception{
        String name=image.getString("file");if(!name.matches(java.util.regex.Pattern.quote(digest(key))+"\\.context-[0-9a-f-]{36}\\.(jpg|png|webp)")||!image.getString("sha256").matches("[0-9a-f]{64}")||image.getLong("bytes")<1||image.getLong("bytes")>MAX_IMAGE)throw new IOException("图片身份无效，原资料保留。");Path p=directory.resolve(name);safe(p);return p;
    }
    Path verifiedImage(String key,JSONObject image)throws Exception{
        Path p=imagePath(key,image);if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.size(p)!=image.getLong("bytes"))throw new IOException("图片缺失或大小已变化，原备注保留。");
        java.security.MessageDigest sha=java.security.MessageDigest.getInstance("SHA-256");try(InputStream in=Files.newInputStream(p)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)sha.update(b,0,n);}StringBuilder s=new StringBuilder();for(byte b:sha.digest())s.append(String.format(Locale.ROOT,"%02x",b&255));if(!s.toString().equals(image.getString("sha256")))throw new IOException("图片校验失败，原备注保留。");return p;
    }
    static String clock(long ms){return String.format(Locale.ROOT,"%02d:%02d:%02d",ms/3600000,ms/60000%60,ms/1000%60);}
    static String searchableText(JSONObject notes)throws Exception{
        StringBuilder text=new StringBuilder();JSONArray entries=notes.getJSONArray("entries");
        for(int i=0;i<entries.length();i++){JSONObject entry=entries.getJSONObject(i);text.append(entry.getString("text")).append('\n');if(entry.has("image"))text.append(entry.getJSONObject("image").getString("name")).append('\n');}
        return text.toString();
    }
    static String text(JSONObject notes)throws Exception{
        StringBuilder out=new StringBuilder();JSONArray entries=notes.getJSONArray("entries");if(entries.length()>0)out.append("用户备注与图片（人工补充，不是录音转写或AI结论）\n");
        for(int i=0;i<entries.length();i++){JSONObject e=entries.getJSONObject(i);out.append('\n').append(e.isNull("atMs")?"整场备注":clock(e.getLong("atMs"))).append("\n").append(e.getString("text")).append('\n');if(e.has("image"))out.append("图片：").append(e.getJSONObject("image").getString("name")).append("（原图见图文ZIP）\n");}return out.toString();
    }
    private static String html(String s){return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\"","&quot;").replace("'","&#39;");}
    void bundle(String key,JSONObject notes,String title,String markdown,OutputStream stream)throws Exception{
        ZipOutputStream zip=new ZipOutputStream(stream,StandardCharsets.UTF_8);StringBuilder page=new StringBuilder("<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; img-src 'self'; style-src 'unsafe-inline'\"><title>").append(html(title)).append("</title><style>body{font:17px/1.8 system-ui;max-width:900px;margin:40px auto;padding:0 24px;color:#242631}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}article{border-top:1px solid #ddd;padding:20px 0}img{max-width:100%;height:auto}small{color:#657080}</style><h1>").append(html(title)).append("</h1><pre>").append(html(markdown)).append("</pre><h2>用户备注与图片</h2><p>人工补充，不是录音转写或AI结论。图片是所选原件。</p>");
        put(zip,"会议材料.md",("# "+title+"\n\n"+markdown).getBytes(StandardCharsets.UTF_8));JSONArray entries=notes.getJSONArray("entries");
        for(int i=0;i<entries.length();i++){JSONObject e=entries.getJSONObject(i);page.append("<article><small>").append(e.isNull("atMs")?"整场备注":clock(e.getLong("atMs"))).append("</small><pre>").append(html(e.getString("text"))).append("</pre>");if(e.has("image")){JSONObject image=e.getJSONObject("image");Path p=verifiedImage(key,image);String name="images/"+e.getString("id")+p.getFileName().toString().substring(p.getFileName().toString().lastIndexOf('.'));zip.putNextEntry(new ZipEntry(name));Files.copy(p,zip);zip.closeEntry();page.append("<img src=\"").append(name).append("\" alt=\"").append(html(image.getString("name"))).append("\"><p>").append(html(image.getString("name"))).append("</p>");}page.append("</article>");}
        put(zip,"打开阅读.html",page.append("</html>").toString().getBytes(StandardCharsets.UTF_8));put(zip,"备注来源.json",notes.toString(2).getBytes(StandardCharsets.UTF_8));zip.finish();zip.flush();
    }
    private static void put(ZipOutputStream zip,String name,byte[] body)throws IOException{zip.putNextEntry(new ZipEntry(name));zip.write(body);zip.closeEntry();}
}
