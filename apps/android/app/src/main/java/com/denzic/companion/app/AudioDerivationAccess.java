package com.denzic.companion.app;

import com.denzic.companion.mobile.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** Resolve only explicit visible, complete local recordings. A caller keeps its
 * existing library/lifecycle exclusion for the operation; no public filename,
 * partial device recording or arbitrary cache file can become an edit source.
 */
final class AudioDerivationAccess {
 interface Library {
  String token()throws Exception;
  RecordingLibrary.Session visible(String key)throws Exception;
 }
 static final class Resolved {
  final AudioDerivationPlan.Source source;final CanonicalPcmRenderer.Input input;
  final String recordingBinding;
  Resolved(AudioDerivationPlan.Source source,CanonicalPcmRenderer.Input input,String binding){this.source=source;this.input=input;recordingBinding=binding;}
  JSONObject dto()throws JSONException{return new JSONObject().put("key",source.key).put("identity",source.identity).put("frames",source.frames).put("sampleRate",16000);}
 }
 final Path root,recordings,cache;final Library library;
 AudioDerivationAccess(Path root,Path recordings,Path cache,Library library){this.root=root.toAbsolutePath().normalize();this.recordings=recordings.toAbsolutePath().normalize();this.cache=cache.toAbsolutePath().normalize();this.library=library;}
 private static IOException invalid(String text){return new IOException(text);}
 private void localPart(Path p)throws IOException {
  p=p.toAbsolutePath().normalize();if((!p.startsWith(recordings)&&!p.startsWith(cache))||!p.startsWith(root)||p.equals(root))throw invalid("原音不属于当前本机资料库。");
  for(Path part=p;part!=null&&part.startsWith(root);part=part.getParent())if(Files.isSymbolicLink(part))throw invalid("原音路径含链接，请先检查；原件已保留。");
  if(!Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS))throw invalid("原音分片尚不可用，请先完成接收。");
 }
 private RecordingLibrary.Session selected(String key)throws Exception {
  RecordingLibrary.Session session=library.visible(key);if(session==null||!session.key().equals(key)||session.state!=RecordingLibrary.SessionState.COMPLETE)throw invalid("只可编辑已完整保存在本机的录音，请先完成接收或修复。");return session;
 }
 List<Resolved> resolve(String expectedToken,List<String> keys,CanonicalPcmRenderer.Control control)throws Exception {
  if(expectedToken==null||!expectedToken.equals(library.token()))throw invalid("资料库已变化，请重新打开录音编辑。");
  if(keys==null||keys.isEmpty()||keys.size()>128||control==null)throw invalid("请选择有效的本机录音。");
  Set<String> seen=new HashSet<>();List<Resolved> resolved=new ArrayList<>();
  for(String key:keys){
   if(key==null||!seen.add(key))throw invalid("录音来源重复，请重新选择。");control.checkpoint(0,0);RecordingLibrary.Session session=selected(key);String binding=RecordingBookmarkAccess.binding(session);
   NativeAudio.PartsResult parts=ManagedAudioParts.prepare(session,cache);if(!parts.captureComplete||parts.samples<=0||parts.parts.isEmpty()||parts.parts.size()>4096)throw invalid("当前音频尚未完整准备，请完成接收后再编辑。");
   List<Path> paths=new ArrayList<>();List<String> hashes=new ArrayList<>();StringBuilder verified=new StringBuilder("Companion canonical edit source v1\n").append(key).append('\n').append(binding).append("\n16000\n").append(parts.samples).append('\n');long frames=0;
   for(NativeAudio.Part part:parts.parts){
    control.checkpoint(frames,parts.samples);if(part.firstSample!=frames||part.samples<=0||frames>AudioDerivationPlan.SAFE-part.samples)throw invalid("本机回听音频时间轴不完整，请重新准备。");localPart(part.path);
    String hash=ImportedAudio.fileHash(part.path);paths.add(part.path);hashes.add(hash);verified.append(hash).append(':').append(part.samples).append('\n');frames+=part.samples;
   }
   if(frames!=parts.samples||!binding.equals(RecordingBookmarkAccess.binding(selected(key))))throw invalid("原音在准备期间发生变化，请重新打开编辑。");
   String identity=ImportedAudio.hash(verified.toString().getBytes(StandardCharsets.UTF_8));
   AudioDerivationPlan.Source source=new AudioDerivationPlan.Source(key,identity,frames);resolved.add(new Resolved(source,new CanonicalPcmRenderer.Input(key,identity,paths,hashes),binding));
  }
  revalidate(expectedToken,resolved);return resolved;
 }
 /** Recheck metadata and every exact canonical input immediately before commit.
  * Normal application mutation is excluded by the caller's existing library
  * guard; this also refuses unexpectedly changed files without changing them.
  */
 void revalidate(String expectedToken,List<Resolved> sources)throws Exception {
  if(!expectedToken.equals(library.token()))throw invalid("资料库已变化，本次未提交新的录音。");
  for(Resolved source:sources){
   if(!source.recordingBinding.equals(RecordingBookmarkAccess.binding(selected(source.source.key))))throw invalid("原音身份已变化，本次未提交派生录音。");
   for(int i=0;i<source.input.parts.size();i++){Path p=source.input.parts.get(i);localPart(p);if(!ImportedAudio.fileHash(p).equals(source.input.hashes.get(i)))throw invalid("原音在编辑期间发生变化，派生录音尚未保存。");}
  }
 }
 JSONObject describe(String token,List<Resolved> sources)throws JSONException {JSONArray rows=new JSONArray();for(Resolved source:sources)rows.put(source.dto());return new JSONObject().put("libraryToken",token).put("sources",rows).put("sampleRate",16000);}
}
