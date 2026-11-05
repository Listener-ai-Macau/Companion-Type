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
    private static byte[] priorV2Meeting(String key)throws Exception {
        java.io.ByteArrayOutputStream buffer=new java.io.ByteArrayOutputStream();java.io.DataOutputStream out=new java.io.DataOutputStream(buffer);
        out.writeInt(0x434d5732);text(out,key);out.writeLong(1);text(out,"候选版转写");text(out,"");out.writeInt(1);
        text(out,"task");text(out,"旧待办");text(out,null);text(out,"2026-11-01");out.writeBoolean(false);
        out.writeBoolean(true);out.writeInt(30);text(out,null);text(out,null);text(out,null);text(out,"2026-11-01");out.flush();
        byte[] body=buffer.toByteArray();buffer.write(MessageDigest.getInstance("SHA-256").digest(body));return buffer.toByteArray();
    }
    private static byte[] oldRewrite(String key,long revision,String due)throws Exception {
        java.io.ByteArrayOutputStream buffer=new java.io.ByteArrayOutputStream();java.io.DataOutputStream out=new java.io.DataOutputStream(buffer);
        out.writeInt(0x434d5731);text(out,key);out.writeLong(revision);text(out,"旧版修改");text(out,"");out.writeInt(1);
        text(out,"calendar-task");text(out,"检查样品");text(out,null);text(out,due);out.writeBoolean(false);out.flush();
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
        byte[] firstCalendarMeeting=Files.readAllBytes(root.resolve(stem(calendarKey)+".meeting"));
        if(java.nio.ByteBuffer.wrap(firstCalendarMeeting).getInt()!=0x434d5731)throw new AssertionError("meeting must stay readable by previous backend");
        MeetingStore.Task original=new MeetingStore(root).load(calendarKey).tasks.get(0);
        if(original.calendar==null||original.calendar.reminderMinutes!=30||original.calendarNeedsReview())throw new AssertionError("calendar choices did not persist");
        MeetingStore.Task edited=new MeetingStore.Task("calendar-task","检查蓝色样品",null,"2026-11-03T16:00:00+08:00",false);
        MeetingStore.Task rescheduled=store.save(calendarKey,1,"会议原文","",Collections.singletonList(edited)).tasks.get(0);
        if(rescheduled.calendar==null||rescheduled.calendar.reminderMinutes!=30||!rescheduled.calendarNeedsReview())throw new AssertionError("reschedule lost prior reminder or failed to flag review");
        byte[] secondCalendarMeeting=Files.readAllBytes(root.resolve(stem(calendarKey)+".meeting"));
        // Simulate interruption after publishing new calendar data but before
        // publishing the new main file; old data must resolve its own settings.
        Files.write(root.resolve(stem(calendarKey)+".meeting"),firstCalendarMeeting);
        MeetingStore.Task interrupted=store.load(calendarKey).tasks.get(0);
        if(interrupted.calendar==null||interrupted.calendarNeedsReview()||interrupted.calendar.reminderMinutes!=30)throw new AssertionError("interrupted save lost the prior calendar version");
        Files.write(root.resolve(stem(calendarKey)+".meeting"),secondCalendarMeeting);
        MeetingStore.Task reviewed=new MeetingStore.Task(rescheduled.id,rescheduled.text,rescheduled.owner,rescheduled.due,false,rescheduled.calendar);
        if(store.save(calendarKey,2,"会议原文","",Collections.singletonList(reviewed)).tasks.get(0).calendarNeedsReview())throw new AssertionError("reviewed choices remained stale");
        MeetingStore.Task cleared=new MeetingStore.Task("calendar-task","检查蓝色样品",null,"2026-11-03T16:00:00+08:00",false,null);
        if(store.save(calendarKey,3,"会议原文","",Collections.singletonList(cleared)).tasks.get(0).calendar!=null)throw new AssertionError("explicit clear was ignored");
        expectFailure(()->store.save(calendarKey,3,"过期编辑","",Collections.singletonList(dated)));
        // An old client can rewrite a CMW1 meeting; a stale sidecar must never
        // attach choices to different bytes merely because a revision matches.
        String reused="synthetic-reused-revision";store.save(reused,0,"new","",Collections.singletonList(dated));
        Files.write(root.resolve(stem(reused)+".meeting"),legacyMeeting(reused));
        MeetingStore.Snapshot rewritten=store.load(reused);
        if(!rewritten.transcript.equals("旧转写")||rewritten.tasks.get(0).calendar!=null)throw new AssertionError("stale calendar choices attached to different meeting bytes");
        String oldRepeated="synthetic-old-multiple-edits";store.save(oldRepeated,0,"new","",Collections.singletonList(dated));
        Files.write(root.resolve(stem(oldRepeated)+".backup"),oldRewrite(oldRepeated,2,"2026-11-02T16:00:00+08:00"));
        Files.write(root.resolve(stem(oldRepeated)+".meeting"),oldRewrite(oldRepeated,3,"2026-11-02T16:00:00+08:00"));
        MeetingStore.Snapshot uncertain=store.load(oldRepeated);
        if(uncertain.tasks.get(0).calendar==null||!uncertain.tasks.get(0).calendarNeedsReview())throw new AssertionError("old edits must surface recovered calendar choices for review");
        MeetingStore.Task unchanged=new MeetingStore.Task("calendar-task","检查样品",null,"2026-11-02T16:00:00+08:00",false);
        store.save(oldRepeated,3,uncertain.transcript,uncertain.notes,Collections.singletonList(unchanged));
        if(!store.load(oldRepeated).tasks.get(0).calendarNeedsReview())throw new AssertionError("unreviewed recovery flag must survive saving");
        MeetingStore.Task confirmed=new MeetingStore.Task("calendar-task","检查样品",null,"2026-11-02T16:00:00+08:00",false,store.load(oldRepeated).tasks.get(0).calendar);
        if(store.save(oldRepeated,4,uncertain.transcript,uncertain.notes,Collections.singletonList(confirmed)).tasks.get(0).calendarNeedsReview())throw new AssertionError("explicit review should clear recovery flag");
        String crashes="synthetic-interrupted-calendar-writes";Path crashMain=root.resolve(stem(crashes)+".meeting"),crashBackup=root.resolve(stem(crashes)+".backup");
        store.save(crashes,0,"one","",Collections.singletonList(dated));
        MeetingStore.Task zeroReminder=new MeetingStore.Task("calendar-task","检查样品",null,"2026-11-02T16:00:00+08:00",false,new MeetingStore.CalendarSettings(0,null,null,null));
        store.save(crashes,1,"two","",Collections.singletonList(zeroReminder));
        byte[] safeMain=Files.readAllBytes(crashMain),safeBackup=Files.readAllBytes(crashBackup);
        store.save(crashes,2,"attempt-a","",Collections.singletonList(dated));
        Files.write(crashMain,safeMain);Files.write(crashBackup,safeBackup);
        store.save(crashes,2,"attempt-b","",Collections.singletonList(zeroReminder));
        Files.write(crashMain,safeMain);Files.write(crashBackup,safeBackup);
        byte[] bad=safeMain.clone();bad[8]^=1;Files.write(crashMain,bad);
        MeetingStore.Snapshot afterRepeatedInterruptions=store.load(crashes);
        if(!afterRepeatedInterruptions.recoveredFromBackup||afterRepeatedInterruptions.tasks.get(0).calendar==null||afterRepeatedInterruptions.tasks.get(0).calendar.reminderMinutes!=30)throw new AssertionError("repeated interruptions evicted backup calendar settings");
        String oldKey="synthetic-v1-session";Files.write(root.resolve(stem(oldKey)+".meeting"),legacyMeeting(oldKey));
        MeetingStore.Snapshot legacy=store.load(oldKey);if(!legacy.transcript.equals("旧转写")||legacy.tasks.get(0).calendar!=null)throw new AssertionError("v1 meeting migration failed");
        if(!store.save(oldKey,legacy.revision,legacy.transcript,legacy.notes,legacy.tasks).transcript.equals("旧转写"))throw new AssertionError("v1 update failed");
        String v2="synthetic-v2-session";Path v2file=root.resolve(stem(v2)+".meeting");Files.write(v2file,priorV2Meeting(v2));
        MeetingStore.Snapshot priorV2=store.load(v2);if(priorV2.tasks.get(0).calendar.reminderMinutes!=30)throw new AssertionError("v2 choices not read");
        store.save(v2,priorV2.revision,priorV2.transcript,priorV2.notes,priorV2.tasks);
        if(java.nio.ByteBuffer.wrap(Files.readAllBytes(v2file)).getInt()!=0x434d5731||store.load(v2).tasks.get(0).calendar.reminderMinutes!=30)throw new AssertionError("v2 migration lost settings");
        System.out.println("PASS local meeting persistence, concurrent edits and backup recovery");
    }
}
