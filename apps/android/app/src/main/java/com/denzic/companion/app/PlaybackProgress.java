package com.denzic.companion.app;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.Locale;
import org.json.JSONObject;

/** Per-library, descriptor-bound playback metadata. Never changes audio or text. */
final class PlaybackProgress {
    interface DirectorySync { void sync(Path directory)throws IOException; }
    private final Path root;
    private final DirectorySync sync;
    PlaybackProgress(Path meetings,DirectorySync sync){this.root=meetings.resolve("playback");this.sync=sync;}
    static boolean validSpeed(double speed){return speed==.75||speed==1||speed==1.25||speed==1.5||speed==1.75||speed==2;}
    private Path file(String key)throws Exception{
        StringBuilder id=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8)))id.append(String.format(Locale.ROOT,"%02x",b&255));
        if(Files.isSymbolicLink(root)||Files.exists(root,LinkOption.NOFOLLOW_LINKS)&&!Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS))throw new IOException("续听位置目录暂时无法读取，原录音仍可回听。");
        Path p=root.resolve(id+".json");if(Files.isSymbolicLink(p))throw new IOException("续听位置无法读取，原录音仍保留。");return p;
    }
    JSONObject load(String key,String binding,long durationMs)throws Exception{
        JSONObject empty=new JSONObject().put("positionMs",0).put("speed",1).put("completed",false).put("saved",false);
        try{
            Path p=file(key);if(!Files.exists(p))return empty;
            if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.size(p)>4096)throw new IOException("Invalid checkpoint size");
            JSONObject v=new JSONObject(new String(Files.readAllBytes(p),StandardCharsets.UTF_8));
            Object position=v.get("positionMs");if(!(position instanceof Integer||position instanceof Long))throw new IOException("Invalid checkpoint position");
            long ms=((Number)position).longValue();double speed=v.getDouble("speed");
            if(v.getInt("version")!=1||!validSpeed(speed)||ms<0||ms>9007199254740991L||!(v.get("completed") instanceof Boolean))throw new IOException("Invalid checkpoint");
            if(!binding.equals(v.getString("binding")))return empty.put("sourceChanged",true);
            if(durationMs>0&&ms>durationMs)return empty.put("sourceChanged",true);
            return new JSONObject().put("positionMs",v.getBoolean("completed")?0:ms).put("speed",speed).put("completed",v.getBoolean("completed")).put("saved",true);
        }catch(Exception error){return empty.put("warning","续听位置暂不可读，将从头回听；原录音和文字仍保留。");}
    }
    void save(String key,String binding,long positionMs,double speed,boolean completed)throws Exception{
        if(positionMs<0||positionMs>9007199254740991L||!validSpeed(speed)||!binding.matches("[0-9a-f]{64}"))throw new IOException("续听位置无效，原录音仍保留。");
        Path p=file(key);Files.createDirectories(root);sync.sync(root.getParent());
        byte[] bytes=new JSONObject().put("version",1).put("binding",binding).put("positionMs",completed?0:positionMs).put("speed",speed).put("completed",completed).toString().getBytes(StandardCharsets.UTF_8);
        Path temp=Files.createTempFile(root,"progress-",".tmp");
        try{
            try(FileChannel channel=FileChannel.open(temp,StandardOpenOption.WRITE)){ByteBuffer buffer=ByteBuffer.wrap(bytes);while(buffer.hasRemaining())channel.write(buffer);channel.force(true);}
            Files.move(temp,p,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);sync.sync(root);
        }finally{Files.deleteIfExists(temp);}
    }
}
