package com.denzic.companion.app;

import org.json.JSONArray;
import org.json.JSONObject;

/** App-side provenance only. The durable store owns revisions, source hashes and history. */
final class ManualMinutesEdits {
    static final String NOTICE="> 人工修订：此版本包含使用者的核对或修改，不代表重新生成的 AI 结果；新增负责人和时间请按实际安排确认。\n\n";
    static String apply(String previousJson,String markdown,String actionId,boolean sourceReviewed,long meetingRevision)throws Exception {
        if(markdown==null||markdown.trim().isEmpty()||markdown.length()>200000)throw new IllegalArgumentException("纪要内容为空或过长，请保留输入并检查。");
        if(actionId!=null&&actionId.length()>500)throw new IllegalArgumentException("事项标识过长。");
        JSONObject result=new JSONObject(previousJson),prior=result.optJSONObject("manualReview");
        if(prior!=null&&prior.optInt("version")==1&&markdown.startsWith(NOTICE))markdown=markdown.substring(NOTICE.length());
        JSONObject manual=prior==null?new JSONObject():new JSONObject(prior.toString());
        JSONArray ids=manual.optJSONArray("actions");if(ids==null)ids=new JSONArray();
        if(actionId!=null&&!actionId.isEmpty()){
            boolean found=false;for(int i=0;i<ids.length();i++)if(actionId.equals(ids.optString(i)))found=true;
            if(!found)ids.put(actionId);
        }
        manual.put("version",1).put("actions",ids).put("updatedAt",java.time.Instant.now().toString());
        if(sourceReviewed)manual.put("sourceReviewed",true).put("reviewedSourceRevision",meetingRevision);
        result.put("manualReview",manual).put("markdown",NOTICE+markdown);
        return result.toString();
    }
    private ManualMinutesEdits(){}
}
