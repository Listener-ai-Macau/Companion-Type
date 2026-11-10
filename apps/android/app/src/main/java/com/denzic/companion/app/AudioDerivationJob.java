package com.denzic.companion.app;

import com.denzic.companion.mobile.ImportedAudio;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** One durable background operation may save a trim, a merge or multiple split
 * pieces. Each independent recording publishes atomically. A partial operation
 * retains completed pieces; retries inspect only its preassigned pending keys.
 */
final class AudioDerivationJob {
 interface Listener {void persist(JSONObject record,boolean committing)throws Exception;}
 private static IOException invalid(String text){return new IOException(text);}
 static JSONObject create(JSONObject request)throws Exception {
  if(request==null||request.toString().getBytes(StandardCharsets.UTF_8).length>256*1024)throw invalid("本次编辑资料过长，请减少片段后分批保存。");
  String token=request.getString("libraryToken");JSONArray input=request.getJSONArray("outputs"),outputs=new JSONArray();if(token.isEmpty()||input.length()==0||input.length()>32)throw invalid("一次最多保存32份片段，请分批整理。");
  for(int i=0;i<input.length();i++){
   JSONObject row=input.getJSONObject(i);String name=row.getString("name").trim();if(name.isEmpty()||name.length()>256||name.matches("(?s).*[\\p{Cntrl}].*"))throw invalid("请为每份片段填写有效名称。");
   JSONObject plan=row.getJSONObject("plan");JSONArray slices=plan.getJSONArray("slices");if(slices.length()==0||slices.length()>512)throw invalid("请选择有效的音频片段。");
   outputs.put(new JSONObject().put("key",ImportedAudio.hash(UUID.randomUUID().toString().getBytes(StandardCharsets.UTF_8))+":1:1").put("name",name).put("plan",new JSONObject(plan.toString())).put("state","pending"));
  }
  return new JSONObject().put("id",UUID.randomUUID().toString()).put("operation","derive").put("running",true).put("state","starting").put("message","正在准备录音编辑").put("request",new JSONObject().put("libraryToken",token).put("outputs",outputs));
 }
 static JSONObject publicDetails(JSONObject record)throws Exception {
  JSONObject result=new JSONObject(record.toString());JSONObject request=result.optJSONObject("request");result.remove("request");
  if(request!=null){JSONArray source=request.getJSONArray("outputs"),outputs=new JSONArray();int completed=0;for(int i=0;i<source.length();i++){JSONObject row=source.getJSONObject(i);boolean saved="complete".equals(row.getString("state"));if(saved)completed++;outputs.put(new JSONObject().put("key",row.getString("key")).put("name",row.getString("name")).put("saved",saved));}result.put("outputs",outputs).put("completed",completed).put("totalOutputs",outputs.length()).put("retryAvailable",completed<outputs.length()&&!record.optBoolean("running"));}
  return result;
 }
 /** Recover only exact new keys already declared by this job. No source is read
  * and no output is recreated; sources may have been explicitly deleted later.
  */
 static int recover(JSONObject record,Path recordings,ImportedAudio.DirectorySync sync)throws Exception {
  JSONArray outputs=record.getJSONObject("request").getJSONArray("outputs");int complete=0;
  for(int i=0;i<outputs.length();i++){
   JSONObject row=outputs.getJSONObject(i);if("complete".equals(row.getString("state"))){complete++;continue;}
   String key=row.getString("key");Path destination=recordings.resolve(ImportedAudio.folder(key));if(!Files.exists(destination,LinkOption.NOFOLLOW_LINKS))continue;
   ImportedAudio saved=ImportedAudio.read(destination);saved.verifiedParts();AudioDerivationPlan provenance=DerivedAudioPublication.read(saved);if(provenance==null)throw invalid("待核对的片段来源不符，已保留现有文件。");
   AudioDerivationPlan expected=AudioDerivationPlan.validate(row.getJSONObject("plan"),provenance.sources);
   // Validating against persisted source snapshots also checks every source
   // identity, range, output offset and total against the original request.
   if(!expected.map().toString().equals(provenance.map().toString()))throw invalid("待核对的片段与本次编辑不符，已保留原件。");
   sync.sync(recordings);row.put("state","complete");complete++;
  }return complete;
 }
 static void run(JSONObject record,Path stage,Path recordings,AudioDerivationAccess access,CanonicalPcmRenderer.Control control,ImportedAudio.DirectorySync sync,Listener listener)throws Exception {
  JSONObject request=record.getJSONObject("request");JSONArray outputs=request.getJSONArray("outputs");String token=request.getString("libraryToken");
  if(!token.equals(access.library.token()))throw invalid("资料库已切换，本次没有保存新的片段。");
  recover(record,recordings,sync);listener.persist(record,false);
  LinkedHashSet<String> keys=new LinkedHashSet<>();for(int i=0;i<outputs.length();i++){JSONObject row=outputs.getJSONObject(i);if("complete".equals(row.getString("state")))continue;JSONArray clips=row.getJSONObject("plan").getJSONArray("slices");for(int j=0;j<clips.length();j++)keys.add(clips.getJSONObject(j).getString("sourceKey"));}
  if(keys.isEmpty())return;
  record.put("state","preparing").put("message","正在核对完整本机原音");listener.persist(record,false);
  List<AudioDerivationAccess.Resolved> resolved=access.resolve(token,new ArrayList<>(keys),control);List<AudioDerivationPlan.Source> sources=new ArrayList<>();Map<String,CanonicalPcmRenderer.Input> inputs=new HashMap<>();for(AudioDerivationAccess.Resolved source:resolved){sources.add(source.source);inputs.put(source.source.key,source.input);}
  // Validate all pending pieces before publishing the first one. A stale range
  // in the final split must not silently produce only its earlier pieces.
  Map<Integer,AudioDerivationPlan> plans=new LinkedHashMap<>();for(int i=0;i<outputs.length();i++)if(!"complete".equals(outputs.getJSONObject(i).getString("state")))plans.put(i,AudioDerivationPlan.validate(outputs.getJSONObject(i).getJSONObject("plan"),sources));
  for(Map.Entry<Integer,AudioDerivationPlan> entry:plans.entrySet()){
   int index=entry.getKey();JSONObject row=outputs.getJSONObject(index);control.checkpoint(0,entry.getValue().frames);record.put("state","processing").put("message","正在生成片段 "+(index+1)+" / "+outputs.length());listener.persist(record,false);
   Path work=Files.createDirectory(stage.resolve("piece-"+index));DerivedAudioPublication.Prepared prepared=DerivedAudioPublication.prepare(work,row.getString("key"),row.getString("name"),entry.getValue(),inputs,control,sync);
   control.checkpoint(entry.getValue().frames,entry.getValue().frames);record.put("state","committing").put("message","正在完成片段保存");listener.persist(record,true);
   DerivedAudioPublication.publish(prepared,recordings,()->{try{access.revalidate(token,resolved);}catch(IOException e){throw e;}catch(Exception e){throw new IOException("资料状态无法核对，派生片段尚未保存。",e);}},sync);
   row.put("state","complete");record.put("state","processing").put("message","片段已保存在本机");listener.persist(record,false);
  }
 }
 private AudioDerivationJob(){}
}
