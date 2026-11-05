package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Saved positions follow the original transcript and recording across process restarts. */
public final class MeetingTranscriptTimingTest {
    private interface Checked {void run()throws Exception;}
    private static void fails(Checked action)throws Exception {
        try{action.run();throw new AssertionError("expected failure");}catch(IOException expected){}
    }
    private static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory(Paths.get(args[0]),"timed-meeting-");
        Path audio=root.resolve("source.wav");Files.write(audio,new byte[]{1,2,3,4});
        MeetingStore store=new MeetingStore(root);String key="device:epoch:session",text="讨论包装 🚀\n周五前发送报价";
        List<MeetingStore.TranscriptWindow> windows=Arrays.asList(
            new MeetingStore.TranscriptWindow("讨论包装 🚀",0,17000),
            new MeetingStore.TranscriptWindow("周五前发送报价",17000,42000));
        MeetingStore.Snapshot saved=store.save(key,0,text,"手写备注",Collections.singletonList(new MeetingStore.Task("one","检查样品",null,null,false)));
        store.saveTranscriptTiming(key,text,audio,42000,windows);
        MeetingStore reopened=new MeetingStore(root);MeetingStore.TranscriptTiming loaded=reopened.loadTranscriptTiming(key,audio);
        check(loaded!=null&&loaded.durationMs==42000&&loaded.windows.size()==2&&loaded.windows.get(0).text.equals("讨论包装 🚀")&&loaded.windows.get(1).startMs==17000,"timing did not reopen");
        check(loaded.unrecognized==null,"legacy timing must not claim complete coverage");
        List<MeetingStore.UnrecognizedRange> gaps=Arrays.asList(new MeetingStore.UnrecognizedRange(17000,19000));
        store.saveTranscriptTiming(key,text,audio,42000,windows,gaps);
        loaded=reopened.loadTranscriptTiming(key,audio);
        check(loaded.unrecognized!=null&&loaded.unrecognized.size()==1&&loaded.unrecognized.get(0).startMs==17000&&loaded.unrecognized.get(0).endMs==19000,"unrecognized range did not reopen");
        fails(()->store.saveTranscriptTiming(key,text,audio,42000,windows,Arrays.asList(new MeetingStore.UnrecognizedRange(41000,43000))));
        check(reopened.loadTranscriptTiming(key,audio).unrecognized.size()==1,"invalid ranges replaced saved coverage");
        fails(()->store.saveTranscriptTiming(key,text,audio,42000,Collections.singletonList(windows.get(0))));
        fails(()->store.saveTranscriptTiming(key,text,audio,42000,Arrays.asList(windows.get(0),new MeetingStore.TranscriptWindow("周五前发送报价",16000,42000))));
        check(reopened.loadTranscriptTiming(key,audio).windows.size()==2,"failed save replaced timing");
        store.saveTranscriptTiming(key,text,audio,42000,Arrays.asList(windows.get(0),new MeetingStore.TranscriptWindow("周五前发送报价",16999,42000)));
        check(reopened.loadTranscriptTiming(key,audio).windows.get(1).startMs==16999,"one millisecond sample rounding was rejected");
        check(reopened.loadTranscriptTiming(key,audio).unrecognized==null,"old save retained stale coverage");
        store.saveTranscriptTiming(key,text,audio,42000,windows,Collections.emptyList());
        check(reopened.loadTranscriptTiming(key,audio).unrecognized.isEmpty(),"empty coverage was not persisted");
        Files.write(audio,new byte[]{1,2,3,5});check(reopened.loadTranscriptTiming(key,audio)==null,"changed audio was accepted");
        Files.write(audio,new byte[]{1,2,3,4});check(reopened.loadTranscriptTiming(key,audio)!=null,"unchanged audio was not usable");
        store.save(key,saved.revision,text+"修订","手写备注",saved.tasks);
        check(reopened.loadTranscriptTiming(key,audio)==null,"changed transcript was accepted");
        fails(()->store.saveTranscriptTiming(key,text,audio,42000,windows));
        check(store.load(key).notes.equals("手写备注")&&store.load(key).tasks.size()==1,"user content changed");
        check(store.deleteTranscriptTiming(key)&&!store.deleteTranscriptTiming(key),"timing deletion failed");
        check(reopened.loadTranscriptTiming(key,audio)==null,"deleted timing reopened");
        if(args.length>2) {
            List<String> lines=Files.readAllLines(Paths.get(args[1]),StandardCharsets.UTF_8);
            long duration=Long.parseLong(lines.get(0));
            String realText=new String(java.util.Base64.getDecoder().decode(lines.get(1)),StandardCharsets.UTF_8);
            java.util.ArrayList<MeetingStore.TranscriptWindow> realWindows=new java.util.ArrayList<>();
            for(int i=2;i<lines.size();i++) {
                String[] fields=lines.get(i).split(" ");
                realWindows.add(new MeetingStore.TranscriptWindow(new String(java.util.Base64.getDecoder().decode(fields[2]),StandardCharsets.UTF_8),Long.parseLong(fields[0]),Long.parseLong(fields[1])));
            }
            String realKey="public-real-recognition";
            Path realAudio=Paths.get(args[2]);
            store.saveTranscription(realKey,null,realText);store.saveTranscriptTiming(realKey,realText,realAudio,duration,realWindows);
            MeetingStore.TranscriptTiming realResult=reopened.loadTranscriptTiming(realKey,realAudio);
            check(realResult!=null&&realResult.windows.size()==realWindows.size(),"actual recognizer result did not reopen");
        }
        System.out.println("PASS timing reopen, content identity, edits and deletion");
    }
}
