package com.denzic.companion.app;

import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Independent named AI drafts; included by the existing whole meetings-directory backup. */
final class AiMaterialStore {
    final Path root;
    AiMaterialStore(Path meetings){root=meetings.resolve("ai-materials");}
    static String hash(String text) throws Exception {
        StringBuilder b=new StringBuilder();for(byte v:MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)))b.append(String.format(Locale.ROOT,"%02x",v&255));return b.toString();
    }
    private Path path(String id) throws IOException {if(!id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))throw new IOException("材料编号无效。");return root.resolve(id+".json");}
    JSONObject save(String id,String ownerKey,String title,String question,String body,JSONArray documents,JSONObject result,boolean edited) throws Exception {
        if(title.trim().isEmpty()||title.length()>100||body.trim().isEmpty()||body.codePointCount(0,body.length())>4000||question.length()>4000)throw new IOException("请填写材料名称和正文，正文最多4000字；较长内容可先复制保留。");
        JSONObject value=new JSONObject().put("version",1).put("id",id).put("ownerKey",ownerKey).put("title",title.trim()).put("question",question)
            .put("body",body).put("sources",documents).put("result",result).put("edited",edited).put("createdAt",System.currentTimeMillis());
        Path dest=path(id);Files.createDirectories(root);
        if(Files.exists(dest)){JSONObject old=load(dest);if(old.getString("ownerKey").equals(ownerKey)&&old.getString("title").equals(title.trim())&&old.getString("body").equals(body)&&old.getString("question").equals(question))return old;throw new IOException("已保存的材料与当前输入不同，请重新保存为另一份材料。");}
        byte[] bytes=value.toString().getBytes(StandardCharsets.UTF_8);if(bytes.length>1024*1024)throw new IOException("材料依据较长，请缩小范围后保存。");
        Path temp=Files.createTempFile(root,".material-",".tmp");
        try{try(FileOutputStream out=new FileOutputStream(temp.toFile())){out.write(bytes);out.getFD().sync();}Files.move(temp,dest,StandardCopyOption.ATOMIC_MOVE);}finally{Files.deleteIfExists(temp);}
        return value;
    }
    private JSONObject load(Path p) throws Exception {if(Files.isSymbolicLink(p)||Files.size(p)>1024*1024)throw new IOException("材料无法读取，请保留备份。");JSONObject v=new JSONObject(new String(Files.readAllBytes(p),StandardCharsets.UTF_8));if(v.getInt("version")!=1||!p.equals(path(v.getString("id"))))throw new IOException("材料格式无效。");return v;}
    JSONArray list(String key) throws Exception {
        List<JSONObject> values=new ArrayList<>();if(Files.exists(root)){try(DirectoryStream<Path> paths=Files.newDirectoryStream(root,"*.json")){for(Path p:paths){JSONObject v=load(p);if(key.equals(v.getString("ownerKey")))values.add(v);}}}
        values.sort((a,b)->Long.compare(b.optLong("createdAt"),a.optLong("createdAt")));JSONArray result=new JSONArray();for(JSONObject v:values)result.put(v);return result;
    }
}
