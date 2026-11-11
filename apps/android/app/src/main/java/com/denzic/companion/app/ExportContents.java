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
        final String key,title,token;final MeetingStore.Snapshot meeting;final MeetingStore.Minutes minutes;final TranslationStore.Entry translation;final JSONArray problems,materials;final JSONObject notes;
        Source(String key,String title,String token,MeetingStore.Snapshot m,MeetingStore.Minutes n,TranslationStore.Entry tr,JSONArray errors){this(key,title,token,m,n,tr,errors,new JSONArray());}
        Source(String key,String title,String token,MeetingStore.Snapshot m,MeetingStore.Minutes n,TranslationStore.Entry tr,JSONArray errors,JSONArray savedMaterials){this(key,title,token,m,n,tr,errors,savedMaterials,null);}
        Source(String key,String title,String token,MeetingStore.Snapshot m,MeetingStore.Minutes n,TranslationStore.Entry tr,JSONArray errors,JSONArray savedMaterials,JSONObject savedNotes){notes=savedNotes;this.key=key;this.title=title;this.token=token;meeting=m;minutes=n;translation=tr;problems=errors;materials=savedMaterials;}
        JSONObject info()throws Exception{
            boolean text=meeting!=null&&!meeting.transcript.trim().isEmpty(),note=meeting!=null&&(!meeting.notes.trim().isEmpty()||!meeting.tasks.isEmpty())||notes!=null&&notes.getJSONArray("entries").length()>0;
            JSONObject min=null;if(minutes!=null)try{min=new JSONObject(minutes.json);}catch(JSONException ignored){}
            boolean hasMinutes=min!=null&&!min.optString("markdown","").trim().isEmpty();boolean stale=minutes!=null&&(minutes.sourceChanged||minutes.sourceMissing||meeting==null||minutes.sourceMeetingRevision!=meeting.revision);
            boolean trStale=translation!=null&&(meeting==null||!translation.matches(meeting.transcript));
            String binding=MinutesTemplateLibrary.hash((token+"\u0000"+key+"\u0000"+title+"\u0000"+(meeting==null?0:meeting.revision)+"\u0000"+(minutes==null?0:minutes.revision)+"\u0000"+(translation==null?"":translation.source+"\u0000"+translation.text+"\u0000"+translation.language)+"\u0000"+materialBinding()+"\u0000"+(notes==null?"":canonical(notes))).getBytes(StandardCharsets.UTF_8));
            return new JSONObject().put("key",key).put("title",title).put("libraryToken",token).put("binding",binding).put("available",new JSONObject().put("minutes",hasMinutes).put("transcript",text).put("translation",translation!=null).put("notes",note)).put("minutesStale",stale).put("minutesDraft",hasMinutes&&("draft".equals(min.optString("quality"))||min.optJSONObject("processing")!=null&&!min.getJSONObject("processing").optBoolean("complete",true))).put("minutesManual",hasMinutes&&min.optJSONObject("manualReview")!=null).put("translationStale",trStale).put("translationLanguage",translation==null?"":language(translation.language)).put("problems",problems).put("materials",materialInfo()).put("manualNotes",noteInfo()).put("noteImages",imageCount());
        }
        private int imageCount()throws Exception{int count=0;if(notes!=null){JSONArray entries=notes.getJSONArray("entries");for(int i=0;i<entries.length();i++)if(entries.getJSONObject(i).has("image"))count++;}return count;}
        private boolean hasMaterial(String id)throws Exception{
            if(!id.startsWith("material:"))return false;
            for(int i=0;i<materials.length();i++)if(id.equals("material:"+materials.getJSONObject(i).getString("id")))return true;
            return false;
        }
        private JSONArray materialInfo()throws Exception{
            JSONArray result=new JSONArray();for(int i=0;i<materials.length();i++){JSONObject m=materials.getJSONObject(i);result.put(new JSONObject().put("id","material:"+m.getString("id")).put("title",m.getString("title")).put("edited",m.optBoolean("edited")));}return result;
        }
        private JSONArray noteInfo()throws Exception{
            JSONArray result=new JSONArray();if(notes==null)return result;JSONArray entries=notes.getJSONArray("entries");
            for(int i=0;i<entries.length();i++){JSONObject entry=entries.getJSONObject(i);String title=entry.optString("text","").split("\\r?\\n",2)[0].replaceFirst("^\\s*[-*]\\s+\\[[ xX]\\]\\s*","").trim();if(title.isEmpty())title=entry.has("image")?"图片备注":"人工补充";
                result.put(new JSONObject().put("id","note:"+entry.getString("id")).put("title",title).put("kind",entry.optString("kind","note")).put("image",entry.has("image")));}
            return result;
        }
        private boolean hasNote(String id)throws Exception{
            if(notes==null||!id.startsWith("note:"))return false;JSONArray entries=notes.getJSONArray("entries");
            for(int i=0;i<entries.length();i++)if(id.equals("note:"+entries.getJSONObject(i).getString("id")))return true;return false;
        }
        private Set<String> selection(JSONArray selected)throws Exception{
            int count=notes==null?0:notes.getJSONArray("entries").length();
            if(selected==null||selected.length()==0||selected.length()>IDS.length+materials.length()+count)throw new IOException("请选择可用的导出内容。");
            Set<String> ids=new HashSet<>();JSONObject available=info().getJSONObject("available");
            for(int i=0;i<selected.length();i++){String id=selected.getString(i);if(!(Arrays.asList(IDS).contains(id)?available.optBoolean(id):hasMaterial(id)||hasNote(id))||!ids.add(id))throw new IOException("所选内容已不可用，请重新读取导出选项。");}
            if(ids.contains("notes"))for(String id:ids)if(id.startsWith("note:"))throw new IOException("请在全部补充和单条补充之间选择一种范围。");
            return ids;
        }
        private JSONObject filteredNotes(Set<String> ids)throws Exception{
            JSONObject result=notes==null?new JSONObject():new JSONObject(notes.toString());JSONArray kept=new JSONArray();
            if(notes!=null){JSONArray entries=notes.getJSONArray("entries");for(int i=0;i<entries.length();i++){JSONObject entry=entries.getJSONObject(i);if(ids.contains("notes")||ids.contains("note:"+entry.getString("id")))kept.put(entry);}}
            return result.put("entries",kept);
        }
        JSONObject notesForBundle(JSONArray selected)throws Exception{return filteredNotes(selection(selected));}
        private String materialBinding()throws Exception{
            TreeMap<String,String> sorted=new TreeMap<>();for(int i=0;i<materials.length();i++){JSONObject m=materials.getJSONObject(i);sorted.put(m.getString("id"),canonical(m));}return canonical(new JSONObject(sorted));
        }
        private String materialText(JSONObject material)throws Exception{
            StringBuilder text=new StringBuilder("> AI 材料（需核对）：保留保存时的原话依据；可能包含错误或遗漏，请对照当前原文核对。\n");
            if(material.optBoolean("edited"))text.append("> 含人工编辑，请核对新增安排和事实。\n");
            JSONObject answer=material.optJSONObject("result");
            if(answer!=null&&answer.optBoolean("incomplete"))text.append("> 来自未完成的查询，可能遗漏内容。\n");
            return text.append('\n').append(material.getString("body")).toString();
        }
        private String materialCitations(JSONObject material)throws Exception{
            StringBuilder text=new StringBuilder("以下为保存材料时的原话，请对照当前原文核对。\n\n");JSONObject answer=material.optJSONObject("result");
            JSONArray items=answer==null?null:answer.optJSONArray("items");
            if(items==null||items.length()==0)text.append("未保存可核对引文，请手动核对原文。\n");
            else for(int i=0;i<items.length();i++){
                JSONObject citation=items.getJSONObject(i).optJSONObject("citation");if(citation==null){text.append("一条保存依据暂无法读取，请手动核对。\n");continue;}
                text.append(citation.optString("title","原文")).append("\n").append(citation.optString("quote","")).append("\n\n");
            }
            return text.toString();
        }
        List<MeetingDocumentSections.Section> select(JSONArray selected)throws Exception{
            Set<String> ids=selection(selected);JSONObject info=info();
            List<MeetingDocumentSections.Section> result=new ArrayList<>();
            if(ids.contains("minutes")){
                String body=NativeMeetingDocuments.savedText(minutes,meeting);if(info.getBoolean("minutesManual")&&!body.contains("人工修订"))body="> 人工修订：此版本含人工核对或安排，请结合原文确认。\n\n"+body;
                result.add(new MeetingDocumentSections.Section("会议纪要",body,true));
            }
            if(ids.contains("transcript"))result.add(new MeetingDocumentSections.Section("会议转写",meeting.transcript,false));
            if(ids.contains("translation")){String body=translation.text;if(info.getBoolean("translationStale"))body="来源提示：译文依据较早或暂不可读取的原文版本，请核对。\n\n"+body;result.add(new MeetingDocumentSections.Section("译文（"+language(translation.language)+"）",body,false));}
            if(ids.contains("notes")){
                StringBuilder text=new StringBuilder(meeting==null?"":meeting.notes);for(MeetingStore.Task task:meeting==null?Collections.<MeetingStore.Task>emptyList():meeting.tasks){text.append('\n').append(task.completed?"[已完成] ":"[待跟进] ").append(task.text);if(task.owner!=null&&!task.owner.trim().isEmpty())text.append("\n负责人：").append(task.owner);if(task.due!=null&&!task.due.trim().isEmpty())text.append("\n时间：").append(task.due);text.append('\n');}
                if(notes!=null)text.append("\n").append(RecordingNotes.text(notes));
                result.add(new MeetingDocumentSections.Section("用户补充与事项",text.toString(),false));
            }
            if(!ids.contains("notes")){
                JSONObject chosen=filteredNotes(ids);if(chosen.getJSONArray("entries").length()>0)result.add(new MeetingDocumentSections.Section("人工补充与跟进",RecordingNotes.text(chosen),false));
            }
            for(int i=0;i<materials.length();i++){
                JSONObject material=materials.getJSONObject(i);
                if(ids.contains("material:"+material.getString("id"))){
                    result.add(new MeetingDocumentSections.Section("AI 材料 · "+material.getString("title"),materialText(material),true));
                    result.add(new MeetingDocumentSections.Section("保存时的原文依据 · "+material.getString("title"),materialCitations(material),false));
                }
            }
            return result;
        }
    }
    private static String canonical(Object value)throws Exception{
        if(value instanceof JSONObject){JSONObject object=(JSONObject)value;TreeSet<String> keys=new TreeSet<>();Iterator<String> it=object.keys();while(it.hasNext())keys.add(it.next());StringBuilder out=new StringBuilder("{");for(String key:keys)out.append(JSONObject.quote(key)).append(':').append(canonical(object.get(key))).append(',');return out.append('}').toString();}
        if(value instanceof JSONArray){JSONArray array=(JSONArray)value;StringBuilder out=new StringBuilder("[");for(int i=0;i<array.length();i++)out.append(canonical(array.get(i))).append(',');return out.append(']').toString();}
        return value==null||value==JSONObject.NULL?"null":value instanceof String?JSONObject.quote((String)value):String.valueOf(value);
    }
    static JSONArray warnings(JSONObject info,JSONArray sections)throws Exception{
        Set<String> ids=new HashSet<>();for(int i=0;i<sections.length();i++)ids.add(sections.getString(i));JSONArray out=new JSONArray();
        if(ids.contains("minutes")&&info.getBoolean("minutesStale"))out.put("纪要依据的原文已变化或暂不可用，文件中保留来源提示。");
        if(ids.contains("minutes")&&info.getBoolean("minutesDraft"))out.put("包含未完成的纪要草稿，文件中保留草稿提示。");
        if(ids.contains("minutes")&&info.getBoolean("minutesManual"))out.put("包含人工核对或安排，请核对负责人和时间。");
        if(ids.contains("translation")&&info.getBoolean("translationStale"))out.put("译文依据较早的原文版本，文件中保留提示。");
        for(String id:ids)if(id.startsWith("material:")){out.put("包含已保存AI材料及保存时的原话依据，请对照当前原文核对。");break;}return out;
    }
    static String srt(MeetingStore.TranscriptTiming timing)throws IOException{
        if(timing==null||timing.windows.isEmpty())throw new IOException("当前原文没有可核验的分段时间，请选择TXT、Markdown、PDF或Word；修改后的文字不会补造字幕时间。");StringBuilder out=new StringBuilder();int index=0;long start=-1;
        for(MeetingStore.TranscriptWindow w:timing.windows){if(w.startMs<start||w.endMs>timing.durationMs)throw new IOException("分段时间需要重新核对，请选择其它文字格式。");start=w.startMs;out.append(++index).append('\n').append(time(w.startMs)).append(" --> ").append(time(w.endMs)).append('\n').append(w.text.replaceAll("[\\r\\n]+"," ")).append("\n\n");}return out.toString();
    }
    private static String time(long ms){return String.format(Locale.ROOT,"%02d:%02d:%02d,%03d",ms/3600000,(ms/60000)%60,(ms/1000)%60,ms%1000);}
}
