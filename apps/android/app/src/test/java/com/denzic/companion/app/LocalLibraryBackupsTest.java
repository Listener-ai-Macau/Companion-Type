package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

public final class LocalLibraryBackupsTest {
 interface Checked{void run()throws Exception;}
 static void check(boolean v,String message){if(!v)throw new AssertionError(message);}
 static void fails(Checked action)throws Exception{boolean failed=false;try{action.run();}catch(IOException expected){failed=true;}check(failed,"invalid operation accepted");}
 public static void main(String[]args)throws Exception{
  Path base=Files.createTempDirectory(Paths.get(args[0]),"library-app-"),source=Files.createDirectory(base.resolve("source")),phone=Files.createDirectory(base.resolve("phone"));
  LocalLibraryBackups a=new LocalLibraryBackups(source),b=new LocalLibraryBackups(phone);Files.createDirectories(a.recordings());Files.createDirectories(a.meetings());Files.createDirectories(b.recordings());Files.createDirectories(b.meetings());
  byte[] wire=Files.readAllBytes(Paths.get(args[1],"descriptor0.bin")),audio=Files.readAllBytes(Paths.get(args[1],"payload.bin"));RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(wire);java.lang.reflect.Method keyMethod=SegmentReceiver.class.getDeclaredMethod("key",RecorderWire.Descriptor.class);keyMethod.setAccessible(true);String stem=(String)keyMethod.invoke(null,descriptor),key=MeetingStore.sessionKey(descriptor);
  Files.write(a.recordings().resolve(stem+".meta"),wire);Files.write(a.recordings().resolve(stem+".cop1"),audio);Files.write(a.recordings().resolve(".consume-pending"),wire);
  MeetingStore ms=new MeetingStore(a.meetings());MeetingStore.Snapshot original=ms.save(key,0,"周五核对报价。","原有备注",Collections.singletonList(new MeetingStore.Task("task","发送报价","小王","周五",true)));
  String ai=new JSONObject().put("markdown","## Action Items\n- 核对报价").put("quality","draft").put("processing",new JSONObject().put("complete",false)).toString();MeetingStore.Minutes first=ms.saveMinutes(key,1,0,original.transcript,ai);
  String human=ManualMinutesEdits.apply(ai,"## Action Items\n- [x] 核对报价 (owner: 小王, due: 周五18:00)","[\"Action Items\",0,0]",false,1);ms.saveEditedMinutes(key,1,first.revision,first.json,human,false);
  ms.saveTranscriptCorrection(key,1,"周五核对报价，原录音不改写。");new TranslationStore(a.meetings().resolve("translations")).save(new TranslationStore.Entry(key,"en",original.transcript,1,"Review the quote on Friday."));Files.write(a.meetings().resolve("title.fixture"),"人工名称".getBytes(StandardCharsets.UTF_8));
  ByteArrayOutputStream out=new ByteArrayOutputStream();a.write(out,a.token());byte[] archive=out.toByteArray();
  MeetingStore owned=new MeetingStore(b.meetings());owned.save(key,0,"本手机已有不同的会议资料。","不得覆盖",Collections.emptyList());Path ownedFile=b.recordings().resolve("owner-existing.fixture");Files.write(ownedFile,new byte[]{9,8,7});String oldToken=b.token();Path oldMeetings=b.meetings();
  JSONObject restored=b.restore(new ByteArrayInputStream(archive),oldToken);String restoredId=restored.getString("activeId");check(!restoredId.equals("original"),"restored into original");check(restored.getJSONArray("libraries").length()==2,"original library lost");
  check(new MeetingStore(oldMeetings).load(key).notes.equals("不得覆盖")&&Arrays.equals(Files.readAllBytes(ownedFile),new byte[]{9,8,7}),"existing phone data changed");
  check(RecordingLibrary.list(b.recordings()).get(0).state==RecordingLibrary.State.VERIFIED,"restored original audio not verified");check(Arrays.equals(Files.readAllBytes(b.recordings().resolve(stem+".cop1")),audio),"audio changed");
  MeetingStore reopened=new MeetingStore(b.meetings());check(reopened.load(key).tasks.get(0).completed,"task status lost");check(reopened.loadMinutes(key).json.equals(human)&&reopened.loadMinutes(key).sourceChanged,"manual result or stale source changed");check(reopened.listMinutesHistory(key).versions.get(0).json.equals(ai),"AI history lost");check(Files.readAllBytes(b.meetings().resolve("title.fixture")).length>0,"title lost");
  check(new TranslationStore(b.meetings().resolve("translations")).load(key).text.equals("Review the quote on Friday."),"translation lost");check(!Files.exists(b.recordings().resolve(".consume-pending")),"restored receipt became active");check(Arrays.equals(Files.readAllBytes(b.recordings().resolve("backup-device-receipts").resolve(restoredId).resolve(".consume-pending")),wire),"device receipt was discarded");
  check(new LocalLibraryBackups(phone).status().getString("activeId").equals(restoredId),"library selection lost on reopen");fails(()->b.activate("original",oldToken));check(b.status().getString("activeId").equals(restoredId),"stale request changed selection");
  b.activate("original",b.token());check(b.meetings().equals(oldMeetings)&&new MeetingStore(b.meetings()).load(key).notes.equals("不得覆盖"),"cannot return to original data");b.activate(restoredId,b.token());check(new MeetingStore(b.meetings()).loadMinutes(key).json.equals(human),"restored library not retained after switch");
  String stable=b.token();fails(()->b.restore(new ByteArrayInputStream(Arrays.copyOf(archive,archive.length/2)),stable));check(b.token().equals(stable),"partial restore changed selected library");
  fails(()->LibraryBackup.restore(new ByteArrayInputStream(archive),base.resolve("disk-budget"),1,100000));check(!Files.exists(base.resolve("disk-budget")),"disk budget published partial restore");
  fails(()->LibraryBackup.restore(new ByteArrayInputStream(archive),base.resolve("file-budget"),Long.MAX_VALUE,1));check(!Files.exists(base.resolve("file-budget")),"file budget published partial restore");
  fails(()->b.write(new OutputStream(){public void write(int n)throws IOException{throw new IOException("destination full");}},b.token()));check(b.token().equals(stable),"failed backup changed current library");
  fails(()->b.activate("../../outside",b.token()));Files.write(phone.resolve("companion-library-index.json"),"broken".getBytes(StandardCharsets.UTF_8));fails(()->b.status());check(Arrays.equals(Files.readAllBytes(ownedFile),new byte[]{9,8,7}),"bad index erased existing files");
  System.out.println("PASS real encoded audio/transcript/manual actions/translation/history round trip; existing colliding phone data retained, durable selection/switchback, stale requests, corrupt/partial/budget failures and device receipt isolation");
 }
}
