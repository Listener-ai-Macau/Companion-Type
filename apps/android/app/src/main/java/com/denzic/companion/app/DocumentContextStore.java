package com.denzic.companion.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Supplementary originals and extracted text, never ASR or generated facts.
 * Flat key-owned leaves participate in the existing backup and exact purge. */
final class DocumentContextStore {
    static final int MAX_FILE=20*1024*1024,MAX_TEXT_FILE=2*1024*1024,CHUNK=256*1024;
    private final Path directory;private final PlaybackProgress.DirectorySync sync;
    DocumentContextStore(Path directory,PlaybackProgress.DirectorySync sync){this.directory=directory;this.sync=sync;}
    private static void key(String key)throws IOException{if(key==null||!key.matches("[0-9a-f]{24,64}:[0-9a-f]{1,16}:[0-9a-f]{1,16}"))throw new IOException("录音标识无效。");}
    private static void id(String id)throws IOException{try{if(!UUID.fromString(id).toString().equals(id))throw new IllegalArgumentException();}catch(Exception e){throw new IOException("材料标识无效。");}}
    private static String hash(String value)throws Exception{return AiMaterialStore.hash(value);}
    private static String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
    private String prefix(String key)throws Exception{key(key);return hash(key)+".document-";}
    private Path index(String key)throws Exception{key(key);return directory.resolve(hash(key)+".documents.json");}
    private Path safe(String leaf)throws IOException{Path path=directory.resolve(leaf);if(!path.toAbsolutePath().normalize().getParent().equals(directory.toAbsolutePath().normalize())||leaf.contains("/")||leaf.contains("\\")||Files.isSymbolicLink(path)||Files.isSymbolicLink(directory))throw new IOException("材料位置无效，原资料保留。");return path;}
    private static String format(String name)throws IOException{String ext=name.substring(name.lastIndexOf('.')+1).toLowerCase(Locale.ROOT);if(!Arrays.asList("pdf","docx","xlsx","pptx","txt","md","csv").contains(ext))throw new IOException("请选择PDF、DOCX、XLSX、PPTX或纯文字文件，旧版Office请另存后导入。");return ext;}
    private void validateRow(String key,JSONObject row)throws Exception{
        String id=row.getString("id");id(id);String ext=format(row.getString("name"));
        if(!ext.equals(row.getString("format"))||!row.getString("file").equals(prefix(key)+id+"."+ext)||!row.getString("sourceSha256").matches("[0-9a-f]{64}")||row.getLong("bytes")<1||row.getLong("bytes")>MAX_FILE||row.getString("name").length()>200||row.getLong("createdAt")<=0)throw new IOException("材料身份无效，原件保留。");safe(row.getString("file"));
        if(row.has("extraction")){JSONObject x=row.getJSONObject("extraction");String sha=x.getString("sha256");if(!sha.matches("[0-9a-f]{64}")||!x.getString("file").equals(prefix(key)+id+".read-"+sha.substring(0,16)+".json")||x.getLong("bytes")<1||x.getLong("bytes")>MAX_TEXT_FILE||x.getInt("characters")<1||x.getInt("characters")>300000)throw new IOException("材料文字身份无效，原件保留。");safe(x.getString("file"));}
    }
    JSONObject read(String key)throws Exception{synchronized(DocumentContextStore.class){Path p=index(key);safe(p.getFileName().toString());if(!Files.exists(p,LinkOption.NOFOLLOW_LINKS))return new JSONObject().put("contextId",key).put("revision",0).put("rows",new JSONArray());
        try{JSONObject envelope=object(p,256*1024);String body=envelope.getString("body");if(!hash(body).equals(envelope.getString("sha256")))throw new IOException("材料目录校验失败，原件保留。");JSONObject value=new JSONObject(body);if(value.getInt("schema")!=1||!key.equals(value.getString("contextId"))||value.getLong("revision")<1)throw new IOException("材料目录身份不符。");JSONArray rows=value.getJSONArray("rows");if(rows.length()>50)throw new IOException("材料数量无效。");Set<String> seen=new HashSet<>();for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);validateRow(key,row);if(!seen.add(row.getString("id")))throw new IOException("材料标识重复。");}return value;}catch(JSONException e){throw new IOException("材料目录损坏，请先备份后检查；原件仍保留。",e);}
    }}
    private static JSONObject object(Path p,long max)throws Exception{if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.size(p)>max)throw new IOException("材料文件缺失或过大，原件保留。");return new JSONObject(new String(Files.readAllBytes(p),StandardCharsets.UTF_8));}
    private JSONObject expected(String key,long revision)throws Exception{JSONObject value=read(key);if(value.getLong("revision")!=revision)throw new IOException("材料已更新，请重新读取后重试。");return value;}
    private static JSONObject row(JSONObject value,String id)throws Exception{JSONArray rows=value.getJSONArray("rows");for(int i=0;i<rows.length();i++)if(id.equals(rows.getJSONObject(i).getString("id")))return rows.getJSONObject(i);throw new IOException("这份材料已移除，请重新读取。");}
    private void publish(Path temp,Path target,boolean replace)throws Exception{
        // All document writers hold DocumentContextStore.class in this single
        // app process. Android's private-data policy can reject hard links;
        // use the same durable atomic rename as recording notes. A fresh leaf
        // is prechecked while that writer lock remains held.
        if(!replace&&Files.exists(target,LinkOption.NOFOLLOW_LINKS))throw new IOException("材料文件已存在但尚未确认，原文件保留，请重新读取后重试。");
        try{if(replace)Files.move(temp,target,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);else Files.move(temp,target,StandardCopyOption.ATOMIC_MOVE);sync.sync(directory);}
        catch(IOException error){throw new IOException("材料尚未安全保存，原件和已保存内容保留；请重新读取后重试。",error);}
    }
    private void write(String key,JSONObject value)throws Exception{value.put("schema",1);String body=value.toString();byte[] bytes=new JSONObject().put("body",body).put("sha256",hash(body)).toString().getBytes(StandardCharsets.UTF_8);if(bytes.length>256*1024)throw new IOException("材料目录过大。");writeBytes(index(key),bytes,true);}
    private void writeBytes(Path target,byte[] bytes,boolean replace)throws Exception{Files.createDirectories(directory);safe(target.getFileName().toString());Path temp=Files.createTempFile(directory,".document-",".tmp");try{try(FileOutputStream out=new FileOutputStream(temp.toFile())){out.write(bytes);out.getFD().sync();}publish(temp,target,replace);}finally{Files.deleteIfExists(temp);}}
    private Path verified(JSONObject file,int max)throws Exception{Path p=safe(file.getString("file"));long size=file.getLong("bytes");String sha=file.has("sourceSha256")?file.getString("sourceSha256"):file.getString("sha256");if(size<1||size>max||!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.size(p)!=size)throw new IOException("材料文件缺失或大小已变化，原件与目录保留。");MessageDigest hash=MessageDigest.getInstance("SHA-256");try(InputStream in=Files.newInputStream(p)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)hash.update(b,0,n);}if(!hex(hash.digest()).equals(sha))throw new IOException("材料文件校验失败，原件与目录保留。");return p;}
    JSONObject add(String key,long revision,String id,String name,InputStream input)throws Exception{synchronized(DocumentContextStore.class){id(id);String ext=format(name);String display=name.replaceAll("[\\r\\n\\x00-\\x1f]"," ");if(display.length()>200)throw new IOException("文件名称过长，请改名后重试。");JSONObject value=read(key);JSONObject previous=null;try{previous=row(value,id);}catch(IOException absent){}if(previous==null){value=expected(key,revision);if(value.getJSONArray("rows").length()>=50)throw new IOException("每场最多50份材料，请整理后再导入。");}
        Files.createDirectories(directory);Path target=safe(prefix(key)+id+"."+ext),temp=Files.createTempFile(directory,".document-",".tmp");try{long count=0;MessageDigest digest=MessageDigest.getInstance("SHA-256");try(FileOutputStream out=new FileOutputStream(temp.toFile())){byte[] b=new byte[65536];int n;while((n=input.read(b))!=-1){if(n==0)continue;count+=n;if(count>MAX_FILE)throw new IOException("文档超过20MB，请拆分后导入。");out.write(b,0,n);digest.update(b,0,n);}out.getFD().sync();}if(count==0)throw new IOException("所选文档为空。");String sha=hex(digest.digest());JSONObject entry=new JSONObject().put("id",id).put("name",display).put("format",ext).put("file",target.getFileName().toString()).put("sourceSha256",sha).put("bytes",count).put("createdAt",System.currentTimeMillis());validateRow(key,entry);
            if(previous!=null){if(!previous.getString("sourceSha256").equals(sha)||!previous.getString("name").equals(display)||previous.getLong("bytes")!=count)throw new IOException("这个材料标识已用于其它文件，请重新导入。");verified(previous,MAX_FILE);return value;}
            if(Files.exists(target,LinkOption.NOFOLLOW_LINKS))verified(entry,MAX_FILE);else publish(temp,target,false);
            value.getJSONArray("rows").put(entry);value.put("revision",revision+1);write(key,value);return value;
        }finally{Files.deleteIfExists(temp);}
    }}
    JSONObject chunk(String key,long revision,String id,int offset)throws Exception{synchronized(DocumentContextStore.class){JSONObject entry=row(expected(key,revision),id);if(offset<0||offset>=entry.getLong("bytes")||offset%CHUNK!=0)throw new IOException("材料读取位置无效。");Path p=offset==0?verified(entry,MAX_FILE):safe(entry.getString("file"));if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.size(p)!=entry.getLong("bytes"))throw new IOException("材料在读取期间变化，请重试。");byte[] bytes=new byte[(int)Math.min(CHUNK,entry.getLong("bytes")-offset)];try(RandomAccessFile in=new RandomAccessFile(p.toFile(),"r")){in.seek(offset);in.readFully(bytes);}return new JSONObject().put("offset",offset).put("base64",Base64.getEncoder().encodeToString(bytes)).put("sourceSha256",entry.getString("sourceSha256"));}}
    static void validateExtraction(JSONObject value,JSONObject entry)throws Exception{
        if(value.getInt("schema")!=1||!value.getString("sourceSha256").equals(entry.getString("sourceSha256"))||!value.getString("format").equals(entry.getString("format"))||!value.getString("readerVersion").matches("[0-9.-]{1,40}"))throw new IOException("提取文字与原件不符，未替换已保存内容。");
        JSONArray sections=value.getJSONArray("sections"),warnings=value.getJSONArray("warnings");if(sections.length()<1||sections.length()>300||warnings.length()>50)throw new IOException("材料文字结构超出范围。");int characters=0;int[] cells={0};Set<String> seen=new HashSet<>();for(int i=0;i<sections.length();i++){JSONObject s=sections.getJSONObject(i);if(!s.getString("id").matches("part-[1-9][0-9]{0,2}")||!seen.add(s.getString("id"))||s.getString("label").length()>160)throw new IOException("材料文字结构无效。");characters+=s.getString("text").length();if(characters>300000)throw new IOException("提取文字超过30万字符。");if(s.has("tableRows")){if(!value.getString("format").equals("xlsx"))throw new IOException("表格布局与材料格式不符。");validateTable(s,cells);}}for(int i=0;i<warnings.length();i++)if(warnings.getString(i).length()>500)throw new IOException("材料提示过长。");if(characters<1||characters!=value.getInt("characters"))throw new IOException("材料文字长度无法确认。");
    }
    private static void validateTable(JSONObject section,int[] count)throws Exception{
        JSONArray rows=section.getJSONArray("tableRows");if(rows.length()<1||rows.length()>10000)throw new IOException("表格行数超出读取范围。");long previousRow=0;StringBuilder canonical=new StringBuilder();
        for(int i=0;i<rows.length();i++){
            JSONObject row=rows.getJSONObject(i);Object raw=row.get("row");if(!(raw instanceof Integer)&&!(raw instanceof Long))throw new IOException("表格行号无效。");long number=((Number)raw).longValue();if(number<=previousRow||number>1048576)throw new IOException("表格行号顺序无效。");previousRow=number;
            JSONArray cells=row.getJSONArray("cells");if(cells.length()<1||cells.length()>16384)throw new IOException("表格列数超出读取范围。");int previousColumn=0;if(i>0)canonical.append('\n');
            for(int j=0;j<cells.length();j++){
                JSONObject cell=cells.getJSONObject(j);String column=cell.getString("column"),text=cell.getString("text");if(!column.matches("[A-Z]{1,3}")||text.isEmpty()||++count[0]>100000)throw new IOException("表格单元格无效。");int position=0;for(int k=0;k<column.length();k++)position=position*26+column.charAt(k)-64;
                if(position<=previousColumn||position>16384)throw new IOException("表格列顺序无效。");previousColumn=position;if(j>0)canonical.append('\t');canonical.append(column).append(number).append(": ").append(text);if(canonical.length()>300000)throw new IOException("表格文字超出范围。");
            }
        }
        if(!canonical.toString().equals(section.getString("text")))throw new IOException("表格布局与保留的原文字不符，未替换已保存内容。");
    }
    JSONObject saveExtraction(String key,long revision,String id,JSONObject extracted)throws Exception{synchronized(DocumentContextStore.class){JSONObject value=expected(key,revision),entry=row(value,id);verified(entry,MAX_FILE);validateExtraction(extracted,entry);byte[] bytes=extracted.toString().getBytes(StandardCharsets.UTF_8);if(bytes.length>MAX_TEXT_FILE)throw new IOException("提取文字过大，原件保留。");String sha=hex(MessageDigest.getInstance("SHA-256").digest(bytes));String file=prefix(key)+id+".read-"+sha.substring(0,16)+".json";JSONObject info=new JSONObject().put("file",file).put("sha256",sha).put("bytes",bytes.length).put("characters",extracted.getInt("characters")).put("readerVersion",extracted.getString("readerVersion"));Path p=safe(file);if(Files.exists(p,LinkOption.NOFOLLOW_LINKS))verified(info,MAX_TEXT_FILE);else writeBytes(p,bytes,false);entry.put("extraction",info);value.put("revision",revision+1);write(key,value);return value;}}
    JSONObject extraction(String key,long revision,String id)throws Exception{synchronized(DocumentContextStore.class){JSONObject entry=row(expected(key,revision),id);verified(entry,MAX_FILE);if(!entry.has("extraction"))throw new IOException("原件已保存，尚未提取文字。");JSONObject result=object(verified(entry.getJSONObject("extraction"),MAX_TEXT_FILE),MAX_TEXT_FILE);validateExtraction(result,entry);return result;}}
    Path original(String key,long revision,String id)throws Exception{synchronized(DocumentContextStore.class){return verified(row(expected(key,revision),id),MAX_FILE);}}
    JSONObject remove(String key,long revision,String id)throws Exception{synchronized(DocumentContextStore.class){JSONObject value=expected(key,revision);row(value,id);JSONArray rows=value.getJSONArray("rows"),next=new JSONArray();for(int i=0;i<rows.length();i++)if(!id.equals(rows.getJSONObject(i).getString("id")))next.put(rows.getJSONObject(i));value.put("rows",next).put("revision",revision+1);write(key,value);return value;}}
    JSONObject aiDocument(String key,String id)throws Exception{synchronized(DocumentContextStore.class){JSONObject value=read(key),entry=row(value,id),extracted=extraction(key,value.getLong("revision"),id);JSONArray sections=extracted.getJSONArray("sections");StringBuilder text=new StringBuilder("[用户提供的补充材料，不是会议录音或已作出的决定。]\n");for(int i=0;i<sections.length();i++){JSONObject s=sections.getJSONObject(i);text.append(s.getString("label")).append('\n').append(s.getString("text")).append('\n');}return new JSONObject().put("id","document:"+key+":"+id).put("title","补充材料 · "+entry.getString("name")).put("kind","supplement").put("text",text.toString()).put("binding",hash(key+":"+id+":"+entry.getJSONObject("extraction").getString("sha256")));}}
}
