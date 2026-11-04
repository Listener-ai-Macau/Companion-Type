package com.denzic.companion.app;

import com.denzic.companion.mobile.MeetingStore;
import org.json.JSONObject;

/** Keep audio and readable text accessible when an independent saved component is damaged. */
final class MeetingDetailAccess {
    static JSONObject read(MeetingStore store,String key) throws Exception {
        return read(store,key,null);
    }
    static JSONObject read(MeetingStore store,String key,TranslationStore translations) throws Exception {
        MeetingStore.Snapshot meeting=null;MeetingStore.Minutes minutes=null;
        boolean textUnavailable=false,minutesUnavailable=false,beforeUnavailable=false;
        try { meeting=store.load(key); } catch(java.io.IOException error) { textUnavailable=true; }
        try { minutes=store.loadMinutes(key); } catch(java.io.IOException error) { minutesUnavailable=true; }
        String before=null;
        if(meeting!=null)try { before=store.loadTranscriptBeforeCorrection(key); } catch(java.io.IOException error) { beforeUnavailable=true; }
        JSONObject content=minutes==null ? null : MinutesHistoryAccess.content(minutes.json);
        TranslationStore.Entry translation=null;boolean translationUnavailable=false;
        if(translations!=null)try{translation=translations.load(key);}catch(java.io.IOException error){translationUnavailable=true;}
        return new JSONObject().put("transcript",meeting==null?"":meeting.transcript)
            .put("revision",meeting==null?0:meeting.revision).put("recovered",meeting!=null&&meeting.recoveredFromBackup)
            .put("transcriptUnreadable",textUnavailable).put("before",before==null?JSONObject.NULL:before)
            .put("beforeUnreadable",beforeUnavailable).put("minutes",content==null?JSONObject.NULL:content)
            .put("minutesRevision",minutes==null?0:minutes.revision)
            .put("minutesUnreadable",minutesUnavailable||(minutes!=null&&content==null))
            .put("minutesRecovered",minutes!=null&&minutes.recoveredFromBackup)
            .put("minutesChanged",minutes!=null&&(minutes.sourceChanged||minutes.sourceMissing))
            .put("translation",translation==null?JSONObject.NULL:translation(translation).put("saved",true))
            .put("translationUnreadable",translationUnavailable);
    }
    static JSONObject translation(TranslationStore.Entry entry) throws Exception {
        return new JSONObject().put("text",entry.text).put("language",entry.language)
            .put("source",entry.source).put("revision",entry.revision);
    }
    private MeetingDetailAccess() {}
}
