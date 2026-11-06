package com.denzic.companion.app;

import org.json.*;
import java.io.*;
import java.nio.channels.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Local-library metadata only. No Bluetooth, model, network or device deletion. */
final class LocalRecordingLifecycle {
    private final Path appRoot,recordings,meetings,directory;
    interface Deleter{boolean remove(Path path)throws IOException;}
    interface DirectorySync{void sync(Path path)throws IOException;}
    private final Deleter delete;
    private final DirectorySync sync;
    LocalRecordingLifecycle(Path appRoot,Path recordings,Path meetings,DirectorySync sync){
        this(appRoot,recordings,meetings,sync,Files::deleteIfExists);
    }
    LocalRecordingLifecycle(Path appRoot,Path recordings,Path meetings,DirectorySync sync,Deleter delete){
        this.appRoot=appRoot.toAbsolutePath().normalize();
        this.recordings=recordings.toAbsolutePath().normalize();this.meetings=meetings.toAbsolutePath().normalize();
        directory=this.meetings.resolve("recording-lifecycle");this.delete=delete;this.sync=sync;
    }
    private interface Action<T>{T run()throws Exception;}
    private void managedPath(Path p)throws IOException{
        if(!p.startsWith(appRoot)||p.equals(appRoot))throw new IOException("资料路径越界，原文件保留。");
        // Context supplies the trusted app root. Android may itself alias an
        // ancestor (/data/user/0); only links within our app can redirect data.
        for(Path part=p;part!=null&&part.startsWith(appRoot);part=part.getParent())
            if(Files.isSymbolicLink(part))throw new IOException("资料目录含链接，已保留原文件，请先检查。");
    }
    private void safeDirectory(Path p)throws IOException{
        managedPath(p);Files.createDirectories(p);managedPath(p);
        if(!Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS))throw new IOException("资料目录无法读取。");
    }
    private <T>T locked(Action<T> action)throws Exception{
        safeDirectory(meetings);safeDirectory(directory);
        Path path=meetings.resolve(".recording-lifecycle.lock");
        if(Files.isSymbolicLink(path))throw new IOException("资料操作锁无效，原文件保留。");
        try(FileChannel channel=FileChannel.open(path,StandardOpenOption.CREATE,StandardOpenOption.WRITE)){
            FileLock lock;try{lock=channel.tryLock();}catch(OverlappingFileLockException e){throw new IOException("录音资料正在更新，请稍后重试。",e);}
            if(lock==null)throw new IOException("录音资料正在更新，请稍后重试。");
            try{return action.run();}finally{lock.release();}
        }
    }
    static String hash(String value)throws Exception{
        return hex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
    }
    private static String hex(byte[] bytes){StringBuilder b=new StringBuilder();for(byte n:bytes)b.append(String.format(Locale.ROOT,"%02x",n&255));return b.toString();}
    private static void key(String value)throws IOException{
        if(value==null||!value.matches("[0-9a-f]{16,64}:[0-9a-f]{1,16}:[0-9a-f]{1,16}"))throw new IOException("录音身份无效，请重新打开录音。");
    }
    private Path statePath(String key)throws Exception{key(key);return directory.resolve(hash(key)+".state.json");}
    private Path planPath(String key)throws Exception{key(key);return directory.resolve(hash(key)+".purge.json");}
    private static JSONObject object(Path p,int max)throws Exception{
        if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.size(p)>max)throw new IOException("管理资料无法读取，原文件保留。");
        String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(Files.readAllBytes(p))).toString();
        return new JSONObject(text);
    }
    private void write(Path dest,JSONObject value)throws Exception{
        byte[] bytes=value.toString().getBytes(StandardCharsets.UTF_8);
        if(bytes.length>2*1024*1024)throw new IOException("管理资料过长，原文件保留。");
        if(Files.isSymbolicLink(dest))throw new IOException("管理资料含链接，原文件保留。");
        Path temp=Files.createTempFile(directory,".lifecycle-",".tmp");
        try{
            try(FileOutputStream out=new FileOutputStream(temp.toFile())){out.write(bytes);out.getFD().sync();}
            Files.move(temp,dest,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            sync.sync(directory);sync.sync(meetings);
        }finally{Files.deleteIfExists(temp);}
    }
    private JSONObject read(String key)throws Exception{
        Path p=statePath(key);
        if(!Files.exists(p,LinkOption.NOFOLLOW_LINKS))return new JSONObject().put("version",1).put("key",key).put("revision",0).put("protected",false).put("trashedAt",0).put("purging",false);
        JSONObject s=object(p,8192);
        if(s.getInt("version")!=1||!key.equals(s.getString("key"))||s.getLong("revision")<1||s.getLong("revision")>=9007199254740990L||s.getLong("trashedAt")<0
            ||!(s.get("protected") instanceof Boolean)||!(s.get("purging") instanceof Boolean)
            ||(s.getBoolean("protected")&&s.getLong("trashedAt")!=0))throw new IOException("删除与保护资料无法核对，原文件保留，请先备份。");
        return s;
    }
    JSONObject get(String key)throws Exception{return locked(()->read(key));}
    void requireVisible(String key)throws Exception{
        JSONObject state=get(key);if(state.getLong("trashedAt")!=0)throw new IOException("录音已在回收站中，请先恢复后再打开、编辑或分享。");
    }
    JSONObject change(String key,long expected,String action,String title)throws Exception{return locked(()->{
        JSONObject s=read(key);if(s.getLong("revision")!=expected)throw new IOException("录音管理状态已变化，请刷新后重试。");
        if(s.getBoolean("purging"))throw new IOException("上次永久清除尚未完成，部分文件可能已移除，请继续清除。");
        switch(action){
            case "protect":if(s.getLong("trashedAt")!=0)throw new IOException("请先恢复录音再设置保护。");s.put("protected",true);break;
            case "unprotect":s.put("protected",false);break;
            case "trash":
                if(s.getBoolean("protected"))throw new IOException("录音已受保护，请先解除保护。");
                if(s.getLong("trashedAt")!=0)throw new IOException("录音已经在回收站中。");
                if(title==null||title.isEmpty()||title.length()>100)throw new IOException("请重新读取录音名称。");
                s.put("title",title).put("trashedAt",System.currentTimeMillis());break;
            case "restore":if(s.getLong("trashedAt")==0)throw new IOException("录音不在回收站中。");s.put("trashedAt",0);break;
            default:throw new IOException("不支持的录音管理操作。");
        }
        s.remove("purged");s.put("revision",expected+1);write(statePath(key),s);
        Files.deleteIfExists(planPath(key));return s;
    });}
    JSONObject trash()throws Exception{return locked(()->{
        List<JSONObject> rows=new ArrayList<>();int problems=0;
        try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,"*.state.json")){
            for(Path p:files){try{JSONObject raw=object(p,8192);String k=raw.getString("key");if(!p.equals(statePath(k)))throw new IOException("管理资料身份不符");JSONObject s=read(k);if(s.getLong("trashedAt")!=0)rows.add(s);}catch(Exception error){problems++;}}
        }
        rows.sort((a,b)->Long.compare(b.optLong("trashedAt"),a.optLong("trashedAt")));
        return new JSONObject().put("rows",new JSONArray(rows)).put("problems",problems);
    });}
    private Path resolve(String scope,String name)throws Exception{
        if(!scope.equals("recordings")&&!scope.equals("meetings"))throw new IOException("清除范围无效。");
        if(name==null||name.isEmpty()||name.indexOf('\\')>=0||name.indexOf(':')>=0)throw new IOException("清除路径无效。");
        for(String part:name.split("/",-1))if(part.isEmpty()||part.equals(".")||part.equals(".."))throw new IOException("清除路径无效。");
        Path root=scope.equals("recordings")?recordings:meetings;Path p=root.resolve(name).normalize();
        if(!p.startsWith(root)||p.equals(root))throw new IOException("清除路径越界。");
        managedPath(p);
        return p;
    }
    private static String fileHash(Path path)throws Exception{
        MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] b=new byte[32768];
        try(InputStream in=Files.newInputStream(path)){int n;while((n=in.read(b))!=-1)digest.update(b,0,n);}return hex(digest.digest());
    }
    private void add(JSONArray rows,String scope,Path root,Path p)throws Exception{
        String name=root.relativize(p).toString().replace(File.separatorChar,'/');resolve(scope,name);
        if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS))throw new IOException("清除范围含非普通文件，原文件保留。");
        if(rows.length()>=10000)throw new IOException("录音文件过多，请先备份后检查。");
        rows.put(new JSONObject().put("scope",scope).put("path",name).put("bytes",Files.size(p)).put("sha256",fileHash(p)));
    }
    private JSONObject inventory(String key)throws Exception{
        safeDirectory(recordings);String prefix=key.replace(':','-')+"-",digest=hash(key);JSONArray files=new JSONArray();int retained=0;
        try(DirectoryStream<Path> entries=Files.newDirectoryStream(recordings)){
            for(Path p:entries){String n=p.getFileName().toString();
                if(n.matches(java.util.regex.Pattern.quote(prefix)+"[0-9]+-[0-9]+-[0-9a-f]{64}\\.(cop1|part|meta)"))add(files,"recordings",recordings,p);
                else if(n.startsWith("damaged-"))retained++;
            }
        }
        try(DirectoryStream<Path> entries=Files.newDirectoryStream(meetings)){
            for(Path p:entries){String n=p.getFileName().toString();if(n.startsWith(digest+".")&&!n.equals(digest+".lock"))add(files,"meetings",meetings,p);else if(n.startsWith("damaged-meeting-"))retained++;}
        }
        Path translations=meetings.resolve("translations");
        if(Files.exists(translations,LinkOption.NOFOLLOW_LINKS)){
            safeDirectory(translations);try(DirectoryStream<Path> entries=Files.newDirectoryStream(translations,digest+".translation*")){for(Path p:entries)add(files,"meetings",meetings,p);}
        }
        Path materials=meetings.resolve("ai-materials");
        if(Files.exists(materials,LinkOption.NOFOLLOW_LINKS)){
            safeDirectory(materials);try(DirectoryStream<Path> entries=Files.newDirectoryStream(materials,"*.json")){
                for(Path p:entries){JSONObject v=object(p,1024*1024);if(key.equals(v.getString("ownerKey")))add(files,"meetings",meetings,p);}
            }
        }
        return new JSONObject().put("version",1).put("key",key).put("files",files).put("retainedUnassigned",retained);
    }
    private void validate(JSONObject plan,boolean allowMissing)throws Exception{
        if(plan.getInt("version")!=1)throw new IOException("清除核对资料无效。");
        String key=plan.getString("key"),prefix=key.replace(':','-')+"-",digest=hash(key);key(key);
        JSONArray files=plan.getJSONArray("files");if(files.length()>10000)throw new IOException("清除核对资料过长。");Set<Path> seen=new HashSet<>();
        for(int i=0;i<files.length();i++){
            JSONObject row=files.getJSONObject(i);String scope=row.getString("scope"),name=row.getString("path");
            boolean owned=scope.equals("recordings")?name.matches(java.util.regex.Pattern.quote(prefix)+"[0-9]+-[0-9]+-[0-9a-f]{64}\\.(cop1|part|meta)"):
                name.startsWith(digest+".")&&!name.contains("/")&&!name.equals(digest+".lock")||name.startsWith("translations/"+digest+".translation");
            if(scope.equals("meetings")&&name.matches("ai-materials/[0-9a-f-]{36}\\.json")){
                Path p=resolve(scope,name);owned=!Files.exists(p,LinkOption.NOFOLLOW_LINKS)&&allowMissing||key.equals(object(p,1024*1024).getString("ownerKey"));
            }
            if(!owned)throw new IOException("清除文件身份不符，原文件保留。");
            Path p=resolve(scope,name);if(!seen.add(p))throw new IOException("清除核对资料重复。");
            if(!Files.exists(p,LinkOption.NOFOLLOW_LINKS)&&allowMissing)continue;
            if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.size(p)!=row.getLong("bytes")||!fileHash(p).equals(row.getString("sha256")))throw new IOException("待清除文件已变化，请重新核对；尚未继续删除。");
        }
    }
    JSONObject preparePurge(String key,long expected)throws Exception{return locked(()->{
        JSONObject s=read(key);if(s.getLong("revision")!=expected||s.getLong("trashedAt")==0||s.getBoolean("protected"))throw new IOException("回收站状态已变化，请刷新后重试。");
        JSONObject plan=s.getBoolean("purging")?object(planPath(key),2*1024*1024):inventory(key);
        if(!key.equals(plan.getString("key")))throw new IOException("清除核对身份不符。");validate(plan,s.getBoolean("purging"));
        plan.put("revision",expected).put("token",UUID.randomUUID().toString());write(planPath(key),plan);return offer(s,plan);
    });}
    private JSONObject offer(JSONObject state,JSONObject plan)throws Exception{
        long bytes=0;JSONArray files=plan.getJSONArray("files");for(int i=0;i<files.length();i++)bytes=Math.addExact(bytes,files.getJSONObject(i).getLong("bytes"));
        return new JSONObject().put("key",state.getString("key")).put("title",state.optString("title","未命名录音")).put("revision",state.getLong("revision"))
            .put("token",plan.getString("token")).put("files",files.length()).put("bytes",bytes).put("retainedUnassigned",plan.optInt("retainedUnassigned"));
    }
    JSONObject purge(String key,long expected,String token)throws Exception{return locked(()->{
        JSONObject s=read(key),plan=object(planPath(key),2*1024*1024);
        if(s.getLong("revision")!=expected||s.getLong("trashedAt")==0||s.getBoolean("protected")||!key.equals(plan.getString("key"))||plan.getLong("revision")!=expected||!plan.getString("token").equals(token))throw new IOException("清除确认已过期，请重新核对。");
        validate(plan,s.getBoolean("purging")); // Entire set before the first irreversible operation.
        JSONObject result=offer(s,plan);s.put("purging",true).put("revision",expected+1);write(statePath(key),s);
        JSONArray files=plan.getJSONArray("files");
        // Audio metadata is removed after audio bytes, so a partial failure is not
        // silently treated as a complete, playable recording. Persisted plan can retry.
        List<JSONObject> ordered=new ArrayList<>();for(int i=0;i<files.length();i++)ordered.add(files.getJSONObject(i));
        ordered.sort(Comparator.comparing(v->v.optString("path").endsWith(".meta")));
        Set<Path> parents=new HashSet<>();
        for(JSONObject row:ordered){Path path=resolve(row.getString("scope"),row.getString("path"));delete.remove(path);parents.add(path.getParent());}
        for(Path parent:parents)sync.sync(parent);
        // Retain only identity/revision so an old revision-zero request cannot
        // affect a later re-import of the same immutable recording (ABA).
        s.remove("title");s.put("trashedAt",0).put("purging",false).put("purged",true).put("revision",expected+2);
        write(statePath(key),s);
        try{Files.deleteIfExists(planPath(key));sync.sync(directory);}catch(IOException cleanup){result.put("cleanupWarning",true);}
        return result.put("purged",true);
    });}
}
