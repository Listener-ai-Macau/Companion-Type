package com.denzic.companion.mobile;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** A connection can succeed while the selected device exposes an unsupported protocol. */
public final class SyncConnectFailureJvmTest {
    public static void main(String[] args) throws Exception {
        List<String> states=new ArrayList<>();List<String> details=new ArrayList<>();boolean[] closed={false};int[] attempts={0};
        RecordingSyncRunner.Listener listener=new RecordingSyncRunner.Listener(){
            public void status(String state,String detail){states.add(state);details.add(detail);}
            public void finished(RecordingLibrary.Session session){throw new AssertionError("unexpected completion");}
        };
        new RecordingSyncRunner(()->{
            attempts[0]++;
            RecordingClient.Link link=new RecordingClient.Link(){
                public int mtu(){return 247;} public byte[] read(UUID id){return new byte[]{2};}
                public void subscribe(UUID id){} public void write(UUID id,byte[] value){}
                public byte[] await(UUID id,long timeout){return null;} public void close(){closed[0]=true;}
            };
            new RecordingClient(link);throw new AssertionError("invalid device unexpectedly accepted");
        },listener,millis->{throw new InterruptedException("do not loop fixture");}).run();
        if(attempts[0]!=1||!closed[0]||!states.contains("error")||states.contains("reconnecting"))
            throw new AssertionError("unsupported device status must stop with actionable error; attempts="+attempts[0]+" states="+states+" closed="+closed[0]);
        if(details.stream().noneMatch(s->s.contains("设备")||s.contains("录音卡")))throw new AssertionError("error is not understandable: "+details);
        states.clear();details.clear();int[] retries={0};
        new RecordingSyncRunner(()->{if(retries[0]++==0)throw new RecordingSyncRunner.LinkFailure("temporary link failure");throw new RecordingSyncRunner.ActionRequired("finished fixture");},listener,millis->{}).run();
        if(retries[0]!=2||!states.contains("reconnecting"))throw new AssertionError("temporary link failure did not resume");
        System.out.println("PASS connection-stage protocol errors stop and transient links retry");
    }
}
