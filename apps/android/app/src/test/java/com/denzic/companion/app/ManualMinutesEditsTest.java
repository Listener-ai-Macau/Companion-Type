package com.denzic.companion.app;
import com.denzic.companion.mobile.MeetingStore;
import org.json.JSONObject;
import java.nio.file.*;
import java.util.*;

public final class ManualMinutesEditsTest {
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 public static void main(String[]args)throws Exception{
  Path root=Files.createTempDirectory(Paths.get(args[0]),"manual-json-");MeetingStore store=new MeetingStore(root);
  MeetingStore.Snapshot m=store.save("meeting",0,"周五核对报价。","我的补充",Collections.emptyList());
  String original=new JSONObject().put("markdown","## Action Items\n- 待核对：核对报价\n\n## 原文依据\n- 周五核对报价。").put("quality","draft").put("processing",new JSONObject().put("complete",false)).put("evidence",new JSONObject().put("quote","周五核对报价。")).toString();
  MeetingStore.Minutes old=store.saveMinutes("meeting",m.revision,0,m.transcript,original);
  String changed="## Action Items\n- [ ] 核对报价 (owner: 小王, due: 周五18:00)\n\n## 原文依据\n- 周五核对报价。";
  String json=ManualMinutesEdits.apply(old.json,changed,"[\"Action Items\",0,0]",false,m.revision);
  MeetingStore.Minutes saved=store.saveEditedMinutes("meeting",m.revision,old.revision,old.json,json,false);
  JSONObject result=new JSONObject(saved.json);
  check(result.getString("markdown").equals(ManualMinutesEdits.NOTICE+changed),"manual notice or original quotes lost");
  check(result.getString("quality").equals("draft")&&!result.getJSONObject("processing").getBoolean("complete"),"manual edit made an incomplete draft look complete");
  check(result.getJSONObject("evidence").getString("quote").equals("周五核对报价。"),"evidence altered");
  check(result.getJSONObject("manualReview").getJSONArray("actions").length()==1,"manual action identity missing");
  String twice=ManualMinutesEdits.apply(saved.json,result.getString("markdown"),"[\"Action Items\",0,0]",false,m.revision);
  check(new JSONObject(twice).getString("markdown").equals(result.getString("markdown")),"manual notice duplicated");
  check(new JSONObject(twice).getJSONObject("manualReview").getJSONArray("actions").length()==1,"action provenance duplicated");
  MeetingStore.Snapshot corrected=store.saveTranscriptCorrection("meeting",m.revision,"改成下周核对报价。");
  String staleEdit=ManualMinutesEdits.apply(saved.json,new JSONObject(twice).getString("markdown"),null,false,corrected.revision);
  MeetingStore.Minutes stale=store.saveEditedMinutes("meeting",corrected.revision,saved.revision,saved.json,staleEdit,false);
  check(stale.sourceChanged,"plain edit cleared stale source");
  String reviewed=ManualMinutesEdits.apply(stale.json,new JSONObject(stale.json).getString("markdown"),null,true,corrected.revision);
  MeetingStore.Minutes current=store.saveEditedMinutes("meeting",corrected.revision,stale.revision,stale.json,reviewed,true);
  check(!current.sourceChanged&&new JSONObject(current.json).getJSONObject("manualReview").getBoolean("sourceReviewed"),"explicit human review not saved");
  check(store.listMinutesHistory("meeting").versions.size()==3,"prior AI/manual versions missing");
  check(store.load("meeting").transcript.equals(corrected.transcript),"source was rewritten");
  System.out.println("PASS real JSON/store manual edits, one provenance notice, retained evidence/draft/history and explicit current-source review");
 }
}
