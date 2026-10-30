package com.denzic.companion.mobile;

import java.io.RandomAccessFile;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Collections;

/** Isolated local persistence, interrupted-save recovery and stale edit checks. */
public final class MeetingStoreTest {
    private interface Checked {void run()throws Exception;}
    private static void expectFailure(Checked action)throws Exception {try{action.run();throw new AssertionError("operation unexpectedly succeeded");}catch(java.io.IOException expected){}}
    private static String stem(String key)throws Exception {StringBuilder b=new StringBuilder();for(byte v:MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8)))b.append(String.format(java.util.Locale.ROOT,"%02x",v&255));return b.toString();}
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory(Paths.get(args[0]),"meeting-store-");MeetingStore store=new MeetingStore(root);String key="synthetic-device:epoch:session";
        if(store.load(key)!=null)throw new AssertionError("new session should be empty");
        MeetingStore.Task first=new MeetingStore.Task("one","整理报价","小王","周五之前",false);
        MeetingStore.Task second=new MeetingStore.Task("two","确认交货 🚀",null,null,true);
        MeetingStore.Snapshot a=store.save(key,0,"原始转写","初稿",Arrays.asList(first,second));if(a.revision!=1)throw new AssertionError("first revision");
        MeetingStore.Snapshot b=store.save(key,1,"修订转写","更新纪要",Arrays.asList(first,second));if(b.revision!=2)throw new AssertionError("second revision");
        MeetingStore.Snapshot reopened=new MeetingStore(root).load(key);
        if(reopened.recoveredFromBackup||!reopened.transcript.equals("修订转写")||!reopened.notes.equals("更新纪要")||reopened.tasks.size()!=2||!reopened.tasks.get(1).completed||!reopened.tasks.get(0).owner.equals("小王"))throw new AssertionError("reopened content differs");
        if(store.list().meetings.size()!=1||store.list().unreadableFiles!=0)throw new AssertionError("offline meeting inventory");
        expectFailure(()->store.save(key,1,"过期编辑","",Collections.emptyList()));
        expectFailure(()->store.save(key,2,"","",Arrays.asList(first,first)));
        try(RandomAccessFile lockFile=new RandomAccessFile(root.resolve(stem(key)+".lock").toFile(),"rw");FileLock ignored=lockFile.getChannel().tryLock()) {expectFailure(()->store.save(key,2,"并发编辑","",Collections.emptyList()));}
        if(!store.load(key).transcript.equals("修订转写"))throw new AssertionError("stale edit changed saved content");
        Path main=root.resolve(stem(key)+".meeting");byte[] damaged=Files.readAllBytes(main);damaged[8]^=1;Files.write(main,damaged);
        MeetingStore.Snapshot recovered=store.load(key);if(!recovered.recoveredFromBackup||recovered.revision!=1||!recovered.transcript.equals("原始转写"))throw new AssertionError("backup recovery not surfaced");
        if(store.list().meetings.size()!=1||!store.list().meetings.get(0).recoveredFromBackup||store.list().unreadableFiles==0)throw new AssertionError("inventory must expose backup recovery");
        MeetingStore.Snapshot restored=store.save(key,1,"从备份继续","恢复",Collections.singletonList(first));if(restored.revision!=2||restored.recoveredFromBackup)throw new AssertionError("recovered meeting not saved");
        try(java.nio.file.DirectoryStream<Path> files=Files.newDirectoryStream(root,"damaged-meeting-*.bin")){java.util.Iterator<Path> it=files.iterator();if(!it.hasNext()||!Arrays.equals(Files.readAllBytes(it.next()),damaged))throw new AssertionError("damaged newer content not retained");}
        String other="another-synthetic-session";store.save(other,0,"其他录音","",Collections.emptyList());Path otherFile=root.resolve(stem(other)+".meeting");byte[] broken=Files.readAllBytes(otherFile);broken[5]^=1;Files.write(otherFile,broken);
        expectFailure(()->store.load(other));expectFailure(()->store.save(other,0,"覆盖","",Collections.emptyList()));
        if(!Arrays.equals(Files.readAllBytes(otherFile),broken)||!store.load(key).transcript.equals("从备份继续"))throw new AssertionError("damaged or unrelated meeting changed");
        if(store.list().meetings.size()!=1||store.list().unreadableFiles==0)throw new AssertionError("one damaged meeting must not hide another");
        System.out.println("PASS local meeting persistence, concurrent edits and backup recovery");
    }
}
