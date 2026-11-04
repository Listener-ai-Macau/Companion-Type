package com.denzic.companion.app;

import com.denzic.companion.mobile.MeetingStore;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Converts the existing durable history to the presentation contract. */
final class MinutesHistoryAccess {
    static JSONObject list(MeetingStore store, String key) throws Exception {
        MeetingStore.MinutesHistory history=store.listMinutesHistory(key);
        JSONArray versions=new JSONArray();int unreadable=history.unreadableFiles;
        for(MeetingStore.Minutes item:history.versions) {
            JSONObject content=content(item.json);
            if(content!=null) {
                versions.put(new JSONObject().put("historyId",item.historyId).put("revision",item.revision)
                    .put("sourceChanged",item.sourceChanged||item.sourceMissing).put("content",content));
            } else { unreadable++; }
        }
        return new JSONObject().put("versions",versions).put("unreadableCount",unreadable);
    }
    static JSONObject content(String text) {
        try { return new JSONObject(text); } catch(JSONException malformed) { return null; }
    }
    static JSONObject restore(MeetingStore store,String key,long meetingRevision,long minutesRevision,String historyId) throws Exception {
        try {
            MeetingStore.Minutes restored=store.restoreMinutesHistory(key,meetingRevision,minutesRevision,historyId);
            return new JSONObject().put("revision",restored.revision).put("sourceChanged",restored.sourceChanged||restored.sourceMissing);
        } catch(java.io.IOException conflict) {
            throw new java.io.IOException("未能确认恢复结果，请返回录音库后重新打开再检查；不会主动删除已有版本。",conflict);
        }
    }
    private MinutesHistoryAccess() {}
}
