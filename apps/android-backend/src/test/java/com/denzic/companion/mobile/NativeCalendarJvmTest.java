package com.denzic.companion.mobile;

import java.io.IOException;

public final class NativeCalendarJvmTest {
    public static void main(String[] args) throws Exception {
        String input = "{\"sessionKey\":\"synthetic\",\"title\":\"Meeting\","
            + "\"tasks\":[{\"text\":\"Review sample\",\"completed\":false,"
            + "\"due\":\"2026-11-02T14:00:00+08:00\"}],\"reminderMinutes\":30}";
        String output = NativeCalendar.export(input);
        if (!output.contains("DTSTART:20261102T060000Z") || !output.contains("PT30M"))
            throw new AssertionError("calendar result missing expected time or reminder");
        try {
            NativeCalendar.export("{}");
            throw new AssertionError("invalid request was accepted");
        } catch (IOException expected) { }
        java.nio.file.Path root=java.nio.file.Files.createTempDirectory(java.nio.file.Paths.get(args[0]),"calendar-bridge-");
        MeetingStore store=new MeetingStore(root);String key="synthetic-会话";
        MeetingStore.CalendarSettings settings=new MeetingStore.CalendarSettings(30,null,"2026-11-02T14:00:00+08:00","2026-11-02T15:00:00+08:00");
        MeetingStore.Task task=new MeetingStore.Task("task-一\"","检查样品",null,"2026-11-02T16:00:00+08:00",false,settings);
        MeetingStore.Snapshot saved=store.save(key,0,"测试原文","",java.util.Collections.singletonList(task));
        String first=NativeCalendar.exportSaved(saved,"测试\n报价",false);
        if(!first.contains("20261102T073000Z")||!first.contains("20261102T060000Z"))throw new AssertionError("saved reminder or slot missing");
        MeetingStore.Task moved=new MeetingStore.Task("task-一\"","检查蓝色样品",null,"2026-11-03T16:00:00+08:00",false);
        MeetingStore.Snapshot changed=store.save(key,1,"测试原文","",java.util.Collections.singletonList(moved));
        try{NativeCalendar.exportSaved(changed,"测试",false);throw new AssertionError("changed date was not surfaced");}catch(IOException expected){}
        String reviewed=NativeCalendar.exportSaved(changed,"测试",true);
        if(!reviewed.contains("20261103T073000Z")||!reviewed.contains("20261102T060000Z"))throw new AssertionError("rescheduled reminder or saved slot lost");
        java.util.regex.Matcher firstUid=java.util.regex.Pattern.compile("[a-f0-9]{64}@companion-mobile").matcher(first);
        if(!firstUid.find()||!reviewed.contains(firstUid.group()))throw new AssertionError("calendar identity changed after edit");
        System.out.println("NativeCalendar JNI test passed");
    }
}
