package com.denzic.companion.mobile;
import java.nio.file.*;
import java.util.*;
import java.io.IOException;

public final class MeetingMinutesManualEditTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    public static void main(String[]args)throws Exception{
        Path root=Files.createTempDirectory(Paths.get(args[0]),"manual-minutes-");MeetingStore store=new MeetingStore(root);
        MeetingStore.Snapshot meeting=store.save("meeting",0,"周五发报价。","保留我的补充",Collections.emptyList());
        String original="{\"markdown\":\"## Action Items\\n- 周五发报价\"}";
        MeetingStore.Minutes first=store.saveMinutes("meeting",meeting.revision,0,meeting.transcript,original);
        MeetingStore.Snapshot corrected=store.saveTranscriptCorrection("meeting",meeting.revision,"周五核对报价。");
        check(store.loadMinutes("meeting").sourceChanged,"source revision did not become stale");
        String manual="{\"markdown\":\"## Action Items\\n- [ ] 周五发报价 (owner: 小王, due: 周五)\",\"manualReview\":{\"version\":1}}";
        MeetingStore.Minutes edited=store.saveEditedMinutes("meeting",corrected.revision,first.revision,original,manual,false);
        check(edited.sourceChanged&&edited.sourceMeetingRevision==first.sourceMeetingRevision,"manual task edit silently refreshed old source");
        check(store.listMinutesHistory("meeting").versions.size()==1&&store.listMinutesHistory("meeting").versions.get(0).json.equals(original),"original AI version was lost");
        try{store.saveEditedMinutes("meeting",corrected.revision,first.revision,original,"lost",false);throw new AssertionError("old minutes revision accepted");}catch(IOException expected){}
        check(store.loadMinutes("meeting").json.equals(manual),"failed write replaced manual result");
        String reviewed=manual.replace("\"version\":1","\"version\":1,\"sourceReviewed\":true");
        MeetingStore.Minutes current=store.saveEditedMinutes("meeting",corrected.revision,edited.revision,manual,reviewed,true);
        check(!current.sourceChanged&&current.sourceMeetingRevision==corrected.revision,"explicit source review did not bind current source");
        check(store.listMinutesHistory("meeting").versions.size()==2,"review removed earlier versions");
        check(store.load("meeting").transcript.equals(corrected.transcript)&&store.load("meeting").notes.equals("保留我的补充"),"minutes editing altered source text or notes");
        store.saveTranscriptCorrection("meeting",corrected.revision,"改为下周核对报价。");
        check(store.loadMinutes("meeting").sourceChanged,"later source edit failed to invalidate manual review");
        try{store.saveEditedMinutes("meeting",corrected.revision,current.revision,reviewed,"lost",true);throw new AssertionError("old meeting revision accepted");}catch(IOException expected){}
        check(new MeetingStore(root).loadMinutes("meeting").json.equals(reviewed),"reopening lost the confirmed version");
        System.out.println("PASS manual minutes editing preserves old source/history, requires explicit current-source review, rejects races and preserves transcript/notes on reopening");
    }
}
