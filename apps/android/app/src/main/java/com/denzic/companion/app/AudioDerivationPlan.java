package com.denzic.companion.app;

import java.io.IOException;
import java.util.*;
import org.json.*;

/** Native validation of packages/audio-derivation's sample map. Source snapshots
 * are resolved from the current private library, never accepted as file paths.
 */
final class AudioDerivationPlan {
 static final long SAFE=9007199254740991L;
 static final class Source {
  final String key,identity;final long frames;
  Source(String key,String identity,long frames)throws IOException {
   if(key==null||!key.matches("[0-9a-f]{16,64}:[0-9a-f]{1,16}:[0-9a-f]{1,16}")||identity==null||!identity.matches("[0-9a-f]{64}")||frames<=0||frames>SAFE)throw invalid("原音身份或完整长度尚未确认，请重新读取。");
   this.key=key;this.identity=identity;this.frames=frames;
  }
 }
 static final class Slice {
  final Source source;final long start,end,outputStart,outputEnd;
  Slice(Source source,long start,long end,long outputStart,long outputEnd){this.source=source;this.start=start;this.end=end;this.outputStart=outputStart;this.outputEnd=outputEnd;}
 }
 final List<Source> sources;final List<Slice> slices;final long frames;
 private AudioDerivationPlan(List<Source> sources,List<Slice> slices,long frames){this.sources=Collections.unmodifiableList(sources);this.slices=Collections.unmodifiableList(slices);this.frames=frames;}
 private static IOException invalid(String text){return new IOException(text);}
 private static long integer(JSONObject value,String field)throws JSONException,IOException {
  Object raw=value.get(field);if(!(raw instanceof Number))throw invalid("音频编辑位置必须是完整采样数。");
  Number number=(Number)raw;long result=number.longValue();double exact=number.doubleValue();
  if(!Double.isFinite(exact)||result<0||result>SAFE||exact!=(double)result)throw invalid("音频编辑位置无效，请重新选择。");return result;
 }
 static AudioDerivationPlan validate(JSONObject plan,List<Source> verified)throws IOException {
  try{
   if(plan==null||verified==null||verified.isEmpty()||verified.size()>128||integer(plan,"schema")!=1||integer(plan,"sampleRate")!=16000)throw invalid("派生音频来源版本无效。");
   Map<String,Source> known=new LinkedHashMap<>();for(Source source:verified)if(source==null||known.put(source.key,source)!=null)throw invalid("原音身份重复，请重新读取。");
   JSONArray rows=plan.getJSONArray("slices");if(rows.length()==0||rows.length()>512)throw invalid("请选择有效的音频片段。");
   List<Slice> slices=new ArrayList<>();Set<String> used=new HashSet<>();long output=0;
   for(int i=0;i<rows.length();i++){
    JSONObject row=rows.getJSONObject(i);Source source=known.get(row.getString("sourceKey"));
    if(source==null||!source.identity.equals(row.getString("sourceIdentity")))throw invalid("原音已变化，请重新选择编辑范围。");
    long start=integer(row,"startFrame"),end=integer(row,"endFrame");if(end<=start||end>source.frames||output>SAFE-(end-start))throw invalid("编辑区间超出原音或处理范围。");
    long next=output+end-start;if(integer(row,"outputStartFrame")!=output||integer(row,"outputEndFrame")!=next)throw invalid("派生音频时间对应已损坏，请重新生成。");
    slices.add(new Slice(source,start,end,output,next));used.add(source.key);output=next;
   }
   if(integer(plan,"frames")!=output)throw invalid("派生音频长度与来源不符。");
   List<Source> sources=new ArrayList<>();for(Source source:verified)if(used.contains(source.key))sources.add(source);
   return new AudioDerivationPlan(sources,slices,output);
  }catch(JSONException|ClassCastException e){throw new IOException("派生音频来源无法完整读取。",e);}
 }
 JSONObject map()throws JSONException {
  JSONArray rows=new JSONArray();for(Slice s:slices)rows.put(new JSONObject().put("sourceKey",s.source.key).put("sourceIdentity",s.source.identity).put("startFrame",s.start).put("endFrame",s.end).put("outputStartFrame",s.outputStart).put("outputEndFrame",s.outputEnd));
  return new JSONObject().put("schema",1).put("sampleRate",16000).put("frames",frames).put("slices",rows);
 }
 JSONObject provenance()throws JSONException {
  JSONArray rows=new JSONArray();for(Source s:sources)rows.put(new JSONObject().put("key",s.key).put("identity",s.identity).put("frames",s.frames).put("sampleRate",16000));
  return new JSONObject().put("schema",1).put("sources",rows).put("plan",map());
 }
 static AudioDerivationPlan readProvenance(JSONObject value)throws IOException {
  try{
   if(integer(value,"schema")!=1)throw invalid("派生音频来源版本无效。");JSONArray rows=value.getJSONArray("sources");if(rows.length()>128)throw invalid("派生音频来源过多。");List<Source> sources=new ArrayList<>();
   for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);if(integer(row,"sampleRate")!=16000)throw invalid("派生音频采样时间轴无效。");sources.add(new Source(row.getString("key"),row.getString("identity"),integer(row,"frames")));}
   return validate(value.getJSONObject("plan"),sources);
  }catch(JSONException e){throw new IOException("派生音频来源无法完整读取。",e);}
 }
 List<CanonicalPcmRenderer.Clip> clips(Map<String,CanonicalPcmRenderer.Input> inputs)throws IOException {
  List<CanonicalPcmRenderer.Clip> result=new ArrayList<>();for(Slice slice:slices){CanonicalPcmRenderer.Input input=inputs.get(slice.source.key);if(input==null||!slice.source.identity.equals(input.identity)||!slice.source.key.equals(input.key))throw invalid("原音已变化，请重新准备编辑。");result.add(new CanonicalPcmRenderer.Clip(input,slice.start,slice.end));}return result;
 }
}
