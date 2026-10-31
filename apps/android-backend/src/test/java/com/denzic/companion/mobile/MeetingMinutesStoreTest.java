package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Collections;

/** Exercises saved AI minutes independently of a phone, device or cloud service. */
public final class MeetingMinutesStoreTest {
    private interface Checked {void run() throws Exception;}
    private static void expectFailure(Checked action)throws Exception {
        try{action.run();throw new AssertionError("operation unexpectedly succeeded");}catch(IOException expected){}
    }
    private static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    private static String stem(String key)throws Exception {
        StringBuilder result=new StringBuilder();
        for(byte b:MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8)))result.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
        return result.toString();
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);Files.createDirectories(root);
        MeetingStore store=new MeetingStore(root);String key="device:epoch:meeting-a";
        String transcript="明天下午讨论包装，小王周五发送报价。";
        MeetingStore.Task task=new MeetingStore.Task("task-1","发送报价","小王","周五",false);
        MeetingStore.Snapshot meeting=store.save(key,0,transcript,"用户自己的备注",Collections.singletonList(task));
        check(store.loadMinutes(key)==null,"new meeting must not invent minutes");
        String first="{\"quality\":\"final\",\"summary\":[\"讨论包装\"]}";
        MeetingStore.Minutes saved=store.saveMinutes(key,meeting.revision,0,transcript,first);
        check(saved.revision==1&&!saved.sourceChanged,"initial minutes were not saved");
        MeetingStore reopened=new MeetingStore(root);MeetingStore.Minutes loaded=reopened.loadMinutes(key);
        check(loaded.json.equals(first)&&loaded.sourceMeetingRevision==1&&!loaded.sourceChanged,"minutes did not survive reopen");
        MeetingStore.Snapshot original=reopened.load(key);
        check(original.transcript.equals(transcript)&&original.notes.equals("用户自己的备注")&&original.tasks.size()==1,"saving minutes changed meeting data");

        expectFailure(()->store.saveMinutes(key,1,0,transcript,"stale result"));
        expectFailure(()->store.saveMinutes(key,1,1,"different source","wrong source result"));
        check(store.loadMinutes(key).json.equals(first),"conflict overwrote saved minutes");
        meeting=store.save(key,1,transcript,"补充说明",Collections.singletonList(task));
        check(!store.loadMinutes(key).sourceChanged,"notes-only edit must not invalidate the same transcript");
        expectFailure(()->store.saveMinutes(key,1,1,transcript,"old meeting revision"));
        String second="{\"quality\":\"draft\",\"summary\":[\"需要核对\"]}";
        saved=store.saveMinutes(key,meeting.revision,1,transcript,second);
        check(saved.revision==2&&reopened.loadMinutes(key).json.equals(second),"second result did not persist");

        String changed=transcript+"会议改到下周。";
        meeting=store.save(key,meeting.revision,changed,"补充说明",Collections.singletonList(task));
        check(store.loadMinutes(key).sourceChanged&&store.loadMinutes(key).json.equals(second),"changed transcript must retain and flag old minutes");
        long currentRevision=meeting.revision;
        expectFailure(()->store.saveMinutes(key,currentRevision,2,transcript,"stale source"));
        String third="{\"quality\":\"final\",\"summary\":[\"会议改期\"]}";
        saved=store.saveMinutes(key,currentRevision,2,changed,third);
        check(saved.revision==3&&!saved.sourceChanged,"new transcript minutes not saved");

        Path main=root.resolve(stem(key)+".minutes"),backup=root.resolve(stem(key)+".minutes-backup");
        byte[] verifiedBackup=Files.readAllBytes(backup);Files.write(main,new byte[]{1,2,3});
        loaded=reopened.loadMinutes(key);
        check(loaded.recoveredFromBackup&&loaded.revision==2&&loaded.sourceChanged&&loaded.json.equals(second),"damaged latest minutes must recover prior result and flag its source");
        saved=store.saveMinutes(key,currentRevision,2,changed,third);
        check(saved.revision==3&&!saved.recoveredFromBackup,"save after recovery failed");
        check(java.util.Arrays.equals(verifiedBackup,Files.readAllBytes(backup)),"recovery replaced the good backup");
        try(java.util.stream.Stream<Path> files=Files.list(root)){
            check(files.anyMatch(p->p.getFileName().toString().startsWith(uncheckedStem(key)+".minutes-damaged-")),"damaged result was not retained");
        }
        Files.move(root.resolve(stem(key)+".meeting"),root.resolve("meeting-unavailable.fixture"));
        if(Files.exists(root.resolve(stem(key)+".backup")))Files.move(root.resolve(stem(key)+".backup"),root.resolve("backup-unavailable.fixture"));
        loaded=reopened.loadMinutes(key);
        check(loaded.sourceMissing&&loaded.sourceChanged&&loaded.json.equals(third),"missing source must not hide saved minutes");
        expectFailure(()->store.saveMinutes(key,currentRevision,3,changed,"no source"));

        String longKey="device:epoch:long-meeting";String longText="讨论产品包装和交货时间。".repeat(3500);
        MeetingStore.Snapshot longMeeting=store.save(longKey,0,longText,"",Collections.emptyList());
        String longJson="{\"summary\":\""+"长期会议内容".repeat(12000)+"\"}";
        store.saveMinutes(longKey,longMeeting.revision,0,longText,longJson);
        check(new MeetingStore(root).loadMinutes(longKey).json.equals(longJson),"long meeting result was truncated");
        check(store.loadMinutes("different-session")==null,"minutes leaked across meeting identities");
        check(store.deleteMinutes(key)==3,"explicit deletion must remove this session's minutes, backup and damaged copy");
        check(store.loadMinutes(key)==null&&Files.exists(root.resolve("meeting-unavailable.fixture")),"deletion touched the original meeting");
        check(store.loadMinutes(longKey).json.equals(longJson),"deletion touched a different meeting");
        check(store.deleteMinutes(longKey)==1&&store.load(longKey).transcript.equals(longText),"deleting minutes must retain the current transcript");
        String brokenKey="device:epoch:broken-minutes";
        MeetingStore.Snapshot brokenMeeting=store.save(brokenKey,0,"原文仍在","",Collections.emptyList());
        store.saveMinutes(brokenKey,brokenMeeting.revision,0,brokenMeeting.transcript,"{\"summary\":[]}");
        Files.write(root.resolve(stem(brokenKey)+".minutes"),new byte[]{4,5});
        expectFailure(()->store.loadMinutes(brokenKey));
        check(store.deleteMinutes(brokenKey)==1&&store.load(brokenKey).transcript.equals("原文仍在"),"explicit delete must work on a damaged result without touching the meeting");
        System.out.println("PASS Android minutes: save/reopen, source changes, stale edits, backup recovery and long result");
    }
    private static String uncheckedStem(String key){try{return stem(key);}catch(Exception e){throw new AssertionError(e);}}
}
