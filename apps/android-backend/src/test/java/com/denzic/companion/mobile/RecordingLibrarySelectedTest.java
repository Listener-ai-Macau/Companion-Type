package com.denzic.companion.mobile;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.Arrays;
import static com.denzic.companion.mobile.RecorderWire.*;
public final class RecordingLibrarySelectedTest {
 static void check(boolean b){if(!b)throw new AssertionError();}
 static Descriptor add(Path root,byte[] template,long session,boolean invalidFile)throws Exception {
  byte[] bytes=new byte[64];Arrays.fill(bytes,(byte)session);byte[] m=template.clone();put64(m,20,session);put32(m,8,session+100);put32(m,28,0);put64(m,32,0);put64(m,40,320);put32(m,48,bytes.length);put32(m,52,crc(bytes,0,bytes.length));System.arraycopy(MessageDigest.getInstance("SHA-256").digest(bytes),0,m,56,32);m[92]=3;put32(m,108,crc(m,0,108));if(m.length==120)put32(m,116,crc(m,0,116));Descriptor d=Descriptor.decode(m);String name=SegmentReceiver.key(d);Files.write(root.resolve(name+".meta"),m);if(invalidFile)Files.createDirectory(root.resolve(name+".cop1"));else Files.write(root.resolve(name+".cop1"),bytes);return d;
 }
 public static void main(String[] args)throws Exception {
  Path root=Files.createDirectory(Paths.get(args[0]));byte[] template=Files.readAllBytes(Paths.get(args[1]));Descriptor wanted=add(root,template,0x2a,false),other=add(root,template,0x2a0,true);
  String key=MeetingStore.sessionKey(wanted);RecordingLibrary.Inventory a=RecordingLibrary.inspectSession(root,key);check(a.problems.isEmpty()&&a.sessions.size()==1&&a.sessions.get(0).state==RecordingLibrary.SessionState.COMPLETE);
  check(RecordingLibrary.inspect(root).sessions.size()==2); // Whole-library access includes the unrelated invalid audio; selected access does not.
  Path otherMeta=root.resolve(SegmentReceiver.key(other)+".meta");byte[] bad=Files.readAllBytes(otherMeta);bad[0]^=1;Files.write(otherMeta,bad);
  check(RecordingLibrary.inspect(root).problems.size()==1&&RecordingLibrary.inspectSession(root,key).problems.isEmpty());
  Path audio=root.resolve(SegmentReceiver.key(wanted)+".cop1");byte[] bytes=Files.readAllBytes(audio);bytes[0]^=1;Files.write(audio,bytes);check(RecordingLibrary.inspectSession(root,key).sessions.get(0).state==RecordingLibrary.SessionState.DAMAGED);
  bytes[0]^=1;Files.write(audio,bytes);check(RecordingLibrary.inspectSession(root,key).sessions.get(0).state==RecordingLibrary.SessionState.COMPLETE);
  Path meta=root.resolve(SegmentReceiver.key(wanted)+".meta");byte[] m=Files.readAllBytes(meta);m[0]^=1;Files.write(meta,m);check(RecordingLibrary.inspectSession(root,key).problems.size()==1);
  for(String invalid:new String[]{"../outside",key+"-",key.replace(":2a",":02a")})try{RecordingLibrary.inspectSession(root,invalid);throw new AssertionError("bad key accepted");}catch(IllegalArgumentException expected){}
  System.out.println("PASS_SELECTED_ONLY_BYTES_EXACT_DELIMITER_DAMAGED_CURRENT_AUDIO_METADATA_AND_CANONICAL_KEY");
 }
}
