package com.denzic.companion.app;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.text.Normalizer;
import java.util.*;
import org.json.*;

/** One atomic, revisioned metadata update for a selection. Audio and AI sources
 * are never edited. The existing full-library backup carries this local file. */
final class RecordingOrganization {
    private static final long LIMIT=4L*1024*1024,MAX_REV=9007199254740000L;
    private final Path directory,file;
    interface DirectorySync{void sync(Path path)throws IOException;}
    private final DirectorySync sync;
    RecordingOrganization(Path directory,DirectorySync sync){
        this.directory=directory.toAbsolutePath().normalize();file=this.directory.resolve("recording-organization.json");this.sync=sync;
    }
    interface Work<T>{T run()throws Exception;}
    private static String hash(String value)throws Exception{
        byte[] bytes=java.security.MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();
    }
    private <T>T locked(Work<T> work)throws Exception{
        synchronized(RecordingOrganization.class){
            if(Files.isSymbolicLink(directory))throw new IOException("分类资料目录无效，原资料保留。");
            Files.createDirectories(directory);Path lock=directory.resolve(".recording-organization.lock");
            if(Files.isSymbolicLink(lock)||Files.isSymbolicLink(file))throw new IOException("分类资料含链接，原资料保留。");
            try(FileChannel channel=FileChannel.open(lock,StandardOpenOption.CREATE,StandardOpenOption.WRITE)){
                FileLock held;try{held=channel.tryLock();}catch(OverlappingFileLockException e){throw new IOException("分类正在更新，请稍后重试。",e);}
                if(held==null)throw new IOException("分类正在更新，请稍后重试。");
                try{return work.run();}finally{held.release();}
            }
        }
    }
    private static void key(String key)throws IOException{
        if(key==null||!key.matches("[0-9a-f]{16,64}:[0-9a-f]{1,16}:[0-9a-f]{1,16}"))throw new IOException("分类录音标识无效，请刷新后重新选择。");
    }
    private static long revision(JSONObject value)throws Exception{
        Object raw=value.get("revision");if(!(raw instanceof Number))throw new IOException("分类版本无效。");
        Number n=(Number)raw;long v=n.longValue();if(v<0||v>=MAX_REV||n.doubleValue()!=v)throw new IOException("分类版本无效。");return v;
    }
    static String folder(String input)throws IOException{
        String value=Normalizer.normalize(input==null?"":input.trim(),Normalizer.Form.NFC);
        if(value.isEmpty())return "";
        if(value.length()>160||value.startsWith("/")||value.endsWith("/")||value.indexOf('\\')>=0||value.indexOf(':')>=0||value.chars().anyMatch(Character::isISOControl))throw new IOException("文件夹名称最长160字，可用斜杠分层，不能包含控制字符或反斜杠。");
        String[] parts=value.split("/",-1);if(parts.length>6)throw new IOException("文件夹最多支持6层。");
        List<String> clean=new ArrayList<>();for(String part:parts){String p=part.trim();if(p.isEmpty()||p.equals(".")||p.equals("..")||p.length()>60)throw new IOException("每层文件夹需为1到60字，不能使用点或空层级。");clean.add(p);}return String.join("/",clean);
    }
    static JSONArray tags(JSONArray input)throws Exception{
        if(input==null||input.length()>20)throw new IOException("每条录音最多20个标签，每个标签不超过40字。");
        JSONArray clean=new JSONArray();Set<String> seen=new HashSet<>();
        for(int i=0;i<input.length();i++){
            Object raw=input.get(i);if(!(raw instanceof String))throw new IOException("标签内容无效。");
            String value=Normalizer.normalize(((String)raw).trim(),Normalizer.Form.NFC);
            if(value.isEmpty()||value.length()>40||value.chars().anyMatch(Character::isISOControl))throw new IOException("标签需为1到40字，不能包含换行或控制字符。");
            if(seen.add(value.toLowerCase(Locale.ROOT)))clean.put(value);
        }return clean;
    }
    private JSONObject readUnlocked()throws Exception{
        if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))return new JSONObject().put("schema",1).put("revision",0).put("entries",new JSONObject());
        if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)||Files.size(file)>LIMIT)throw new IOException("分类资料无法读取，原文件保留，请先备份。");
        try{
            String raw=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(Files.readAllBytes(file))).toString();
            JSONObject envelope=new JSONObject(raw);String body=envelope.getString("body");
            if(!hash(body).equals(envelope.getString("sha256")))throw new IOException("分类资料校验失败，原文件保留，请先备份后检查。");
            JSONObject value=new JSONObject(body);if(value.getInt("schema")!=1||revision(value)<1)throw new IOException("分类资料版本无效。");
            JSONObject entries=value.getJSONObject("entries");if(entries.length()>10000)throw new IOException("分类条目超过支持范围。");
            Iterator<String> ids=entries.keys();while(ids.hasNext()){String id=ids.next();
                key(id);JSONObject row=entries.getJSONObject(id);String f=row.getString("folder");JSONArray t=row.getJSONArray("tags");
                if(!folder(f).equals(f)||!tags(t).toString().equals(t.toString()))throw new IOException("分类内容无法核对，原文件保留。");
            }return value;
        }catch(JSONException|CharacterCodingException e){throw new IOException("分类资料损坏，原文件保留，请先备份后检查。",e);}
    }
    JSONObject read()throws Exception{return locked(this::readUnlocked);}
    static JSONObject item(JSONObject snapshot,String key)throws Exception{
        key(key);JSONObject value=snapshot.getJSONObject("entries").optJSONObject(key);
        return value==null?new JSONObject().put("folder","").put("tags",new JSONArray()):new JSONObject(value.toString());
    }
    private void write(JSONObject value)throws Exception{
        String body=value.toString();byte[] bytes=new JSONObject().put("body",body).put("sha256",hash(body)).toString().getBytes(StandardCharsets.UTF_8);
        if(bytes.length>LIMIT)throw new IOException("分类资料过大，本次未写入，请减少分类内容。");
        Path temp=Files.createTempFile(directory,".organization-",".tmp");
        try{
            try(FileChannel out=FileChannel.open(temp,StandardOpenOption.WRITE)){ByteBuffer buffer=ByteBuffer.wrap(bytes);while(buffer.hasRemaining())out.write(buffer);out.force(true);}
            Files.move(temp,file,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);sync.sync(directory);
        }finally{Files.deleteIfExists(temp);}
    }
    JSONObject change(long expected,JSONArray keys,String action,String destination,JSONArray labels,Set<String> visible)throws Exception{return locked(()->{
        JSONObject value=readUnlocked();long rev=revision(value);if(rev!=expected)throw new IOException("分类已更新，请重新读取；当前选择和输入仍保留。");
        if(keys.length()==0||keys.length()>500)throw new IOException("请选择1到500条录音。");
        Set<String> selected=new LinkedHashSet<>();for(int i=0;i<keys.length();i++){String id=keys.getString(i);key(id);if(!selected.add(id)||!visible.contains(id))throw new IOException("所选录音已变化或包含重复项目，本批未修改，请刷新后重选。");}
        if(!Arrays.asList("move","setTags","addTags","removeTags").contains(action))throw new IOException("不支持的分类操作。");
        String target=action.equals("move")?folder(destination):"";JSONArray clean=action.equals("move")?new JSONArray():tags(labels);
        JSONObject entries=value.getJSONObject("entries");boolean changed=false;
        for(String id:selected){
            JSONObject old=item(value,id),next=new JSONObject(old.toString());
            if(action.equals("move"))next.put("folder",target);
            else if(action.equals("setTags"))next.put("tags",new JSONArray(clean.toString()));
            else if(action.equals("addTags")){JSONArray combined=new JSONArray(old.getJSONArray("tags").toString());Set<String> present=new HashSet<>();for(int i=0;i<combined.length();i++)present.add(combined.getString(i).toLowerCase(Locale.ROOT));for(int i=0;i<clean.length();i++)if(present.add(clean.getString(i).toLowerCase(Locale.ROOT))){if(combined.length()>=20)throw new IOException("所选录音添加后会超过20个标签，本批未写入。");combined.put(clean.getString(i));}next.put("tags",combined);}
            else{Set<String> removed=new HashSet<>();for(int i=0;i<clean.length();i++)removed.add(clean.getString(i).toLowerCase(Locale.ROOT));JSONArray kept=new JSONArray();JSONArray before=old.getJSONArray("tags");for(int i=0;i<before.length();i++)if(!removed.contains(before.getString(i).toLowerCase(Locale.ROOT)))kept.put(before.getString(i));next.put("tags",kept);}
            if(!old.toString().equals(next.toString())){changed=true;if(next.getString("folder").isEmpty()&&next.getJSONArray("tags").length()==0)entries.remove(id);else entries.put(id,next);}
        }
        if(entries.length()>10000)throw new IOException("分类条目超过支持范围，本批未写入。");
        if(changed){value.put("revision",rev+1);write(value);}return value;
    });}
    void remove(String key)throws Exception{locked(()->{
        key(key);JSONObject value=readUnlocked(),entries=value.getJSONObject("entries");if(entries.has(key)){entries.remove(key);value.put("revision",revision(value)+1);write(value);}return null;
    });}
}
