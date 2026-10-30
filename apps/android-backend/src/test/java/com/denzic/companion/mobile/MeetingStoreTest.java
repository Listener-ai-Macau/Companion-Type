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
    private static void text(java.io.DataOutputStream out,String s)throws Exception {if(s==null){out.writeInt(-1);return;}byte[] bytes=s.getBytes(StandardCharsets.UTF_8);out.writeInt(bytes.length);out.write(bytes);}
    private static byte[] legacyMeeting(String key)throws Exception {
        java.io.ByteArrayOutputStream buffer=new java.io.ByteArrayOutputStream();java.io.DataOutputStream out=new java.io.DataOutputStream(buffer);
        out.writeInt(0x434d5731);text(out,key);out.writeLong(1);text(out,"旧转写");text(out,"");out.writeInt(1);
        text(out,"task");text(out,"旧待办");text(out,null);text(out,"2026-11-01");out.writeBoolean(false);out.flush();
        byte[] body=buffer.toByteArray();buffer.write(MessageDigest.getInstance("SHA-256").digest(body));return buffer.toByteArray();
    }
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
        String calendarKey="synthetic-calendar-session";
        MeetingStore.CalendarSettings setting=new MeetingStore.CalendarSettings(30,null,"2026-11-02T14:00:00+08:00","2026-11-02T15:00:00+08:00");
        MeetingStore.Task dated=new MeetingStore.Task("calendar-task","检查样品",null,"2026-11-02T16:00:00+08:00",false,setting);
        store.save(calendarKey,0,"会议原文","",Collections.singletonList(dated));
        MeetingStore.Task original=new MeetingStore(root).load(calendarKey).tasks.get(0);
        if(original.calendar==null||original.calendar.reminderMinutes!=30||original.calendarNeedsReview())throw new AssertionError("calendar choices did not persist");
        MeetingStore.Task edited=new MeetingStore.Task("calendar-task","检查蓝色样品",null,"2026-11-03T16:00:00+08:00",false);
        MeetingStore.Task rescheduled=store.save(calendarKey,1,"会议原文","",Collections.singletonList(edited)).tasks.get(0);
        if(rescheduled.calendar==null||rescheduled.calendar.reminderMinutes!=30||!rescheduled.calendarNeedsReview())throw new AssertionError("reschedule lost prior reminder or failed to flag review");
        MeetingStore.Task reviewed=new MeetingStore.Task(rescheduled.id,rescheduled.text,rescheduled.owner,rescheduled.due,false,rescheduled.calendar);
        if(store.save(calendarKey,2,"会议原文","",Collections.singletonList(reviewed)).tasks.get(0).calendarNeedsReview())throw new AssertionError("reviewed choices remained stale");
        MeetingStore.Task cleared=new MeetingStore.Task("calendar-task","检查蓝色样品",null,"2026-11-03T16:00:00+08:00",false,null);
        if(store.save(calendarKey,3,"会议原文","",Collections.singletonList(cleared)).tasks.get(0).calendar!=null)throw new AssertionError("explicit clear was ignored");
        expectFailure(()->store.save(calendarKey,3,"过期编辑","",Collections.singletonList(dated)));
        String oldKey="synthetic-v1-session";Files.write(root.resolve(stem(oldKey)+".meeting"),legacyMeeting(oldKey));
        MeetingStore.Snapshot legacy=store.load(oldKey);if(!legacy.transcript.equals("旧转写")||legacy.tasks.get(0).calendar!=null)throw new AssertionError("v1 meeting migration failed");
        if(!store.save(oldKey,legacy.revision,legacy.transcript,legacy.notes,legacy.tasks).transcript.equals("旧转写"))throw new AssertionError("v1 update failed");
        System.out.println("PASS local meeting persistence, concurrent edits and backup recovery");
    }
}
