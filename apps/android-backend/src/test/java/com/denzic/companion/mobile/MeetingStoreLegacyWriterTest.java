package com.denzic.companion.mobile;

import java.nio.file.Path;

/** Compile this writer with the preceding backend to test old-client compatibility. */
public final class MeetingStoreLegacyWriterTest {
    public static void main(String[] args)throws Exception {
        MeetingStore store=new MeetingStore(Path.of(args[0]));String key="public-long-meeting";
        MeetingStore.Snapshot row=store.load(key);if(row==null)throw new AssertionError("old client cannot read meeting");
        String transcript=args[1].equals("transcript")?row.transcript+"旧版修订":row.transcript;
        store.save(key,row.revision,transcript,"旧版补充",row.tasks);
        System.out.println("PASS preceding backend writes "+args[1]);
    }
}
