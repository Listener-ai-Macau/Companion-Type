package com.denzic.companion.app;

import com.denzic.companion.mobile.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** Generated sample values only. No recorded speech, model or audio device. */
public final class DerivedAudioPublicationTest {
 interface Attempt {void run()throws Exception;}
 static void check(boolean ok,String why){if(!ok)throw new AssertionError(why);}
 static void refuses(Attempt work)throws Exception {try{work.run();throw new AssertionError("Invalid operation accepted");}catch(IOException expected){}}
 static String key(String seed)throws Exception{return ImportedAudio.hash(seed.getBytes("UTF-8"))+":1:1";}
 static byte[] wav(int start,int count){ByteBuffer b=ByteBuffer.allocate(44+count*2).order(ByteOrder.LITTLE_ENDIAN);b.put(new byte[]{'R','I','F','F'}).putInt(36+count*2).put(new byte[]{'W','A','V','E','f','m','t',' '}).putInt(16).putShort((short)1).putShort((short)1).putInt(16000).putInt(32000).putShort((short)2).putShort((short)16).put(new byte[]{'d','a','t','a'}).putInt(count*2);for(int i=0;i<count;i++)b.putShort((short)(start+i));return b.array();}
 static JSONObject slice(AudioDerivationPlan.Source s,long a,long b,long out)throws Exception{return new JSONObject().put("sourceKey",s.key).put("sourceIdentity",s.identity).put("startFrame",a).put("endFrame",b).put("outputStartFrame",out).put("outputEndFrame",out+b-a);}
 static JSONObject plan(JSONArray rows,long frames)throws Exception{return new JSONObject().put("schema",1).put("sampleRate",16000).put("frames",frames).put("slices",rows);}
 static ImportedAudio source(Path root,Path rec,String seed,int first,int frames)throws Exception {
  Path stage=Files.createDirectory(root.resolve("source-"+seed));byte[] all=wav(first,frames);Files.write(stage.resolve("original.audio"),all);int half=frames/2;Files.write(ImportedAudio.part(stage,0),wav(first,half));Files.write(ImportedAudio.part(stage,1),wav(first+half,frames-half));return ImportedAudio.publish(stage,rec,key(seed),"公开生成PCM "+seed,"audio/wav",all.length,ImportedAudio.hash(all),Arrays.asList((long)half,(long)(frames-half)),p->{});
 }
 static CanonicalPcmRenderer.Input input(ImportedAudio audio,AudioDerivationPlan.Source identity)throws Exception {List<Path> parts=new ArrayList<>();List<String> hashes=new ArrayList<>();for(int i=0;i<audio.partCount();i++){Path p=ImportedAudio.part(audio.directory,i);parts.add(p);hashes.add(ImportedAudio.fileHash(p));}return new CanonicalPcmRenderer.Input(identity.key,identity.identity,parts,hashes);}
 public static void main(String[] args)throws Exception {
  Path root=Paths.get(args[0]);Files.createDirectory(root);Path rec=Files.createDirectory(root.resolve("recordings")),meet=Files.createDirectory(root.resolve("meetings"));
  ImportedAudio a=source(root,rec,"A",100,16),b=source(root,rec,"B",200,17);byte[] oldA=Files.readAllBytes(a.original),oldB=Files.readAllBytes(b.original),oldMeta=Files.readAllBytes(a.directory.resolve("import.json"));
  AudioDerivationPlan.Source sa=new AudioDerivationPlan.Source(a.key,ImportedAudio.hash(a.fingerprint()),16),sb=new AudioDerivationPlan.Source(b.key,ImportedAudio.hash(b.fingerprint()),17);List<AudioDerivationPlan.Source> sources=Arrays.asList(sa,sb);
  JSONObject raw=plan(new JSONArray().put(slice(sa,4,10,0)).put(slice(sb,2,6,6)).put(slice(sa,0,3,10)),13);AudioDerivationPlan map=AudioDerivationPlan.validate(raw,sources);
  JSONObject damaged=new JSONObject(raw.toString());damaged.getJSONArray("slices").getJSONObject(1).put("outputStartFrame",7);refuses(()->AudioDerivationPlan.validate(damaged,sources));
  JSONObject fractional=new JSONObject(raw.toString());fractional.getJSONArray("slices").getJSONObject(0).put("startFrame",4.5);refuses(()->AudioDerivationPlan.validate(fractional,sources));
  JSONObject typed=new JSONObject(raw.toString());typed.put("frames","13");refuses(()->AudioDerivationPlan.validate(typed,sources));
  JSONObject stale=new JSONObject(raw.toString());stale.getJSONArray("slices").getJSONObject(0).put("sourceIdentity",ImportedAudio.hash("stale".getBytes("UTF-8")));refuses(()->AudioDerivationPlan.validate(stale,sources));
  check(AudioDerivationPlan.readProvenance(map.provenance()).slices.get(1).source.key.equals(b.key),"Persisted multi-meeting identity lost");
  Map<String,CanonicalPcmRenderer.Input> inputs=new HashMap<>();inputs.put(a.key,input(a,sa));inputs.put(b.key,input(b,sb));String derivedKey=key("derived");Path stage=Files.createDirectory(root.resolve("private-stage"));
  DerivedAudioPublication.Prepared prepared=DerivedAudioPublication.prepare(stage,derivedKey,"公开片段合并",map,inputs,(done,total)->{},p->{});
  check(RecordingLibrary.inspect(rec).sessions.size()==2,"Private preparation leaked into the recording library");
  refuses(()->DerivedAudioPublication.publish(prepared,rec,()->{throw new IOException("library changed");},p->{}));check(Files.exists(prepared.directory),"Stale library failure destroyed retryable preparation");check(!Files.exists(rec.resolve(ImportedAudio.folder(derivedKey))),"Failed library guard published audio");
  ImportedAudio saved=DerivedAudioPublication.publish(prepared,rec,()->{},p->{});check(saved.samples==13&&saved.partCount()==1,"Published derived audio length wrong");
  short[] expected={104,105,106,107,108,109,202,203,204,205,100,101,102};ByteBuffer audio=ByteBuffer.wrap(Files.readAllBytes(saved.original)).order(ByteOrder.LITTLE_ENDIAN);for(int i=0;i<expected.length;i++)check(audio.getShort(44+i*2)==expected[i],"Sample reorder/multipart boundary wrong at "+i);
  AudioDerivationPlan reopened=DerivedAudioPublication.read(ImportedAudio.read(saved.directory));check(reopened.slices.size()==3&&reopened.slices.get(2).outputStart==10&&reopened.slices.get(2).start==0,"Reopen changed source offsets");check(DerivedAudioPublication.read(a)==null,"Ordinary import falsely described as edited");
  String prefix=LocalRecordingLifecycle.hash(derivedKey);try(DirectoryStream<Path> files=Files.newDirectoryStream(meet,prefix+".*")){check(!files.iterator().hasNext(),"Original transcript/notes were copied to derived recording");}
  ByteArrayOutputStream zip=new ByteArrayOutputStream();LibraryBackup.write(zip,rec,meet,null);Path restored=root.resolve("restored");LibraryBackup.restore(new ByteArrayInputStream(zip.toByteArray()),restored);ImportedAudio copy=ImportedAudio.read(restored.resolve("recordings").resolve(ImportedAudio.folder(derivedKey)));copy.verifiedParts();check(Arrays.equals(Files.readAllBytes(copy.directory.resolve("import.json")),Files.readAllBytes(saved.directory.resolve("import.json"))),"Backup changed atomic source provenance");check(DerivedAudioPublication.read(copy).slices.get(1).source.key.equals(b.key),"Restore lost another-meeting source");
  // A duplicate publication is refused without retiring either independent copy.
  Path retryStage=Files.createDirectory(root.resolve("retry-stage"));DerivedAudioPublication.Prepared retry=DerivedAudioPublication.prepare(retryStage,derivedKey,"重复身份",map,inputs,(d,t)->{},p->{});refuses(()->DerivedAudioPublication.publish(retry,rec,()->{},p->{}));check(Files.exists(retry.directory)&&Files.exists(saved.original),"Collision overwrote or removed a recording");
  Path cancelled=Files.createDirectory(root.resolve("cancelled-stage"));refuses(()->DerivedAudioPublication.prepare(cancelled,key("cancelled"),"取消",map,inputs,(done,total)->{if(done>0)throw new IOException("cancelled");},p->{}));check(!Files.exists(rec.resolve(ImportedAudio.folder(key("cancelled")))),"Cancelled preparation appeared in library");
  Path syncStage=Files.createDirectory(root.resolve("sync-stage"));DerivedAudioPublication.Prepared uncertain=DerivedAudioPublication.prepare(syncStage,key("sync-uncertain"),"目录同步未知",map,inputs,(d,t)->{},p->{});refuses(()->DerivedAudioPublication.publish(uncertain,rec,()->{},p->{throw new IOException("injected post-rename fsync failure");}));ImportedAudio recovered=ImportedAudio.read(rec.resolve(ImportedAudio.folder(uncertain.key)));recovered.verifiedParts();check(DerivedAudioPublication.read(recovered).frames==13,"Uncertain post-rename result was lost instead of recoverable");
  // Exercise the real library resolver, rather than trusting frontend identities.
  final String[] token={"library-a"};final Set<String> hidden=new HashSet<>();AudioDerivationAccess access=new AudioDerivationAccess(root,rec,root.resolve("decoded-cache"),new AudioDerivationAccess.Library(){
   public String token(){return token[0];}
   public RecordingLibrary.Session visible(String key)throws Exception {if(hidden.contains(key))throw new IOException("trashed");List<RecordingLibrary.Session> found=RecordingLibrary.inspectSession(rec,key).sessions;if(found.size()!=1)throw new IOException("source unavailable");return found.get(0);}
  });
  List<AudioDerivationAccess.Resolved> resolved=access.resolve("library-a",Arrays.asList(a.key,b.key),(d,t)->{});check(resolved.get(0).source.frames==16&&resolved.get(1).source.frames==17,"Native resolver changed source lengths");check(!access.describe("library-a",resolved).toString().contains(root.toString()),"Public source descriptor exposed private paths");check(resolved.get(0).source.identity.equals(access.resolve("library-a",Arrays.asList(a.key),(d,t)->{}).get(0).source.identity),"Unchanged source identity was unstable");
  token[0]="library-b";refuses(()->access.revalidate("library-a",resolved));token[0]="library-a";hidden.add(b.key);refuses(()->access.revalidate("library-a",resolved));hidden.clear();refuses(()->access.resolve("library-a",Arrays.asList(a.key,a.key),(d,t)->{}));
  ImportedAudio corrupt=source(root,rec,"intentional-corrupt-copy",300,15);List<AudioDerivationAccess.Resolved> corruptSnapshot=access.resolve("library-a",Arrays.asList(corrupt.key),(d,t)->{});Path mutated=ImportedAudio.part(corrupt.directory,0);byte[] known=Files.readAllBytes(mutated),changed=known.clone();changed[44]^=1;Files.write(mutated,changed);refuses(()->access.revalidate("library-a",corruptSnapshot));Files.write(mutated,known);corrupt.verifiedParts();
  LocalRecordingLifecycle life=new LocalRecordingLifecycle(root,rec,meet,p->{});life.change(derivedKey,0,"trash","公开合并");JSONObject offer=life.preparePurge(derivedKey,1);life.purge(derivedKey,1,offer.getString("token"));check(!Files.exists(saved.directory),"Exact purge left derived original or provenance behind");check(Arrays.equals(Files.readAllBytes(a.original),oldA)&&Arrays.equals(Files.readAllBytes(b.original),oldB)&&Arrays.equals(Files.readAllBytes(a.directory.resolve("import.json")),oldMeta),"Derivation or purge changed an original");check(Files.exists(copy.original),"Purging source library affected its independent restored copy");
  System.out.println("PASS actual generated PCM: native map validation, multipart/reorder samples, atomic audio+provenance, stale guard/retry/collision/cancel, uncertain directory sync recovery, real backup/restore and exact derived-only purge; original sources unchanged. No app UI, phone or model qualified.");
 }
}
