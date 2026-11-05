package com.denzic.companion.mobile;
import java.io.IOException;
import java.nio.file.*;
import java.util.Collections;
/** Real meeting store restore with distinct transcript versions and conflicts. */
public final class MeetingMinutesHistoryRestoreTest {
 private static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 private interface Checked {void run()throws Exception;}
 private static void fails(Checked op)throws Exception {try{op.run();throw new AssertionError("stale restore accepted");}catch(IOException expected){}}
 public static void main(String[] args)throws Exception {
  Path root=Files.createTempDirectory(Paths.get(args[0]),"minutes-restore-");MeetingStore store=new MeetingStore(root);String key="fixture-device:meeting";
  MeetingStore.Snapshot first=store.save(key,0,"原来的文字","用户备注",Collections.emptyList());
  store.saveMinutes(key,first.revision,0,first.transcript,"旧版人工修改");
  MeetingStore.Snapshot second=store.save(key,1,"新的修订文字","用户备注",Collections.emptyList());
  store.saveMinutes(key,second.revision,1,second.transcript,"新版人工修改");
  MeetingStore.Minutes previous=store.listMinutesHistory(key).versions.get(0);check(previous.json.equals("旧版人工修改")&&previous.sourceChanged,"old source status");
  fails(()->store.restoreMinutesHistory(key,second.revision,1,previous.historyId));
  check(store.loadMinutes(key).json.equals("新版人工修改"),"stale request changed current");
  MeetingStore.Minutes restored=store.restoreMinutesHistory(key,second.revision,2,previous.historyId);
  check(restored.json.equals("旧版人工修改")&&restored.sourceChanged&&restored.sourceMeetingRevision==1&&restored.revision==3,"restore lost original source");
  MeetingStore.MinutesHistory history=store.listMinutesHistory(key);check(history.versions.size()==2&&history.versions.get(0).json.equals("新版人工修改"),"newer version not retained");
  check(store.load(key).transcript.equals("新的修订文字")&&store.load(key).notes.equals("用户备注"),"restore changed source");
  MeetingStore.Minutes newest=history.versions.get(0);MeetingStore.Minutes back=store.restoreMinutesHistory(key,second.revision,3,newest.historyId);
  check(back.json.equals("新版人工修改")&&!back.sourceChanged&&back.sourceMeetingRevision==2,"switch back source incorrect");
  System.out.println("PASS mobile history restore, preserved current, original source metadata and conflict handling");
 }
}
