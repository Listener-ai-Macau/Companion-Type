package com.denzic.companion.mobile;

import java.io.IOException;

/** Prepare calendar data locally; importing it remains an explicit user action. */
public final class NativeCalendar {
    private NativeCalendar() {}
    private static native String exportJson(String request) throws IOException;
    /** JSON request and response are documented in the backend README. Call on a worker thread. */
    public static String export(String request) throws IOException {
        if(request==null)throw new IllegalArgumentException("calendar request required");
        try{System.loadLibrary("companion_mobile_audio");return exportJson(request);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile calendar library is not installed for this device",error);}
    }

    /** Export saved task choices. A changed deadline asks for review before reusing them. */
    public static String exportSaved(MeetingStore.Snapshot meeting,String title,boolean reviewedChangedDates) throws IOException {
        if(meeting==null||title==null)throw new IllegalArgumentException("saved meeting and title required");
        StringBuilder tasks=new StringBuilder(),reminders=new StringBuilder(),slots=new StringBuilder();
        for(MeetingStore.Task task:meeting.tasks){
            if(tasks.length()>0)tasks.append(',');
            tasks.append("{\"id\":").append(json(task.id)).append(",\"text\":").append(json(task.text))
                .append(",\"completed\":").append(task.completed).append(",\"due\":").append(json(task.due)).append('}');
            MeetingStore.CalendarSettings setting=task.calendar;
            if(task.completed||setting==null)continue;
            if(task.calendarNeedsReview()&&!reviewedChangedDates)throw new IOException("请先核对之前的提醒和执行时段。");
            String uid=calendarUid(meeting.sessionKey,task.id);
            if(setting.reminderMinutes!=null||setting.reminderAt!=null){
                if(reminders.length()>0)reminders.append(',');reminders.append("{\"uid\":").append(json(uid)).append(",\"reminder\":{");
                if(setting.reminderMinutes!=null)reminders.append("\"kind\":\"before\",\"minutes\":").append(setting.reminderMinutes);
                else reminders.append("\"kind\":\"at\",\"at\":").append(json(setting.reminderAt));
                reminders.append("}}");
            }
            if(setting.slotStart!=null){
                if(slots.length()>0)slots.append(',');slots.append("{\"uid\":").append(json(uid)).append(",\"slot\":{\"start\":")
                    .append(json(setting.slotStart)).append(",\"end\":").append(json(setting.slotEnd)).append("}}");
            }
        }
        String request="{\"sessionKey\":"+json(meeting.sessionKey)+",\"title\":"+json(title)+",\"tasks\":["+tasks+
            "],\"reminders\":["+reminders+"],\"slots\":["+slots+"]}";
        return export(request);
    }
    private static String calendarUid(String session,String id) {
        try {
            java.security.MessageDigest hash=java.security.MessageDigest.getInstance("SHA-256");
            for(String field:new String[]{"companion-mobile-calendar-task",session,id}){
                byte[] value=field.getBytes(java.nio.charset.StandardCharsets.UTF_8);long n=value.length;
                for(int i=7;i>=0;i--)hash.update((byte)(n>>>(i*8)));hash.update(value);
            }
            StringBuilder out=new StringBuilder();for(byte b:hash.digest())out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return out+"@companion-mobile";
        }catch(java.security.NoSuchAlgorithmException e){throw new AssertionError(e);}
    }
    private static String json(String value) {
        if(value==null)return "null";StringBuilder out=new StringBuilder("\"");
        for(int i=0;i<value.length();i++){char c=value.charAt(i);if(c=='\"'||c=='\\')out.append('\\').append(c);
            else if(c<32)out.append(String.format(java.util.Locale.ROOT,"\\u%04x",(int)c));else out.append(c);}
        return out.append('\"').toString();
    }
}
