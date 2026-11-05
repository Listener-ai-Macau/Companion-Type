package com.denzic.companion.mobile;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

/** Full local round trip using the real recording inventory and meeting store. */
public final class LibraryBackupTest {
    private interface Checked {void run() throws Exception;}
    private static void fails(Checked test)throws Exception {try{test.run();throw new AssertionError("invalid backup accepted");}catch(IOException expected){}}
    private static void check(boolean v,String m){if(!v)throw new AssertionError(m);}
    private static byte[] change(byte[] archive)throws Exception {
        ByteArrayOutputStream result=new ByteArrayOutputStream();
        try(ZipInputStream in=new ZipInputStream(new ByteArrayInputStream(archive));ZipOutputStream out=new ZipOutputStream(result)){
            ZipEntry e;boolean altered=false;byte[] b=new byte[8192];
            while((e=in.getNextEntry())!=null){out.putNextEntry(new ZipEntry(e.getName()));int n;while((n=in.read(b))!=-1){if(!altered&&e.getName().endsWith(".cop1")){b[0]^=1;altered=true;}out.write(b,0,n);}out.closeEntry();}check(altered,"fixture has no audio");
        }return result.toByteArray();
    }
    public static void main(String[] args)throws Exception {
        Path base=Files.createTempDirectory(Paths.get(args[0]),"library-backup-");Path recordings=Files.createDirectory(base.resolve("recordings")),meetings=Files.createDirectory(base.resolve("meetings")),control=Files.createDirectory(base.resolve("control"));
        byte[] wire=Files.readAllBytes(Paths.get(args[0],"descriptor0.bin")),audio=Files.readAllBytes(Paths.get(args[0],"payload.bin"));
        RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(wire);String stem=SegmentReceiver.key(descriptor);
        Files.write(recordings.resolve(stem+".meta"),wire);Files.write(recordings.resolve(stem+".cop1"),audio);
        check(RecordingLibrary.list(recordings).get(0).state==RecordingLibrary.State.VERIFIED,"synthetic audio fixture");
        String key=MeetingStore.sessionKey(descriptor),transcript="明天下午讨论包装，小王周五发送报价。",minutes="{\"quality\":\"final\",\"summary\":[\"讨论包装\"]}";
        MeetingStore store=new MeetingStore(meetings);MeetingStore.Task task=new MeetingStore.Task("a","发送报价","小王","周五",false);
        store.save(key,0,transcript,"备注",Collections.singletonList(task));store.saveMinutes(key,1,0,transcript,"{\"summary\":[\"较早纪要\"]}");store.saveMinutes(key,1,1,transcript,minutes);
        Files.write(control.resolve("session.fixture"),"control state".getBytes(StandardCharsets.UTF_8));
        fails(()->LibraryBackup.write(new ByteArrayOutputStream(),base.resolve("missing-recordings"),meetings,control));
        ByteArrayOutputStream out=new ByteArrayOutputStream();LibraryBackup.write(out,recordings,meetings,control);byte[] archive=out.toByteArray();
        Path restored=base.resolve("restored");LibraryBackup.restore(new ByteArrayInputStream(archive),restored);
        check(RecordingLibrary.list(restored.resolve("recordings")).get(0).state==RecordingLibrary.State.VERIFIED,"restored audio not valid");
        check(Arrays.equals(audio,Files.readAllBytes(restored.resolve("recordings").resolve(stem+".cop1"))),"audio changed");
        MeetingStore reopened=new MeetingStore(restored.resolve("meetings"));MeetingStore.Snapshot saved=reopened.load(key);
        check(saved.transcript.equals(transcript)&&saved.notes.equals("备注")&&saved.tasks.size()==1&&saved.tasks.get(0).owner.equals("小王"),"meeting not restored");
        check(reopened.loadMinutes(key).json.equals(minutes),"minutes not restored");
        check(reopened.listMinutesHistory(key).versions.size()==1&&reopened.listMinutesHistory(key).versions.get(0).json.contains("较早纪要"),"history not restored");
        MeetingStore.Minutes earlier=reopened.listMinutesHistory(key).versions.get(0);
        MeetingStore.Minutes switched=reopened.restoreMinutesHistory(key,saved.revision,2,earlier.historyId);
        check(switched.json.contains("较早纪要")&&!switched.sourceChanged&&reopened.listMinutesHistory(key).versions.get(0).json.equals(minutes),"history switch after backup lost current result");
        check(Arrays.equals(Files.readAllBytes(control.resolve("session.fixture")),Files.readAllBytes(restored.resolve("control/session.fixture"))),"control state not restored");
        fails(()->LibraryBackup.restore(new ByteArrayInputStream(archive),restored));
        check(reopened.load(key).transcript.equals(transcript),"existing destination overwritten");
        Path corrupt=base.resolve("corrupt");fails(()->LibraryBackup.restore(new ByteArrayInputStream(change(archive)),corrupt));check(!Files.exists(corrupt),"corrupt backup published");
        Path truncated=base.resolve("truncated");fails(()->LibraryBackup.restore(new ByteArrayInputStream(Arrays.copyOf(archive,archive.length/2)),truncated));check(!Files.exists(truncated),"partial backup published");
        Path noSpace=base.resolve("budget");fails(()->LibraryBackup.restore(new ByteArrayInputStream(archive),noSpace,1,100000));check(!Files.exists(noSpace),"disk-budget partial backup published");
        Path tooMany=base.resolve("too-many");fails(()->LibraryBackup.restore(new ByteArrayInputStream(archive),tooMany,Long.MAX_VALUE,1));check(!Files.exists(tooMany),"file-budget partial backup published");
        ByteArrayOutputStream bad=new ByteArrayOutputStream();try(ZipOutputStream zip=new ZipOutputStream(bad)){zip.putNextEntry(new ZipEntry("recordings/../../escape"));zip.write(1);zip.closeEntry();}
        Path traversal=base.resolve("traversal");fails(()->LibraryBackup.restore(new ByteArrayInputStream(bad.toByteArray()),traversal));check(!Files.exists(base.resolve("escape"))&&!Files.exists(traversal),"path escaped");
        final boolean[] changed={false};OutputStream mutation=new FilterOutputStream(new ByteArrayOutputStream()){
            void change()throws IOException {if(!changed[0]){changed[0]=true;Files.write(control.resolve("session.fixture"),"changed while saving".getBytes(StandardCharsets.UTF_8));}}
            @Override public void write(int value)throws IOException {out.write(value);change();}
            @Override public void write(byte[] bytes,int off,int len)throws IOException {out.write(bytes,off,len);change();}
        };
        fails(()->LibraryBackup.write(mutation,recordings,meetings,control));
        System.out.println("PASS recording, transcript, minutes, tasks and control round trip; corrupt, truncated, collision, traversal and changing source rejected");
    }
}
