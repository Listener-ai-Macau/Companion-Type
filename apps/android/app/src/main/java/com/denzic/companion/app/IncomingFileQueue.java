package com.denzic.companion.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Pending OS deliveries, not a second recording library. No original is imported until confirmed. */
final class IncomingFileQueue {
    private final Path root, index;
    interface Sync { void sync(Path directory)throws IOException; }
    private final Sync sync;
    IncomingFileQueue(Path root,Sync sync){this.root=root.toAbsolutePath().normalize();this.index=this.root.resolve("companion-incoming-v1.json");this.sync=sync;}
    private static void id(String id)throws IOException{if(id==null||!id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))throw new IOException("接收标识无效，请重新分享文件。");}
    static String kind(String name,String mime){
        String ext=name.toLowerCase(Locale.ROOT).replaceFirst("^.*\\.","");
        if(Arrays.asList("pdf","docx","xlsx","pptx","txt","md","csv").contains(ext))return "document";
        if(Arrays.asList("jpg","jpeg","png","webp").contains(ext)||Arrays.asList("image/jpeg","image/png","image/webp").contains(mime))return "image";
        if(Arrays.asList("wav","mp3","m4a","aac","flac","ogg","opus","mp4","mov","mkv","webm","3gp","amr","wma","aiff","aif").contains(ext)||mime.startsWith("audio/")||mime.startsWith("video/"))return "media";
        return "unsupported";
    }
    static String imageExtension(JSONObject row)throws Exception{
        String name=row.getString("name").toLowerCase(Locale.ROOT);String mime=row.optString("mime","");
        if(name.endsWith(".png")||"image/png".equals(mime))return "png";
        if(name.endsWith(".webp")||"image/webp".equals(mime))return "webp";
        if(name.endsWith(".jpg")||name.endsWith(".jpeg")||"image/jpeg".equals(mime))return "jpg";
        throw new IOException("请选择JPEG、PNG或WebP图片。");
    }
    private JSONArray read()throws Exception{
        if(!Files.exists(index,LinkOption.NOFOLLOW_LINKS))return new JSONArray();
        if(Files.isSymbolicLink(index)||!Files.isRegularFile(index,LinkOption.NOFOLLOW_LINKS)||Files.size(index)>256*1024)throw new IOException("接收清单暂不可读取，原资料未改变，请保留文件后重试。");
        JSONObject value=new JSONObject(new String(Files.readAllBytes(index),StandardCharsets.UTF_8));String body=value.getString("body");
        if(!hash(body).equals(value.getString("sha256")))throw new IOException("接收清单校验失败，原资料未改变。");
        JSONObject data=new JSONObject(body);if(data.getInt("version")!=1)throw new IOException("接收清单版本无效。");JSONArray rows=data.getJSONArray("rows");
        if(rows.length()>32)throw new IOException("接收清单过长。");Set<String> seen=new HashSet<>();
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);id(row.getString("id"));if(!seen.add(row.getString("id"))||row.getString("uri").length()>8192||!row.getString("uri").startsWith("content://")||row.getString("name").length()>200||row.getString("mime").length()>256||!Arrays.asList("ready","attempting","complete","failed").contains(row.getString("state")))throw new IOException("接收清单无效，原资料未改变。");}
        return rows;
    }
    private static String hash(String value)throws Exception{StringBuilder out=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
    private void write(JSONArray rows)throws Exception{
        Files.createDirectories(root);String body=new JSONObject().put("version",1).put("rows",rows).toString();byte[] bytes=new JSONObject().put("body",body).put("sha256",hash(body)).toString().getBytes(StandardCharsets.UTF_8);
        if(bytes.length>256*1024)throw new IOException("接收清单已满，请整理后重试。");Path temp=Files.createTempFile(root,".incoming-",".tmp");
        try{try(FileOutputStream out=new FileOutputStream(temp.toFile())){out.write(bytes);out.getFD().sync();}Files.move(temp,index,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);sync.sync(root);}finally{Files.deleteIfExists(temp);}
    }
    JSONObject get(String entryId)throws Exception{synchronized(IncomingFileQueue.class){id(entryId);JSONArray rows=read();for(int i=0;i<rows.length();i++)if(entryId.equals(rows.getJSONObject(i).getString("id")))return rows.getJSONObject(i);throw new IOException("这项接收已移除，请重新读取。");}}
    void receive(JSONArray incoming)throws Exception{synchronized(IncomingFileQueue.class){
        if(incoming.length()<1||incoming.length()>16)throw new IOException("一次最多接收16个文件，请分批分享。");JSONArray rows=read();int pending=0;for(int i=0;i<rows.length();i++)if(!"complete".equals(rows.getJSONObject(i).getString("state")))pending++;
        // Validate the complete delivery before publishing any item.
        List<JSONObject> add=new ArrayList<>();
        for(int j=0;j<incoming.length();j++){
            JSONObject source=incoming.getJSONObject(j);String uri=source.getString("uri"),name=source.getString("name"),mime=source.getString("mime");
            if(!uri.startsWith("content://")||uri.length()>8192||name.isEmpty()||name.length()>200||mime.length()>256)throw new IOException("分享文件的信息不完整，请另存后重新分享。");
            boolean duplicate=false;for(int i=0;i<rows.length();i++){JSONObject old=rows.getJSONObject(i);if(!"complete".equals(old.getString("state"))&&uri.equals(old.getString("uri"))&&name.equals(old.getString("name")))duplicate=true;}
            for(JSONObject old:add)if(uri.equals(old.getString("uri"))&&name.equals(old.getString("name")))duplicate=true;
            if(!duplicate)add.add(new JSONObject(source.toString()).put("id",UUID.randomUUID().toString()).put("kind",kind(name,mime)).put("state","ready").put("receivedAt",System.currentTimeMillis()));
        }
        if(pending+add.size()>16||rows.length()+add.size()>32)throw new IOException("待处理文件已满，请先导入或移除，再重新分享；已有资料保留。");
        for(JSONObject row:add)rows.put(row);write(rows);
    }}
    private void replace(JSONObject changed)throws Exception{JSONArray rows=read();boolean found=false;for(int i=0;i<rows.length();i++)if(changed.getString("id").equals(rows.getJSONObject(i).getString("id"))){rows.put(i,changed);found=true;}if(!found)throw new IOException("这项接收已移除。");write(rows);}
    JSONObject bind(String entryId,String libraryId,String key,String title)throws Exception{synchronized(IncomingFileQueue.class){
        JSONObject row=get(entryId);if("unsupported".equals(row.getString("kind")))throw new IOException("暂不支持此文件格式，请使用音视频、PDF、Office文档或常见图片。");
        if(row.has("libraryId")&&(!libraryId.equals(row.getString("libraryId"))||!key.equals(row.getString("key"))))throw new IOException("此项已指定其它资料或会议，请切回原资料继续，或移除后重新分享。");
        row.put("libraryId",libraryId).put("key",key).put("targetTitle",title);replace(row);return row;
    }}
    void state(String entryId,String state,String message)throws Exception{synchronized(IncomingFileQueue.class){JSONObject row=get(entryId);row.put("state",state).put("message",message);replace(row);}}
    JSONArray list()throws Exception{synchronized(IncomingFileQueue.class){JSONArray rows=read(),out=new JSONArray();for(int i=0;i<rows.length();i++){JSONObject row=new JSONObject(rows.getJSONObject(i).toString());row.remove("uri");out.put(row);}return out;}}
    void remove(String entryId)throws Exception{synchronized(IncomingFileQueue.class){id(entryId);JSONArray rows=read(),next=new JSONArray();for(int i=0;i<rows.length();i++)if(!entryId.equals(rows.getJSONObject(i).getString("id")))next.put(rows.getJSONObject(i));write(next);}}
}
