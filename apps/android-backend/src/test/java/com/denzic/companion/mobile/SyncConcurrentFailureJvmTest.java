package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.FileSystemException;
import java.util.ArrayList;
import java.util.List;

/** A simultaneous disconnect must not hide a local or protocol failure. */
public final class SyncConcurrentFailureJvmTest {
    public static void main(String[] args) {
        verifyTerminal(new FileSystemException("fictional-audio",null,"No space left on device"));
        verifyTerminal(new IOException("recording metadata conflict; existing copy preserved"));
        verifyLinkRetry(new IOException("wrapped link failure",new RecordingSyncRunner.LinkFailure("Bluetooth disconnected")));
        System.out.println("PASS simultaneous disconnect preserves actionable storage and metadata failures");
    }
    private static void verifyTerminal(IOException failure) {
        List<String> states=new ArrayList<>();List<String> details=new ArrayList<>();int[] attempts={0};boolean[] closed={false};
        RecordingSyncRunner.Listener listener=new RecordingSyncRunner.Listener(){
            public void status(String state,String detail){states.add(state);details.add(detail);}
            public void finished(RecordingLibrary.Session session){throw new AssertionError("unexpected completion");}
        };
        RecordingSyncRunner runner=new RecordingSyncRunner(()->{
            attempts[0]++;
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync() throws IOException {throw failure;}
                public boolean disconnected(){return true;}
                public void close(){closed[0]=true;}
            };
        },listener,millis->{throw new AssertionError("local failure was hidden by a coincident disconnect");});
        runner.run();
        if(attempts[0]!=1||!closed[0]||!states.contains("error")||states.contains("reconnecting")||!details.contains(failure.getMessage()))
            throw new AssertionError("local failure must be reported without retry: "+states);
    }
    private static void verifyLinkRetry(IOException failure) {
        List<String> states=new ArrayList<>();int[] attempts={0};boolean[] closed={false};
        RecordingSyncRunner.Listener listener=new RecordingSyncRunner.Listener(){
            public void status(String state,String detail){states.add(state);}
            public void finished(RecordingLibrary.Session session){throw new AssertionError("unexpected completion");}
        };
        new RecordingSyncRunner(()->{
            if(attempts[0]++>0)throw new RecordingSyncRunner.ActionRequired("end fixture");
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync() throws IOException {throw failure;}
                public boolean disconnected(){return true;}
                public void close(){closed[0]=true;}
            };
        },listener,millis->{if(!closed[0])throw new AssertionError("link was not closed");}).run();
        if(attempts[0]!=2||!states.contains("reconnecting"))throw new AssertionError("typed link failure must reconnect");
    }
}
