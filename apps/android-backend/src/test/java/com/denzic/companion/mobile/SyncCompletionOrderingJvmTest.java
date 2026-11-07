package com.denzic.companion.mobile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/** Execute the production runner with a real, verified own-test original. */
public final class SyncCompletionOrderingJvmTest {
    public static void main(String[] args)throws Exception {
        Path directory=Paths.get(args[0]);Files.createDirectory(directory);
        RecorderWire.Descriptor d=RecorderWire.Descriptor.decode(Files.readAllBytes(Paths.get(args[1])));
        String key=SegmentReceiver.key(d);
        Files.copy(Paths.get(args[1]),directory.resolve(key+".meta"));
        Files.copy(Paths.get(args[2]),directory.resolve(key+".cop1"));
        RecordingLibrary.Session session=RecordingLibrary.sessions(directory,d).get(0);
        if(session.state!=RecordingLibrary.SessionState.COMPLETE)throw new AssertionError("fixture must be genuinely complete");
        List<String> order=new ArrayList<>();
        new RecordingSyncRunner(()->new RecordingSyncRunner.Connection(){
            public RecordingLibrary.Session sync(){order.add("durable_receipts_complete");return session;}
            public boolean disconnected(){return false;}
            public void close(){order.add("gatt_closed");}
        },new RecordingSyncRunner.Listener(){
            public void status(String state,String detail){}
            public void finished(RecordingLibrary.Session value){order.add("public_complete");}
        },millis->{throw new AssertionError("complete task must not retry");}).run();
        if(!order.equals(java.util.Arrays.asList("durable_receipts_complete","gatt_closed","public_complete")))
            throw new AssertionError("completed receiver exposed before GATT release: "+order);
        System.out.println("PASS production runner reports completion only after connection release; real own-test original verified, no added retry");
    }
}
