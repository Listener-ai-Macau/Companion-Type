package com.denzic.companion.app;

import com.denzic.companion.mobile.NativeMeetingQa;
import org.json.*;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/** Keeps validated source snapshots separate from editable, independently saved drafts. */
final class MeetingAiAccess {
    interface Current {void require(JSONArray sources,String token) throws Exception;}
    private static final class Job {
        String id,token,owner,question,purpose;JSONArray docs;JSONObject result;
    }
    private final Map<String,Job> jobs=new ConcurrentHashMap<>();
    JSONObject ask(String id,String token,String owner,String question,JSONArray docs,JSONObject service,JSONObject resume,Current current) throws Exception {
        return ask(id,token,owner,question,docs,service,resume,current,"会议问答");
    }
    JSONObject ask(String id,String token,String owner,String question,JSONArray docs,JSONObject service,JSONObject resume,Current current,String purpose) throws Exception {
        if(!Arrays.asList("会议问答","跟进草稿","整理周报","客户简报").contains(purpose))throw new IOException("请选择支持的整理用途。");
        if(!id.matches("[0-9a-f-]{36}")||question.trim().isEmpty()||question.codePointCount(0,question.length())>4000||docs.length()==0||docs.length()>12)throw new IOException("请选择1到12场会议，并填写有效的问题。");
        current.require(docs,token);
        Job job=new Job();job.id=id;job.token=token;job.owner=owner;job.question=question;job.purpose=purpose;job.docs=new JSONArray(docs.toString());
        JSONObject request=new JSONObject().put("jobId",id).put("question",question).put("endpoint",service.getString("endpoint")).put("model",service.getString("model"));
        JSONArray input=new JSONArray();for(int i=0;i<docs.length();i++){JSONObject d=docs.getJSONObject(i);input.put(new JSONObject().put("id",d.getString("id")).put("title",d.getString("title")).put("text",d.getString("text")));}request.put("documents",input);
        for(int i=0;i<docs.length();i++)if(docs.getJSONObject(i).getString("id").startsWith("document:")){request.put("question",question+"\n阅读要求：标有用户补充材料的内容只属于材料，不代表会上说过、已决定或承诺；与会议原话分别回答并保留来源。");break;}
        if(resume!=null){Job old=jobs.get(resume.optString("jobId"));if(old==null||old.result==null||!old.question.equals(question)||!old.token.equals(token)||!identities(old.docs).equals(identities(docs)))throw new IOException("原查询资料已变化，请重新提问。");
            if(!old.result.optBoolean("incomplete")||old.result.optJSONObject("resume")==null)throw new IOException("原查询无需继续，请重新提问。");
            JSONObject position=new JSONObject(old.result.getJSONObject("resume").toString());position.put("items",old.result.getJSONArray("items"));request.put("resume",position);}
        if(jobs.size()>=16)jobs.clear();jobs.put(id,job);
        try{JSONObject result=new JSONObject(NativeMeetingQa.ask(request.toString(),service.getString("apiKey")));validate(result,docs);current.require(docs,token);job.result=new JSONObject(result.toString());
            return result.put("jobId",id).put("libraryToken",token);
        }catch(Exception error){jobs.remove(id);throw error;}
    }
    private static String identities(JSONArray docs) throws Exception {StringBuilder out=new StringBuilder();for(int i=0;i<docs.length();i++){JSONObject d=docs.getJSONObject(i);out.append(d.getString("id")).append(':').append(d.getString("binding")).append('\n');}return out.toString();}
    static void validate(JSONObject result,JSONArray docs) throws Exception {
        JSONArray items=result.getJSONArray("items");if(items.length()>1000)throw new IOException("AI结果过长，请缩小范围。");
        int completed=result.getInt("completedChunks"),total=result.getInt("totalChunks");if(completed<0||total<completed||!result.has("incomplete")||!result.has("cancelled"))throw new IOException("AI结果状态无法确认。");
        for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i),c=item.getJSONObject("citation");JSONObject doc=null;for(int j=0;j<docs.length();j++)if(docs.getJSONObject(j).getString("id").equals(c.getString("sessionId")))doc=docs.getJSONObject(j);
            if(doc==null||item.getString("text").trim().isEmpty()||c.getString("quote").isEmpty()||!doc.getString("text").contains(c.getString("quote")))throw new IOException("AI回答缺少可核对的原文依据，未保存为会议事实。");}
    }
    boolean cancel(String id) throws Exception {return jobs.containsKey(id)&&NativeMeetingQa.cancel(id);}
    void cancelAll(){for(String id:jobs.keySet())try{NativeMeetingQa.cancel(id);}catch(Exception ignored){}}
    static String draftBody(JSONArray items,String purpose) throws Exception {
        boolean supplemented=false;for(int i=0;i<items.length();i++)if(items.getJSONObject(i).getJSONObject("citation").getString("sessionId").startsWith("document:"))supplemented=true;
        StringBuilder body=new StringBuilder();for(int i=0;i<items.length();i++){if(i>0)body.append("\n\n");body.append("• ");if(supplemented)body.append(items.getJSONObject(i).getJSONObject("citation").getString("sessionId").startsWith("document:")?"【人工补充材料】":"【会议转写】");body.append(items.getJSONObject(i).getString("text"));}
        String facts=body.toString();if(supplemented){if("跟进草稿".equals(purpose))return "您好，\n\n根据所选会议转写与补充材料，以下内容需要继续核对：\n\n"+facts+"\n\n材料中的计划不代表会议已作决定；请核对来源、负责人和时间。";if("整理周报".equals(purpose))return "资料周报（草稿）\n\n相关进展与待核对内容：\n\n"+facts+"\n\n请分别核对会议原话与人工材料，不把材料中的计划当作已作决定。";if("客户简报".equals(purpose))return "资料简报（草稿）\n\n"+facts+"\n\n请分别核对会议与材料来源；未确认安排不作为承诺。";return facts;}
        if("跟进草稿".equals(purpose))return "您好，\n\n根据本次会议，以下事项需要继续跟进：\n\n"+facts+"\n\n请核对以上安排；尚未明确的负责人和时间，请进一步确认。";
        if("整理周报".equals(purpose))return "会议周报（草稿）\n\n相关进展与下一步：\n\n"+facts+"\n\n待核对：请确认各事项的负责人、时间与实际进度。";
        if("客户简报".equals(purpose))return "会议简报（草稿）\n\n"+facts+"\n\n以上内容需结合原话核对；未明确的事项不作为承诺。";
        return facts;
    }
    JSONObject save(JSONObject args,AiMaterialStore store,Current current) throws Exception {
        Job job=jobs.get(args.getString("jobId"));if(job==null||job.result==null)throw new IOException("本次查询已离开，请重新提问或保留当前文字。");current.require(job.docs,job.token);
        if(!job.owner.equals(args.getString("ownerKey")))throw new IOException("当前会议已变化，未保存到其他会议。");
        if(job.result.getJSONArray("items").length()==0)throw new IOException("当前没有有据可查的结果可保存。");
        String generated=draftBody(job.result.getJSONArray("items"),job.purpose);
        JSONArray sources=new JSONArray();for(int i=0;i<job.docs.length();i++){JSONObject d=new JSONObject(job.docs.getJSONObject(i).toString());d.remove("text");sources.put(d);}
        return store.save(args.getString("id"),job.owner,args.getString("title"),job.question,args.getString("body"),sources,job.result,!generated.equals(args.getString("body")));
    }
}
