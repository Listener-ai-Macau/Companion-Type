package com.denzic.companion.app;

import com.denzic.companion.mobile.ImportedAudio;
import java.io.*;
import java.nio.*;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** Prepare audio and its source map in one private directory, then publish the
 * entire ordinary imported recording with a single atomic rename. No original
 * record, transcript, bookmark, note or minutes file is ever rewritten/copied.
 * Caller owns the private stage, recording leases and library selection lock.
 */
final class DerivedAudioPublication {
 static final long PART_FRAMES=57_600_000L,MAX_ORIGINAL_BYTES=2L*1024*1024*1024;
 private static final int BUFFER=65536,MANIFEST_LIMIT=65536;
 interface Guard {void revalidate()throws IOException;}
 static final class Prepared {
  final Path directory;final String key;final long frames;final String fingerprint;
  Prepared(Path directory,ImportedAudio audio){this.directory=directory;key=audio.key;frames=audio.samples;fingerprint=ImportedAudio.hash(audio.fingerprint());}
 }
 private static IOException invalid(String text){return new IOException(text);}
 private static void privateDirectory(Path p)throws IOException {if(p==null||Files.isSymbolicLink(p)||!Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS))throw invalid("编辑保存目录尚未就绪。");}
 private static void budget(Path directory,long bytes)throws IOException {if(directory.toFile().getUsableSpace()<bytes+16L*1024*1024)throw invalid("本机存储空间不足，原录音未改变，请腾出空间后重试。");}
 private static void write(FileChannel out,ByteBuffer b)throws IOException {while(b.hasRemaining())if(out.write(b)<=0)throw invalid("派生录音未完整写入，请检查存储空间。");}
 private static ByteBuffer header(long frames){long bytes=frames*2;ByteBuffer b=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);b.put(new byte[]{'R','I','F','F'}).putInt((int)(36+bytes)).put(new byte[]{'W','A','V','E','f','m','t',' '}).putInt(16).putShort((short)1).putShort((short)1).putInt(16000).putInt(32000).putShort((short)2).putShort((short)16).put(new byte[]{'d','a','t','a'}).putInt((int)bytes);b.flip();return b;}
 static Prepared prepare(Path stage,String key,String name,AudioDerivationPlan plan,Map<String,CanonicalPcmRenderer.Input> inputs,CanonicalPcmRenderer.Control control,ImportedAudio.DirectorySync sync)throws IOException {
  privateDirectory(stage);if(!ImportedAudio.validKey(key)||name==null||name.trim().isEmpty()||name.length()>256||name.matches("(?s).*[\\p{Cntrl}].*")||plan==null||control==null||sync==null)throw invalid("请填写有效的派生录音名称并重新选择片段。");
  for(AudioDerivationPlan.Source source:plan.sources)if(source.key.equals(key))throw invalid("派生录音必须使用新的独立身份。");
  long originalBytes=44+plan.frames*2;if(originalBytes>MAX_ORIGINAL_BYTES||plan.frames<=0)throw invalid("本次派生音频超过2GB，请分批保存。");
  budget(stage,originalBytes*2+65536);control.checkpoint(0,plan.frames);
  Path directory=stage.resolve(ImportedAudio.folder(key));Files.createDirectory(directory);
  CanonicalPcmRenderer.Result rendered=CanonicalPcmRenderer.render(stage,plan.clips(inputs),control);
  if(rendered.frames!=plan.frames||rendered.bytes!=originalBytes)throw invalid("派生录音与来源长度不符，尚未保存。");
  Path original=directory.resolve("original.audio");Files.move(rendered.temporary,original,StandardCopyOption.ATOMIC_MOVE);
  try{
   JSONArray parts=new JSONArray();long done=0;ByteBuffer buffer=ByteBuffer.allocate(BUFFER);
   try(FileChannel in=FileChannel.open(original,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
    while(done<plan.frames){
     control.checkpoint(done,plan.frames);long count=Math.min(PART_FRAMES,plan.frames-done);Path part=ImportedAudio.part(directory,parts.length());
     try(FileChannel out=FileChannel.open(part,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){
      write(out,header(count));long offset=44+done*2,remaining=count*2;
      while(remaining>0){control.checkpoint(done+(count*2-remaining)/2,plan.frames);buffer.clear();buffer.limit((int)Math.min(BUFFER,remaining));int length=buffer.remaining();while(buffer.hasRemaining()){int n=in.read(buffer,offset+buffer.position());if(n<=0)throw invalid("派生音频暂不能完整读取。");}buffer.flip();budget(directory,length);write(out,buffer);offset+=length;remaining-=length;}
      out.force(true);
     }
     parts.put(new JSONObject().put("samples",count).put("sha256",ImportedAudio.fileHash(part)));done+=count;
    }
   }
   JSONObject json=new JSONObject().put("version",1).put("kind","importedAudio").put("key",key).put("name",name.trim()).put("mime","audio/wav").put("originalBytes",rendered.bytes).put("originalSha256",rendered.sha256).put("samples",plan.frames).put("parts",parts).put("derivation",plan.provenance());
   byte[] metadata=json.toString().getBytes(StandardCharsets.UTF_8);if(metadata.length>MANIFEST_LIMIT)throw invalid("本次来源对应过长，请减少片段后分批保存；原音未改变。");
   try(FileChannel out=FileChannel.open(directory.resolve("import.json"),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){write(out,ByteBuffer.wrap(metadata));out.force(true);}
   control.checkpoint(plan.frames,plan.frames);sync.sync(directory);ImportedAudio audio=ImportedAudio.read(directory);audio.verifiedParts();AudioDerivationPlan saved=read(audio);if(saved==null||saved.frames!=plan.frames)throw invalid("派生录音来源尚未完整保存。");sync.sync(stage);return new Prepared(directory,audio);
  }catch(JSONException e){throw new IOException("派生录音来源尚未完整保存，原音保留。",e);}
 }
 /** Must run while the caller holds its library selection / lifecycle guard.
  * A directory-sync failure AFTER the rename is an uncertain durability result;
  * recovery must inspect this exact new key, never publish a duplicate or remove it.
  */
 static ImportedAudio publish(Prepared prepared,Path recordings,Guard guard,ImportedAudio.DirectorySync sync)throws IOException {
  privateDirectory(recordings);if(prepared==null||guard==null||sync==null)throw invalid("编辑任务尚未就绪。");privateDirectory(prepared.directory);
  ImportedAudio audio=ImportedAudio.read(prepared.directory);audio.verifiedParts();AudioDerivationPlan plan=read(audio);
  if(!audio.key.equals(prepared.key)||audio.samples!=prepared.frames||!ImportedAudio.hash(audio.fingerprint()).equals(prepared.fingerprint)||plan==null||plan.frames!=audio.samples)throw invalid("待保存的派生录音已变化，请重新生成。");
  Path destination=recordings.resolve(ImportedAudio.folder(prepared.key));guard.revalidate();if(Files.exists(destination,LinkOption.NOFOLLOW_LINKS))throw invalid("这份派生录音身份已存在，尚未重复保存。");
  Files.move(prepared.directory,destination,StandardCopyOption.ATOMIC_MOVE);sync.sync(recordings);return ImportedAudio.read(destination);
 }
 static AudioDerivationPlan read(ImportedAudio audio)throws IOException {
  try{Path path=audio.directory.resolve("import.json");if(Files.isSymbolicLink(path)||Files.size(path)>MANIFEST_LIMIT)throw invalid("派生录音来源无法读取。");byte[] bytes=Files.readAllBytes(path);if(!java.security.MessageDigest.isEqual(sha256(bytes),audio.fingerprint()))throw invalid("录音来源在读取期间已变化。");JSONObject json=new JSONObject(new String(bytes,StandardCharsets.UTF_8));if(!json.has("derivation"))return null;AudioDerivationPlan plan=AudioDerivationPlan.readProvenance(json.getJSONObject("derivation"));if(plan.frames!=audio.samples)throw invalid("派生录音来源长度不符。");return plan;}catch(JSONException e){throw new IOException("派生录音来源无法完整读取。",e);}
 }
 private static byte[] sha256(byte[] bytes){try{return java.security.MessageDigest.getInstance("SHA-256").digest(bytes);}catch(java.security.NoSuchAlgorithmException e){throw new AssertionError(e);}}
 private DerivedAudioPublication(){}
}
