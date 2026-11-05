package com.denzic.companion.app;

import com.denzic.companion.mobile.LibraryBackup;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.*;

/** App-private library selection. Restores publish NEW folders, then one atomic index. */
final class LocalLibraryBackups {
    static final AtomicBoolean BUSY=new AtomicBoolean();
    private final Path root,index;
    LocalLibraryBackups(Path root){this.root=root.toAbsolutePath().normalize();index=this.root.resolve("companion-library-index.json");}
    private static String hash(byte[] bytes)throws Exception{StringBuilder out=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
    private static boolean validId(String id){return "original".equals(id)||id!=null&&id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}");}
    private Path path(String kind,String id)throws IOException{
        if(!validId(id))throw new IOException("资料库标识无效，原文件已保留。");
        Path p=root.resolve("companion-"+kind+("original".equals(id)?"":"-"+id));
        if(!p.getParent().equals(root)||Files.isSymbolicLink(p)||Files.exists(p,LinkOption.NOFOLLOW_LINKS)&&!Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS))throw new IOException("资料目录无法读取，原文件已保留。");return p;
    }
    private JSONObject read()throws Exception{
        if(Files.isSymbolicLink(index))throw new IOException("资料库索引无法读取，原文件已保留。");
        if(!Files.exists(index))return new JSONObject().put("version",1).put("activeId","original").put("libraries",new JSONArray().put(new JSONObject().put("id","original").put("restoredAt",0)));
        if(!Files.isRegularFile(index,LinkOption.NOFOLLOW_LINKS)||Files.size(index)>1000000)throw new IOException("资料库索引无法读取，原文件已保留。");
        try{
            JSONObject value=new JSONObject(new String(Files.readAllBytes(index),StandardCharsets.UTF_8));
            if(value.getInt("version")!=1)throw new IOException("Unsupported library index");
            JSONArray libraries=value.getJSONArray("libraries");if(libraries.length()<1||libraries.length()>10000)throw new IOException("Invalid library count");
            Set<String> ids=new HashSet<>();for(int i=0;i<libraries.length();i++){JSONObject item=libraries.getJSONObject(i);String id=item.getString("id");if(!validId(id)||!ids.add(id)||item.getLong("restoredAt")<0)throw new IOException("Invalid library index");}
            if(!ids.contains("original")||!ids.contains(value.getString("activeId")))throw new IOException("Invalid active library");
            String previous=value.optString("previousId","");if(!previous.isEmpty()&&!ids.contains(previous))throw new IOException("Invalid previous library");
            for(String id:ids)if(!"original".equals(id)){if(!Files.isDirectory(path("recordings",id))||!Files.isDirectory(path("meetings",id)))throw new IOException("Restored library missing");}
            return value;
        }catch(Exception error){throw new IOException("资料库索引无法读取，原文件已保留，请保留现有资料后重试。",error);}
    }
    String token()throws Exception{return hash(read().toString().getBytes(StandardCharsets.UTF_8));}
    private Path selectedPath(String kind)throws IOException{try{return path(kind,read().getString("activeId"));}catch(IOException error){throw error;}catch(Exception error){throw new IOException("资料库索引无法读取，原文件已保留。",error);}}
    Path recordings()throws IOException{return selectedPath("recordings");}
    Path meetings()throws IOException{return selectedPath("meetings");}
    JSONObject status()throws Exception{JSONObject v=read();v.put("token",hash(v.toString().getBytes(StandardCharsets.UTF_8)));return v;}
    private void expected(String token)throws Exception{if(token==null||!token.equals(token()))throw new IOException("资料已变化，请刷新备份页面后重试；原资料未被覆盖。");}
    private void publish(JSONObject value)throws Exception{
        byte[] bytes=value.toString().getBytes(StandardCharsets.UTF_8);Path temp=root.resolve(".companion-library-"+UUID.randomUUID()+".tmp");
        try(FileChannel out=FileChannel.open(temp,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)){ByteBuffer b=ByteBuffer.wrap(bytes);while(b.hasRemaining())out.write(b);out.force(true);}
        try{Files.move(temp,index,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}finally{Files.deleteIfExists(temp);}
    }
    void write(OutputStream output,String token)throws Exception{
        Files.createDirectories(root);
        try(FileChannel channel=FileChannel.open(root.resolve(".companion-library.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);FileLock ignored=channel.lock()){
            expected(token);Path rec=recordings(),meet=meetings();Files.createDirectories(rec);Files.createDirectories(meet);
            LibraryBackup.write(output,rec,meet,null);expected(token);
        }
    }
    JSONObject activate(String id,String token)throws Exception{
        try(FileChannel channel=FileChannel.open(root.resolve(".companion-library.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);FileLock ignored=channel.lock()){
            expected(token);JSONObject v=read();boolean known=false;JSONArray list=v.getJSONArray("libraries");for(int i=0;i<list.length();i++)if(id.equals(list.getJSONObject(i).getString("id")))known=true;
            if(!known)throw new IOException("找不到这份保留的资料。");
            if(!id.equals(v.getString("activeId"))){v.put("previousId",v.getString("activeId")).put("activeId",id);publish(v);}return status();
        }
    }
    JSONObject restore(InputStream input,String token)throws Exception{
        Files.createDirectories(root);
        try(FileChannel channel=FileChannel.open(root.resolve(".companion-library.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);FileLock ignored=channel.lock()){
            expected(token);JSONObject v=read();String id=UUID.randomUUID().toString();Path target=root.resolve(".companion-import-"+id);
            long budget=Math.max(0,root.toFile().getUsableSpace()-65536);
            LibraryBackup.restore(input,target,budget,100000);
            // Device confirmation receipts are preserved for inspection, never replayed by a restore.
            Path rec=target.resolve("recordings");try(DirectoryStream<Path> files=Files.newDirectoryStream(rec,".consume*")){
                for(Path file:files){Path held=rec.resolve("backup-device-receipts").resolve(id);Files.createDirectories(held);Files.move(file,held.resolve(file.getFileName()));}
            }
            expected(token);Files.move(rec,path("recordings",id));Files.move(target.resolve("meetings"),path("meetings",id));
            // Optional control data stays in the private import folder and is never activated.
            v.getJSONArray("libraries").put(new JSONObject().put("id",id).put("restoredAt",System.currentTimeMillis()));
            v.put("previousId",v.getString("activeId")).put("activeId",id);publish(v);return status();
        }
    }
}
