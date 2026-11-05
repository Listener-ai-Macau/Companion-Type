package com.denzic.companion.app;

import org.json.*;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Library-local preferences and immutable custom template versions; included in the normal backup. */
final class MinutesTemplateLibrary {
    private final Path directory,file;
    MinutesTemplateLibrary(Path meetings){directory=meetings;file=meetings.resolve("minutes-templates-v1.json");}
    static String hash(byte[] bytes)throws Exception{
        StringBuilder out=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();
    }
    static JSONObject template(JSONObject value)throws Exception{
        String id=value.getString("id");
        if(Arrays.asList("meeting","interview","lecture").contains(id))return new JSONObject().put("id",id);
        if(!"custom".equals(id))throw new IOException("不支持的纪要模板。");
        String name=value.getString("name").trim(),instructions=value.getString("instructions").trim();
        if(name.isEmpty()||instructions.isEmpty()||name.getBytes(StandardCharsets.UTF_8).length>256||instructions.getBytes(StandardCharsets.UTF_8).length>8192)
            throw new IOException("请填写模板名称和整理要求；名称最多256字节，要求最多8192字节。");
        return new JSONObject().put("id","custom").put("name",name).put("instructions",instructions);
    }
    static String identity(JSONObject t)throws Exception{
        JSONObject v=template(t);return hash((v.getString("id")+"\u0000"+v.optString("name","")+"\u0000"+v.optString("instructions","")).getBytes(StandardCharsets.UTF_8));
    }
    private JSONObject read()throws Exception{
        if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))return new JSONObject().put("version",1).put("items",new JSONArray()).put("selected",new JSONObject().put("id","meeting"));
        try{
            if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)||Files.size(file)>2*1024*1024)throw new IOException("Invalid template file");
            JSONObject envelope=new JSONObject(new String(Files.readAllBytes(file),StandardCharsets.UTF_8));
            String payload=envelope.getString("payload");if(!hash(payload.getBytes(StandardCharsets.UTF_8)).equals(envelope.getString("sha256")))throw new IOException("Template checksum mismatch");
            JSONObject state=new JSONObject(payload);if(state.getInt("version")!=1)throw new IOException("Unsupported templates");
            JSONArray items=state.getJSONArray("items");if(items.length()>200)throw new IOException("Too many templates");
            Set<String> seen=new HashSet<>();for(int i=0;i<items.length();i++){
                JSONObject t=template(items.getJSONObject(i));if(!"custom".equals(t.getString("id"))||!seen.add(identity(t)))throw new IOException("Invalid saved template");
            }
            JSONObject selected=template(state.getJSONObject("selected"));if("custom".equals(selected.getString("id"))&&!seen.contains(identity(selected)))throw new IOException("Selected template missing");
            return state;
        }catch(Exception error){throw new IOException("已保存的模板暂时无法读取，原文件已保留；不会覆盖它。",error);}
    }
    private String etag()throws Exception{return Files.exists(file,LinkOption.NOFOLLOW_LINKS)?hash(Files.readAllBytes(file)):"empty";}
    private JSONObject result(JSONObject state)throws Exception{
        JSONArray items=new JSONArray();for(int i=0;i<state.getJSONArray("items").length();i++){
            JSONObject t=template(state.getJSONArray("items").getJSONObject(i));t.put("key",identity(t));items.put(t);
        }
        return new JSONObject().put("version",1).put("etag",etag()).put("items",items).put("selected",template(state.getJSONObject("selected")));
    }
    JSONObject load()throws Exception{
        Files.createDirectories(directory);
        try(FileChannel channel=FileChannel.open(directory.resolve("minutes-templates.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);FileLock lock=channel.lock()){return result(read());}
    }
    JSONObject change(String expected,String action,JSONObject value,String key)throws Exception{
        Files.createDirectories(directory);
        try(FileChannel channel=FileChannel.open(directory.resolve("minutes-templates.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);FileLock lock=channel.lock()){
            JSONObject state=read();if(!etag().equals(expected))throw new IOException("模板已更新，请重新读取后再保存。");
            JSONArray current=state.getJSONArray("items"),next=new JSONArray();
            if("delete".equals(action)){
                boolean found=false;for(int i=0;i<current.length();i++){
                    JSONObject item=current.getJSONObject(i);if(identity(item).equals(key))found=true;else next.put(item);
                }
                if(!found)throw new IOException("这份模板已变化，请重新读取。");
                if(identity(state.getJSONObject("selected")).equals(key))state.put("selected",new JSONObject().put("id","meeting"));
            }else if("select".equals(action)||"save".equals(action)){
                JSONObject t=template(value);boolean found=false;
                for(int i=0;i<current.length();i++){JSONObject item=current.getJSONObject(i);next.put(item);if(identity(item).equals(identity(t)))found=true;}
                if("custom".equals(t.getString("id"))&&!found){
                    if(!"save".equals(action))throw new IOException("请先保存这份自定义模板。");
                    if(next.length()>=200)throw new IOException("已保存200份模板，请先移除不再使用的版本。");next.put(t);
                }
                state.put("selected",t);
            }else throw new IOException("不支持的模板操作。");
            state.put("items",next);String payload=state.toString();
            byte[] bytes=new JSONObject().put("payload",payload).put("sha256",hash(payload.getBytes(StandardCharsets.UTF_8))).toString().getBytes(StandardCharsets.UTF_8);
            if(bytes.length>2*1024*1024)throw new IOException("模板资料过大，请先移除不再使用的版本。");
            Path temporary=Files.createTempFile(directory,".minutes-template-",".tmp");
            try{
                try(FileChannel output=FileChannel.open(temporary,StandardOpenOption.WRITE)){ByteBuffer buffer=ByteBuffer.wrap(bytes);while(buffer.hasRemaining())output.write(buffer);output.force(true);}
                Files.move(temporary,file,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            }finally{Files.deleteIfExists(temporary);}
            return result(state);
        }
    }
}
