package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** Capture and select saved text; no network, inference or source writes. */
final class ExportContents {
    static final String[] IDS={"minutes","transcript","translation","notes"};
    static String language(String id){if("en".equals(id))return "英语";if("zh".equals(id))return "简体中文";if("ja".equals(id))return "日语";if("ko".equals(id))return "韩语";return id;}
    static final class Source{
        final String key,title,token;final MeetingStore.Snapshot meeting;final MeetingStore.Minutes minutes;final TranslationStore.Entry translation;final JSONArray problems;
        Source(String key,String title,String token,MeetingStore.Snapshot m,MeetingStore.Minutes n,TranslationStore.Entry tr,JSONArray errors){this.key=key;this.title=title;this.token=token;meeting=m;minutes=n;translation=tr;problems=errors;}
        JSONObject info()throws Exception{
            boolean text=meeting!=null&&!meeting.transcript.trim().isEmpty(),note=meeting!=null&&(!meeting.notes.trim().isEmpty()||!meeting.tasks.isEmpty());
            JSONObject min=null;if(minutes!=null)try{min=new JSONObject(minutes.json);}catch(JSONException ignored){}
            boolean hasMinutes=min!=null&&!min.optString("markdown","").trim().isEmpty();boolean stale=minutes!=null&&(minutes.sourceChanged||minutes.sourceMissing||meeting==null||minutes.sourceMeetingRevision!=meeting.revision);
            boolean trStale=translation!=null&&(meeting==null||!translation.matches(meeting.transcript));
            String binding=MinutesTemplateLibrary.hash((token+"\u0000"+key+"\u0000"+title+"\u0000"+(meeting==null?0:meeting.revision)+"\u0000"+(minutes==null?0:minutes.revision)+"\u0000"+(translation==null?"":translation.source+"\u0000"+translation.text+"\u0000"+translation.language)).getBytes(StandardCharsets.UTF_8));
            return new JSONObject().put("key",key).put("title",title).put("libraryToken",token).put("binding",binding).put("available",new JSONObject().put("minutes",hasMinutes).put("transcript",text).put("translation",translation!=null).put("notes",note)).put("minutesStale",stale).put("minutesDraft",hasMinutes&&("draft".equals(min.optString("quality"))||min.optJSONObject("processing")!=null&&!min.getJSONObject("processing").optBoolean("complete",true))).put("minutesManual",hasMinutes&&min.optJSONObject("manualReview")!=null).put("translationStale",trStale).put("translationLanguage",translation==null?"":language(translation.language)).put("problems",problems);
        }
        List<MeetingDocumentSections.Section> select(JSONArray selected)throws Exception{
            if(selected==null||selected.length()==0||selected.length()>4)throw new IOException("请至少选择一项内容。");Set<String> ids=new HashSet<>();JSONObject info=info(),available=info.getJSONObject("available");
            for(int i=0;i<selected.length();i++){String id=selected.getString(i);if(!Arrays.asList(IDS).contains(id)||!ids.add(id)||!available.optBoolean(id))throw new IOException("所选内容已不可用，请重新读取导出选项。");}
            List<MeetingDocumentSections.Section> result=new ArrayList<>();
            if(ids.contains("minutes")){
                String body=NativeMeetingDocuments.savedText(minutes,meeting);if(info.getBoolean("minutesManual")&&!body.contains("人工修订"))body="> 人工修订：此版本含人工核对或安排，请结合原文确认。\n\n"+body;
                result.add(new MeetingDocumentSections.Section("会议纪要",body,true));
            }
            if(ids.contains("transcript"))result.add(new MeetingDocumentSections.Section("会议转写",meeting.transcript,false));
            if(ids.contains("translation")){String body=translation.text;if(info.getBoolean("translationStale"))body="来源提示：译文依据较早或暂不可读取的原文版本，请核对。\n\n"+body;result.add(new MeetingDocumentSections.Section("译文（"+language(translation.language)+"）",body,false));}
            if(ids.contains("notes")){
                StringBuilder text=new StringBuilder(meeting.notes);for(MeetingStore.Task task:meeting.tasks){text.append('\n').append(task.completed?"[已完成] ":"[待跟进] ").append(task.text);if(task.owner!=null&&!task.owner.trim().isEmpty())text.append("\n负责人：").append(task.owner);if(task.due!=null&&!task.due.trim().isEmpty())text.append("\n时间：").append(task.due);text.append('\n');}
                result.add(new MeetingDocumentSections.Section("用户补充与事项",text.toString(),false));
            }return result;
        }
    }
    static JSONArray warnings(JSONObject info,JSONArray sections)throws Exception{
        Set<String> ids=new HashSet<>();for(int i=0;i<sections.length();i++)ids.add(sections.getString(i));JSONArray out=new JSONArray();
        if(ids.contains("minutes")&&info.getBoolean("minutesStale"))out.put("纪要依据的原文已变化或暂不可用，文件中保留来源提示。");
        if(ids.contains("minutes")&&info.getBoolean("minutesDraft"))out.put("包含未完成的纪要草稿，文件中保留草稿提示。");
        if(ids.contains("minutes")&&info.getBoolean("minutesManual"))out.put("包含人工核对或安排，请核对负责人和时间。");
        if(ids.contains("translation")&&info.getBoolean("translationStale"))out.put("译文依据较早的原文版本，文件中保留提示。");return out;
    }
    static String srt(MeetingStore.TranscriptTiming timing)throws IOException{
        if(timing==null||timing.windows.isEmpty())throw new IOException("当前原文没有可核验的分段时间，请选择TXT、Markdown、PDF或Word；修改后的文字不会补造字幕时间。");StringBuilder out=new StringBuilder();int index=0;long start=-1;
        for(MeetingStore.TranscriptWindow w:timing.windows){if(w.startMs<start||w.endMs>timing.durationMs)throw new IOException("分段时间需要重新核对，请选择其它文字格式。");start=w.startMs;out.append(++index).append('\n').append(time(w.startMs)).append(" --> ").append(time(w.endMs)).append('\n').append(w.text.replaceAll("[\\r\\n]+"," ")).append("\n\n");}return out.toString();
    }
    private static String time(long ms){return String.format(Locale.ROOT,"%02d:%02d:%02d,%03d",ms/3600000,(ms/60000)%60,(ms/1000)%60,ms%1000);}
}
