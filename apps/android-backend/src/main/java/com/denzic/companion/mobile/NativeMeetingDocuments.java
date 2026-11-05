package com.denzic.companion.mobile;

import java.io.IOException;

/** Documents for an already saved meeting. Call on a worker thread. No upload. */
public final class NativeMeetingDocuments {
    private NativeMeetingDocuments() {}
    private static native byte[] exportSavedNative(String title,String savedMinutesJson,String extra,boolean stale,boolean word) throws IOException;
    private static native String savedTextNative(String savedMinutesJson,boolean stale) throws IOException;
    /** Word document bytes; the host UI chooses where to save or share them. */
    public static byte[] word(String title,MeetingStore.Minutes minutes,MeetingStore.Snapshot meeting) throws IOException {
        return export(title,minutes,meeting,true);
    }
    /** FreeMind-compatible .mm bytes; opening or sharing is a host UI choice. */
    public static byte[] mindmap(String title,MeetingStore.Minutes minutes,MeetingStore.Snapshot meeting) throws IOException {
        return export(title,minutes,meeting,false);
    }
    public static String savedText(MeetingStore.Minutes minutes,MeetingStore.Snapshot meeting) throws IOException {
        if(minutes==null)throw new IllegalArgumentException("saved minutes required");
        if(meeting!=null&&!minutes.sessionKey.equals(meeting.sessionKey))throw new IllegalArgumentException("meeting and minutes belong to different sessions");
        try {System.loadLibrary("companion_mobile_audio");return savedTextNative(minutes.json,minutes.sourceChanged||minutes.sourceMissing||meeting==null||meeting.revision!=minutes.sourceMeetingRevision);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile document library is not installed for this device",error);}
    }
    static byte[] wordContent(String title,String markdown)throws IOException{
        try{
            String json=new org.json.JSONObject().put("markdown",markdown).toString();
            System.loadLibrary("companion_mobile_audio");return exportSavedNative(title,json,"",false,true);
        }catch(org.json.JSONException error){throw new IOException("文档内容无法读取。",error);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile document library is not installed for this device",error);}
    }
    private static byte[] export(String title,MeetingStore.Minutes minutes,MeetingStore.Snapshot meeting,boolean word) throws IOException {
        if(title==null||minutes==null)throw new IllegalArgumentException("saved minutes and title required");
        if(meeting!=null&&!minutes.sessionKey.equals(meeting.sessionKey))throw new IllegalArgumentException("meeting and minutes belong to different sessions");
        StringBuilder extra=new StringBuilder();
        if(meeting!=null&&meeting.notes!=null&&!meeting.notes.trim().isEmpty())extra.append("## 用户补充\n").append(meeting.notes).append('\n');
        if(meeting!=null&&!meeting.tasks.isEmpty()) {
            extra.append("## 当前任务\n");
            for(MeetingStore.Task task:meeting.tasks) {
                extra.append(task.completed?"- [x] ":"- [ ] ").append(task.text);
                if(task.owner!=null&&!task.owner.trim().isEmpty())extra.append(" (owner: ").append(task.owner).append(')');
                if(task.due!=null&&!task.due.trim().isEmpty())extra.append(" (due: ").append(task.due).append(')');
                extra.append('\n');
            }
        }
        try {System.loadLibrary("companion_mobile_audio");return exportSavedNative(title,minutes.json,extra.toString(),minutes.sourceChanged||minutes.sourceMissing||meeting==null||meeting.revision!=minutes.sourceMeetingRevision,word);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile document library is not installed for this device",error);}
    }
}
