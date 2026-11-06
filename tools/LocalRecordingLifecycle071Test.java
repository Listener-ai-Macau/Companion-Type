package com.denzic.companion.app;

import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import com.denzic.companion.mobile.LibraryBackup;

/** Synthetic app-private fixtures only; no phone, device, model, clipboard or network. */
public final class LocalRecordingLifecycle071Test {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    interface Attempt{void run()throws Exception;}
    static void refused(Attempt a,String message)throws Exception{try{a.run();throw new AssertionError(message);}catch(IOException|JSONException expected){}}
    static final String A="0102030405060708090a0b0c:1:2",B="1102030405060708090a0b0c:1:2";
    static List<Path> fixture(Path recordings,Path meetings,String key)throws Exception{
        String prefix=key.replace(':','-')+"-0-123-"+String.join("",Collections.nCopies(64,"a"));String hash=LocalRecordingLifecycle.hash(key);
        List<Path> files=new ArrayList<>(Arrays.asList(recordings.resolve(prefix+".cop1"),recordings.resolve(prefix+".meta"),meetings.resolve(hash+".meeting"),meetings.resolve(hash+".minutes-history-1.bin"),meetings.resolve(hash+".title"),meetings.resolve("translations").resolve(hash+".translation")));
        for(Path p:files){Files.createDirectories(p.getParent());Files.write(p,("公开虚构资料 "+key+" "+p.getFileName()).getBytes("UTF-8"));}
        Path material=meetings.resolve("ai-materials").resolve(LocalRecordingLifecycle.hash(key).substring(0,8)+"-1111-2222-3333-444444444444.json");Files.createDirectories(material.getParent());
        Files.write(material,new JSONObject().put("ownerKey",key).put("body","公开虚构AI材料").toString().getBytes("UTF-8"));files.add(material);return files;
    }
    static LocalRecordingLifecycle lifecycle(Path r,Path m){return new LocalRecordingLifecycle(r.getParent(),r,m,path->{});}
    public static void main(String[] args)throws Exception{
        Path base=Files.createTempDirectory(Paths.get(args[0]),"trash071-"),r=Files.createDirectory(base.resolve("recordings")),m=Files.createDirectory(base.resolve("meetings"));
        List<Path> a=fixture(r,m,A),b=fixture(r,m,B);Map<Path,byte[]> original=new HashMap<>();for(Path p:a)original.put(p,Files.readAllBytes(p));for(Path p:b)original.put(p,Files.readAllBytes(p));
        LocalRecordingLifecycle life=lifecycle(r,m);check(life.get(A).getLong("revision")==0,"new state");
        LocalRecordingLifecycle initial=life;
        life.change(A,0,"protect","");refused(()->initial.change(A,0,"trash","会议A"),"stale revision accepted");refused(()->initial.change(A,1,"trash","会议A"),"protected recording trashed");
        life.change(A,1,"unprotect","");life.change(A,2,"trash","会议A");refused(()->initial.requireVisible(A),"trash remained directly readable");
        life=lifecycle(r,m);check(life.trash().getJSONArray("rows").length()==1,"trash did not survive reopen");
        life.change(A,3,"restore","");life.requireVisible(A);for(Path p:original.keySet())check(Arrays.equals(original.get(p),Files.readAllBytes(p)),"restore changed originals");
        System.out.println("PASS protection, stale revision, soft delete, direct-access refusal, reopen/restore and original bytes");

        life.change(A,4,"trash","会议A");JSONObject plan=life.preparePurge(A,5);String token=plan.getString("token");
        Files.write(a.get(2),"changed after preview".getBytes("UTF-8"));LocalRecordingLifecycle same=life;
        refused(()->same.purge(A,5,token),"changed file deleted");check(Files.exists(a.get(0))&&life.get(A).getLong("revision")==5,"preflight must finish before any deletion");
        Files.write(a.get(2),original.get(a.get(2)));JSONObject fresh=life.preparePurge(A,5);refused(()->same.purge(A,5,token),"old confirmation token accepted");
        System.out.println("PASS full-set preflight and expired confirmation cannot delete a file");

        Path damaged=Files.write(m.resolve("damaged-meeting-public-fixture.bin"),"unassigned damaged fixture".getBytes("UTF-8"));
        JSONObject prepared=life.preparePurge(A,5);final int[] calls={0};
        LocalRecordingLifecycle interrupted=new LocalRecordingLifecycle(r.getParent(),r,m,path->{},path->{if(++calls[0]==2)throw new IOException("injected interruption");return Files.deleteIfExists(path);});
        refused(()->interrupted.purge(A,5,prepared.getString("token")),"interrupted deletion reported complete");
        JSONObject interruptedState=life.get(A);check(interruptedState.getBoolean("purging")&&interruptedState.getLong("revision")==6,"partial purge not persisted");
        refused(()->same.change(A,6,"restore",""),"partial purge restored as complete");
        life=lifecycle(r,m);JSONObject resumed=life.preparePurge(A,6);JSONObject cleared=life.purge(A,6,resumed.getString("token"));
        for(Path p:a)check(!Files.exists(p),"owned original remains");for(Path p:b)check(Arrays.equals(original.get(p),Files.readAllBytes(p)),"other recording modified");
        check(Files.exists(damaged)&&cleared.getInt("retainedUnassigned")==1,"unassigned damaged copy deleted or hidden");check(life.trash().getJSONArray("rows").length()==0,"completed row retained");
        refused(()->same.change(A,0,"protect",""),"purge reset revision and accepted stale pre-delete request");
        System.out.println("PASS partial purge restart/retry; other UID, AI material and unassigned copies retained");

        String c="0102030405060708090a0b0c:2:2";List<Path> extra=fixture(r,m,c);life.change(c,0,"trash","会议C");
        life.change(B,0,"protect","");ByteArrayOutputStream backup=new ByteArrayOutputStream();LibraryBackup.write(backup,r,m,null);
        Path recovered=base.resolve("restored");LibraryBackup.restore(new ByteArrayInputStream(backup.toByteArray()),recovered);
        check(lifecycle(recovered.resolve("recordings"),recovered.resolve("meetings")).get(B).getBoolean("protected"),"backup lost protection");
        LocalRecordingLifecycle restored=lifecycle(recovered.resolve("recordings"),recovered.resolve("meetings"));check(restored.get(c).getLong("trashedAt")>0,"backup lost trash state");restored.change(c,1,"restore","");
        for(Path p:extra){Path copy=recovered.resolve(p.startsWith(r)?"recordings":"meetings").resolve((p.startsWith(r)?r:m).relativize(p));check(Arrays.equals(Files.readAllBytes(p),Files.readAllBytes(copy)),"restored backup lost original contents");}
        Path state=m.resolve("recording-lifecycle").resolve(LocalRecordingLifecycle.hash(B)+".state.json");byte[] good=Files.readAllBytes(state);Files.write(state,"{broken".getBytes("UTF-8"));
        LocalRecordingLifecycle broken=life;refused(()->broken.get(B),"corrupt state became unprotected");check(life.trash().getInt("problems")==1,"unreadable state not reported");Files.write(state,good);
        Path sibling=Files.createDirectory(base.resolve("sibling-library"));Path keep=Files.write(sibling.resolve("keep.txt"),"other library".getBytes("UTF-8"));
        refused(()->same.get("../../sibling-library"),"path escaped");check(Files.exists(keep),"other library touched");
        refused(()->new LocalRecordingLifecycle(base.resolve("other-app"),r,m,path->{}).get(B),"managed directory outside trusted app root accepted");
        JSONObject next=life.preparePurge(c,1);
        LocalRecordingLifecycle syncFailure=new LocalRecordingLifecycle(r.getParent(),r,m,path->{throw new IOException("injected directory publication failure");});
        refused(()->syncFailure.purge(c,1,next.getString("token")),"publication failure ignored");
        for(Path p:extra)check(Files.exists(p),"a file deleted before durable purge state");
        check(life.get(c).getBoolean("purging"),"failure state cannot be resumed");
        System.out.println("PASS existing full backup retains lifecycle, corrupt state fails closed, other library and path traversal protection");
        System.out.println("PASS simulated directory-publication failure refuses data deletion; real Android fsync remains device acceptance");
        System.out.println("Synthetic artifacts retained at "+base);
    }
}
