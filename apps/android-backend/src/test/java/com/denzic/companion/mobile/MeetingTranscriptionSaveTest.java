package com.denzic.companion.mobile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Collections;

/** Normal recognition, retry, and edits made while recognition was running. */
public final class MeetingTranscriptionSaveTest {
    private interface Checked {void run()throws Exception;}
    private static void fails(Checked action)throws Exception {
        try{action.run();throw new AssertionError("expected conflict");}catch(java.io.IOException expected){}
    }
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory(Paths.get(args[0]),"transcript-save-");
        MeetingStore store=new MeetingStore(root);String key="device:epoch:meeting";
        MeetingStore.Snapshot first=store.saveTranscription(key,null,"第一次转写");
        if(first.revision!=1||!first.transcript.equals("第一次转写")||!first.notes.isEmpty()||!first.tasks.isEmpty())throw new AssertionError("first transcription was not saved");
        if(store.saveTranscription(key,null,"第一次转写").revision!=1)throw new AssertionError("same result should be idempotent");
        MeetingStore.Task task=new MeetingStore.Task("task","发报价",null,"2026-11-06",false,new MeetingStore.CalendarSettings(30,null,null,null));
        store.save(key,1,first.transcript,"人工备注",Collections.singletonList(task));
        MeetingStore.Snapshot updated=store.saveTranscription(key,first.transcript,"重新识别结果");
        if(updated.revision!=3||!updated.notes.equals("人工备注")||updated.tasks.size()!=1||updated.tasks.get(0).calendar==null||updated.tasks.get(0).calendar.reminderMinutes!=30)
            throw new AssertionError("recognition replaced notes, tasks or reminder");
        MeetingStore.Snapshot reopened=new MeetingStore(root).load(key);
        if(!reopened.transcript.equals("重新识别结果")||!reopened.notes.equals("人工备注")||reopened.tasks.get(0).calendar.reminderMinutes!=30)
            throw new AssertionError("recognized text or user content did not reopen");
        store.save(key,3,"人工修正","人工备注",reopened.tasks);
        fails(()->store.saveTranscription(key,"重新识别结果","过期的识别结果"));
        fails(()->store.saveTranscription(key,null,"不应覆盖"));
        if(!store.load(key).transcript.equals("人工修正"))throw new AssertionError("concurrent transcript edit was overwritten");
        String missing="different-session";
        fails(()->store.saveTranscription(missing,"原有文字","不能恢复的识别"));
        if(store.load(missing)!=null)throw new AssertionError("missing meeting was silently recreated");
        System.out.println("PASS transcription save, retry, user edits and calendar preservation");
    }
}
