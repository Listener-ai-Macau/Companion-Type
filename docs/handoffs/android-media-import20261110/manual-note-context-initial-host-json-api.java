package com.denzic.companion.app;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Human-authored note metadata, independent of recognition and AI generation. */
final class ManualNoteContext {
    static final int MAX_REFERENCES=16,MAX_QUOTE=4000,MAX_TOTAL_QUOTES=16000;
    private static final Set<String> BASE=new HashSet<>(Arrays.asList("id","kind","name","sourceSha256","quote"));
    private static final Set<String> DOCUMENT=new HashSet<>(Arrays.asList("id","kind","name","sourceSha256","quote","documentId","extractionSha256","sectionId","sectionLabel","row"));
    private static IOException invalid(){return new IOException("人工引用的内容或身份无效；原备注和资料保留。");}
    private static boolean uuid(String text){try{return UUID.fromString(text).toString().equals(text);}catch(Exception ignored){return false;}}
    private static boolean sha(String text){return text.matches("[0-9a-f]{64}");}
    private static boolean controls(String text,boolean quote){for(int i=0;i<text.length();i++){char c=text.charAt(i);if(Character.isISOControl(c)&&!(quote&&(c=='\n'||c=='\r'||c=='\t')))return true;if(Character.isHighSurrogate(c)){if(i+1>=text.length()||!Character.isLowSurrogate(text.charAt(++i)))return true;}else if(Character.isLowSurrogate(c))return true;}return false;}
    static String kind(JSONObject note)throws Exception {
        if(!note.has("kind"))return "note";
        Object raw=note.get("kind");if(!(raw instanceof String)||!("note".equals(raw)||"followup".equals(raw)))throw invalid();return (String)raw;
    }
    static JSONArray references(JSONObject note)throws Exception {
        if(!note.has("references"))return new JSONArray();
        Object raw=note.get("references");if(!(raw instanceof JSONArray))throw invalid();JSONArray result=(JSONArray)raw;validate(result);return result;
    }
    static void validate(JSONArray refs)throws Exception {
        if(refs.length()>MAX_REFERENCES)throw new IOException("每条备注最多引用16处依据，请先整理已有引用；原资料保留。");Set<String> ids=new HashSet<>();int total=0;
        for(int i=0;i<refs.length();i++){
            JSONObject ref=refs.getJSONObject(i);String type=ref.getString("kind");boolean document="document".equals(type);
            if(!document&&!"transcript".equals(type))throw invalid();Set<String> allowed=document?DOCUMENT:BASE;
            if(!allowed.containsAll(ref.keySet())||!ref.keySet().containsAll(BASE))throw invalid();
            String id=ref.getString("id"),name=ref.getString("name"),quote=ref.getString("quote");
            if(quote.length()>MAX_QUOTE)throw new IOException("单处引用最多4000个字符，请选择更短的片段；完整原件仍保留。");
            if(!uuid(id)||!ids.add(id)||name.trim().isEmpty()||name.length()>200||controls(name,false)||!sha(ref.getString("sourceSha256"))||quote.trim().isEmpty()||controls(quote,true))throw invalid();
            total+=quote.length();if(total>MAX_TOTAL_QUOTES)throw new IOException("这条备注的引用文字超过16000个字符，请减少或分开保存；完整原件仍保留。");
            if(document){
                if(!uuid(ref.getString("documentId"))||!sha(ref.getString("extractionSha256")))throw invalid();
                String part=ref.getString("sectionId"),label=ref.getString("sectionLabel");
                if(!part.matches("part-[0-9]{1,3}")||Integer.parseInt(part.substring(5))<1||label.length()>160||controls(label,false))throw invalid();
                if(ref.has("row")){Object value=ref.get("row");if(!(value instanceof Integer||value instanceof Long))throw invalid();long row=((Number)value).longValue();if(row<1||row>1048576)throw invalid();}
            }else if(!"会议转写".equals(name))throw invalid();
        }
    }
    static String hash(String text)throws Exception {
        byte[] digest=MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));StringBuilder out=new StringBuilder();for(byte value:digest)out.append(String.format(Locale.ROOT,"%02x",value&255));return out.toString();
    }
    /** Verifies the exact saved reading representation, without making business inferences. */
    static void verifyDocument(JSONObject ref,JSONObject document,JSONObject extraction)throws Exception {
        validate(new JSONArray().put(ref));
        if(!"document".equals(ref.getString("kind"))||!ref.getString("documentId").equals(document.getString("id"))||!ref.getString("name").equals(document.getString("name"))||!ref.getString("sourceSha256").equals(document.getString("sourceSha256"))||!document.has("extraction")||!ref.getString("extractionSha256").equals(document.getJSONObject("extraction").getString("sha256"))||!ref.getString("sourceSha256").equals(extraction.getString("sourceSha256")))throw new IOException("材料或提取版本已变化，请重新选择依据；当前便签输入仍保留。");
        JSONArray sections=extraction.getJSONArray("sections");JSONObject section=null;
        for(int i=0;i<sections.length();i++)if(ref.getString("sectionId").equals(sections.getJSONObject(i).getString("id")))section=sections.getJSONObject(i);
        if(section==null||!ref.getString("sectionLabel").equals(section.getString("label")))throw invalid();
        if(ref.has("row")){
            JSONArray rows=section.optJSONArray("tableRows");JSONObject row=null;
            if(rows!=null)for(int i=0;i<rows.length();i++)if(rows.getJSONObject(i).getLong("row")==ref.getLong("row"))row=rows.getJSONObject(i);
            if(row==null||!tableQuote(row).equals(ref.getString("quote")))throw new IOException("所引用的单元格文字与已保存材料不符；未改变便签。");
        }else if(!section.getString("text").contains(ref.getString("quote")))throw new IOException("引用文字不在这段已保存材料中，请重新选择；输入仍保留。");
    }
    static String tableQuote(JSONObject row)throws Exception {
        StringBuilder out=new StringBuilder();JSONArray cells=row.getJSONArray("cells");
        for(int i=0;i<cells.length();i++){if(i>0)out.append('\n');JSONObject cell=cells.getJSONObject(i);out.append(cell.getString("column")).append(row.getLong("row")).append('\t').append(cell.getString("text"));}return out.toString();
    }
    static void verifyTranscript(JSONObject ref,String text)throws Exception {
        validate(new JSONArray().put(ref));if(!"transcript".equals(ref.getString("kind"))||!hash(text).equals(ref.getString("sourceSha256"))||!text.contains(ref.getString("quote")))throw new IOException("转写文字已变化或引文不匹配，请重新选择依据；便签输入仍保留。");
    }
    static boolean same(JSONObject a,JSONObject b){return a.similar(b);}
    interface Verifier {void verify(JSONObject reference)throws Exception;}
    /** Existing identical citations may remain when a source is later changed/deleted. */
    static JSONArray prepare(JSONArray previous,JSONArray proposed,Verifier verifier)throws Exception {
        validate(previous);validate(proposed);Map<String,JSONObject> old=new HashMap<>();for(int i=0;i<previous.length();i++){JSONObject ref=previous.getJSONObject(i);old.put(ref.getString("id"),ref);}
        for(int i=0;i<proposed.length();i++){JSONObject ref=proposed.getJSONObject(i),before=old.get(ref.getString("id"));if(before==null||!same(before,ref))verifier.verify(new JSONObject(ref.toString()));}
        return new JSONArray(proposed.toString());
    }
    private ManualNoteContext(){}
}
