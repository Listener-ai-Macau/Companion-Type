package com.denzic.companion.mobile;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;

/** Reuses an existing public meeting result; does not access any service. */
public final class MeetingMinutesPublicTest {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);String transcript=Files.readString(Path.of(args[1]),StandardCharsets.UTF_8);
        String json=Files.readString(Path.of(args[2]),StandardCharsets.UTF_8),mode=args[3];
        MeetingStore store=new MeetingStore(root);String key="public-long-meeting";
        if(mode.equals("seed")) {
            MeetingStore.Snapshot row=store.save(key,0,transcript,"",Collections.emptyList());
            store.saveMinutes(key,row.revision,0,transcript,json);
        }
        MeetingStore.Snapshot row=store.load(key);MeetingStore.Minutes minutes=store.loadMinutes(key);
        if(minutes==null||!minutes.json.equals(json)||minutes.sourceMissing)throw new AssertionError("public minutes did not survive");
        if(mode.equals("legacy-note")&&(minutes.sourceChanged||!row.notes.equals("旧版补充")))throw new AssertionError("old-client notes broke minutes");
        if(mode.equals("legacy-transcript")&&(!minutes.sourceChanged||!row.transcript.endsWith("旧版修订")))throw new AssertionError("old-client transcript edit was not detected");
        if(mode.equals("seed")&&(minutes.sourceChanged||!row.transcript.equals(transcript)))throw new AssertionError("initial public source mismatch");
        System.out.println("PASS public long-meeting minutes "+mode);
    }
}
