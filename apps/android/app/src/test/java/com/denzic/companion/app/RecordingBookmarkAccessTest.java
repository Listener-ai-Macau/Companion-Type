package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import org.json.*;
import java.nio.file.*;import java.util.*;import java.io.*;import java.security.*;import java.util.zip.CRC32;import java.lang.reflect.*;

/** Existing cached host JNI decoder plus the production app mapper. No ASR is invoked. */
public final class RecordingBookmarkAccessTest {
 static void put16(byte[]p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
 static void put32(byte[]p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
 static void put64(byte[]p,int i,long v){for(int n=0;n<8;n++)p[i+n]=(byte)(v>>>(8*n));}
 static void check(boolean v,String m){if(!v)throw new AssertionError(m);}
 interface Checked{void run()throws Exception;}
 static void fails(Checked action)throws Exception{try{action.run();throw new AssertionError("invalid mark accepted");}catch(IOException expected){}}
 static NativeAudio.Part part(Path p,long first,long samples)throws Exception{Constructor<NativeAudio.Part> c=NativeAudio.Part.class.getDeclaredConstructor(Path.class,long.class,long.class);c.setAccessible(true);return c.newInstance(p,first,samples);}
 static NativeAudio.PartsResult parts(Path p,long samples,List<NativeAudio.Part> rows,List<NativeAudio.Bookmark> marks)throws Exception{Constructor<NativeAudio.PartsResult> c=NativeAudio.PartsResult.class.getDeclaredConstructor(Path.class,long.class,boolean.class,List.class,List.class,byte[].class);c.setAccessible(true);return c.newInstance(p,samples,true,rows,marks,new byte[32]);}
 public static void main(String[]args)throws Exception{
  Path root=Files.createTempDirectory(Paths.get(args[0]),"native-device-mark-");
  // Same synthetic silent Opus/schema3 fixture used by the existing NativeAudioJvmTest.
  ByteArrayOutputStream source=new ByteArrayOutputStream();source.write(new byte[]{'C','O','P','1',3,1,20,3,(byte)128,62,0,0});
  int[] opus={184,91,61,13,6,212,119,103,154,112,59,167,214,84,199,215,224,197,21,15,83,26,25,151,74,91,44,201,192,179,8,78,13,165,128,204,28,243,127,83};
  byte[] audio=new byte[42];audio[0]=40;for(int i=0;i<opus.length;i++)audio[i+2]=(byte)opus[i];source.write(audio);source.write(audio);
  while(source.size()%248!=0)source.write(255);byte[] mark=new byte[32];System.arraycopy(new byte[]{'C','P','G','1'},0,mark,2,4);mark[6]=4;put32(mark,8,1);put64(mark,12,640);put64(mark,20,40);CRC32 crc=new CRC32();crc.update(mark,0,28);put32(mark,28,crc.getValue());
  source.write(mark);while(source.size()%248!=0)source.write(255);source.write(audio);byte[] raw=source.toByteArray(),hash=MessageDigest.getInstance("SHA-256").digest(raw);
  byte[] d=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,d,0,4);put16(d,4,2);put16(d,6,112);put32(d,8,41);d[12]=1;d[20]=1;put32(d,40,960);put32(d,48,raw.length);crc.reset();crc.update(raw);put32(d,52,crc.getValue());System.arraycopy(hash,0,d,56,32);put32(d,88,1);d[92]=3;d[93]=3;d[96]=1;crc.reset();crc.update(d,0,108);put32(d,108,crc.getValue());
  RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(d);Method keyMethod=SegmentReceiver.class.getDeclaredMethod("key",RecorderWire.Descriptor.class);keyMethod.setAccessible(true);String stem=(String)keyMethod.invoke(null,descriptor);Files.write(root.resolve(stem+".meta"),d);Files.write(root.resolve(stem+".cop1"),raw);
  RecordingLibrary.Session session=RecordingLibrary.sessions(root).get(0);String binding=RecordingBookmarkAccess.binding(session),key=MeetingStore.sessionKey(descriptor);
  NativeAudio.VerifiedPrefix prefix=NativeAudio.inspectPrefix(session);JSONObject list=RecordingBookmarkAccess.describe(key,"library-token",binding,prefix);
  check(list.getBoolean("complete")&&list.getJSONArray("marks").length()==1,"native source mark missing");JSONObject item=list.getJSONArray("marks").getJSONObject(0);check(item.getString("sequence").equals("1")&&item.getLong("elapsedMs")==40,"source metadata wrong");
  Files.write(Paths.get(args[0]).resolve("native-mark-list.json"),list.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
  NativeAudio.Result decoded=NativeAudio.decode(session,root.resolve("decoded.wav"));NativeAudio.PartsResult playable=parts(root,decoded.samples,Collections.singletonList(part(decoded.path,0,decoded.samples)),decoded.bookmarks);
  RecordingBookmarkAccess.Playback selected=RecordingBookmarkAccess.playback(playable,"1",640,40);check(selected.part==0&&selected.positionMs==decoded.bookmarks.get(0).playbackSamples/16,"ignored native playback mapping");check(selected.positionMs!=40,"used elapsed time as playback time");
  String text=new String(RecordingBookmarkAccess.text("示例录音",list),java.nio.charset.StandardCharsets.UTF_8);check(text.contains("设备重点 1")&&text.contains("不是 AI 结论"),"export attribution missing");
  NativeAudio.PartsResult split=parts(root,decoded.samples,Arrays.asList(part(decoded.path,0,160),part(decoded.path,160,decoded.samples-160)),decoded.bookmarks);RecordingBookmarkAccess.Playback second=RecordingBookmarkAccess.playback(split,"1",640,40);check(second.part==1&&second.offsetMs==10&&second.positionMs==20,"multipart lookup used the wrong part/offset");
  JSONObject partial=new JSONObject(list.toString()).put("complete",false);check(new String(RecordingBookmarkAccess.text("示例",partial),java.nio.charset.StandardCharsets.UTF_8).contains("完整录音可能还有其他重点"),"partial export claimed complete");fails(()->RecordingBookmarkAccess.text("示例",new JSONObject(list.toString()).put("marks",new JSONArray())));
  fails(()->RecordingBookmarkAccess.playback(playable,"2",640,40));fails(()->RecordingBookmarkAccess.playback(playable,"1",640,41));
  NativeAudio.PartsResult duplicate=parts(root,decoded.samples,playable.parts,Arrays.asList(decoded.bookmarks.get(0),decoded.bookmarks.get(0)));fails(()->RecordingBookmarkAccess.playback(duplicate,"1",640,40));
  NativeAudio.PartsResult hole=parts(root,decoded.samples,Collections.singletonList(part(decoded.path,0,1)),decoded.bookmarks);fails(()->RecordingBookmarkAccess.playback(hole,"1",640,40));
  NativeAudio.PartsResult end=parts(root,decoded.bookmarks.get(0).playbackSamples,playable.parts,decoded.bookmarks);fails(()->RecordingBookmarkAccess.playback(end,"1",640,40));
  byte[] synced=d.clone();synced[95]=1;crc.reset();crc.update(synced,0,108);put32(synced,108,crc.getValue());Files.write(root.resolve(stem+".meta"),synced);check(binding.equals(RecordingBookmarkAccess.binding(RecordingLibrary.sessions(root).get(0))),"receipt-only state invalidated source");
  synced[94]=1;crc.reset();crc.update(synced,0,108);put32(synced,108,crc.getValue());Files.write(root.resolve(stem+".meta"),synced);check(!binding.equals(RecordingBookmarkAccess.binding(RecordingLibrary.sessions(root).get(0))),"changed recording metadata retained binding");
  check(Arrays.equals(raw,Files.readAllBytes(root.resolve(stem+".cop1"))),"original audio changed");
  System.out.println("PASS cached host JNI inspect/decode plus app list/export/playback mapper; device elapsed40ms mapped to playback"+selected.positionMs+"ms, missing/duplicate/gap/end rejected, source binding and originals preserved; no models/Android/device claim");
 }
}
