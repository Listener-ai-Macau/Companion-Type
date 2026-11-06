package com.denzic.companion.mobile;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Long disconnect recovery and cancellation on the runner included in the Android AAR. */
public final class SyncRunnerBehaviorJvmTest {
    public static void main(String[] args) throws Exception {
        List<String> states=new ArrayList<>();int[] attempts={0};
        RecordingSyncRunner.Listener listener=new RecordingSyncRunner.Listener(){
            public void status(String state,String detail){synchronized(states){states.add(state);}}
            public void finished(RecordingLibrary.Session session){throw new AssertionError("unexpected completion");}
        };
        long[] elapsed={0};
        new RecordingSyncRunner(()->{
            attempts[0]++;
            if(attempts[0]<=10)throw new RecordingSyncRunner.LinkFailure("temporarily offline");
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync()throws IOException{throw new IOException("local file error");}
                public boolean disconnected(){return false;}
                public void close(){}
            };
        },listener,millis->{elapsed[0]+=millis;}).run();
        if(attempts[0]!=11||elapsed[0]<174034||!states.contains("reconnecting")||!states.contains("error"))
            throw new AssertionError("reception stopped before a long temporary disconnect could recover: attempts="+attempts[0]+" elapsed="+elapsed[0]);
        states.clear();int[] fatalAttempts={0};
        new RecordingSyncRunner(()->{fatalAttempts[0]++;throw new RecordingSyncRunner.ActionRequired("pairing removed");},listener,millis->{throw new AssertionError("actionable error was retried");}).run();
        if(fatalAttempts[0]!=1||!states.contains("error")||states.contains("reconnecting"))throw new AssertionError("pairing error not reported");
        states.clear();int[] permissionAttempts={0};
        new RecordingSyncRunner(()->{permissionAttempts[0]++;throw new IOException("Bluetooth permission is required",new SecurityException("revoked during connect"));},listener,
            millis->{throw new AssertionError("revoked permission was retried instead of asking for permission");}).run();
        if(permissionAttempts[0]!=1||!states.contains("error")||states.contains("reconnecting"))throw new AssertionError("revoked permission not reported");
        states.clear();AtomicBoolean permissionClosed=new AtomicBoolean();int[] permissionSyncAttempts={0};
        new RecordingSyncRunner(()->{permissionSyncAttempts[0]++;return new RecordingSyncRunner.Connection(){
            public RecordingLibrary.Session sync()throws IOException{throw new IOException("Bluetooth permission is required",new SecurityException("revoked during transfer"));}
            public boolean disconnected(){return true;}public void close(){permissionClosed.set(true);}
        };},listener,millis->{throw new AssertionError("transfer permission error was retried");}).run();
        if(permissionSyncAttempts[0]!=1||!permissionClosed.get()||!states.contains("error")||states.contains("reconnecting"))throw new AssertionError("transfer permission failure not reported");
        // Adapter availability is not an accumulated GATT failure. A user
        // turns Bluetooth on at36s, just after the old35s poll; old30s
        // backoff then delays recovery until65s despite an available card.
        states.clear();long[] adapterClock={0},restoredAt={-1};
        new RecordingSyncRunner(()->{
            if(adapterClock[0]<36000)throw new RecordingSyncRunner.BluetoothOff();
            restoredAt[0]=adapterClock[0];throw new RecordingSyncRunner.ActionRequired("availability fixture complete");
        },listener,millis->{adapterClock[0]+=millis;}).run();
        if(restoredAt[0]<36000||restoredAt[0]-36000>15000)
            throw new AssertionError("Bluetooth on waited beyond15s: restoredAt="+restoredAt[0]+" availableAt=36000");
        states.clear();long[] afterOffClock={0},realLinkWait={-1};boolean[] realLinkFailed={false};
        new RecordingSyncRunner(()->{
            if(afterOffClock[0]<36000)throw new RecordingSyncRunner.BluetoothOff();
            if(!realLinkFailed[0]){realLinkFailed[0]=true;throw new RecordingSyncRunner.LinkFailure("first real GATT failure");}
            throw new RecordingSyncRunner.ActionRequired("backoff fixture complete");
        },listener,millis->{if(realLinkFailed[0])realLinkWait[0]=millis;afterOffClock[0]+=millis;}).run();
        if(realLinkWait[0]!=5000)throw new AssertionError("Adapter-off time inflated real GATT backoff: "+realLinkWait[0]);
        states.clear();int[] bluetoothAttempts={0};
        new RecordingSyncRunner(()->{
            if(bluetoothAttempts[0]++<2)throw new RecordingSyncRunner.BluetoothOff();
            throw new RecordingSyncRunner.ActionRequired("fixture resumed");
        },listener,millis->{}).run();
        if(bluetoothAttempts[0]!=3||!states.contains("waiting_bluetooth")||!states.contains("error"))throw new AssertionError("Bluetooth off did not wait and resume");
        states.clear();AtomicBoolean oldConnectionClosed=new AtomicBoolean();int[] afterDisconnect={0};
        new RecordingSyncRunner(()->{
            if(afterDisconnect[0]++!=0)throw new RecordingSyncRunner.ActionRequired("stop fixture");
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync()throws IOException{throw new RecordingSyncRunner.LinkFailure("disconnected");}
                public boolean disconnected(){return true;}
                public void close(){oldConnectionClosed.set(true);}
            };
        },listener,millis->{if(!oldConnectionClosed.get())throw new AssertionError("old connection held during reconnect wait");}).run();
        if(afterDisconnect[0]!=2||!states.contains("reconnecting"))throw new AssertionError("disconnect was not retried");
        states.clear();AtomicBoolean stalledClosed=new AtomicBoolean();int[] timeoutConnections={0};
        new RecordingSyncRunner(()->{
            if(timeoutConnections[0]++!=0)throw new RecordingSyncRunner.ActionRequired("stop timeout fixture");
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync()throws IOException{throw new java.net.SocketTimeoutException("Bluetooth notification timed out");}
                public boolean disconnected(){return false;}
                public void close(){stalledClosed.set(true);}
            };
        },listener,millis->{if(!stalledClosed.get())throw new AssertionError("stalled connection held during retry");}).run();
        if(timeoutConnections[0]!=2||!states.contains("reconnecting"))throw new AssertionError("stalled Bluetooth was not retried");
        states.clear();AtomicBoolean failedGattClosed=new AtomicBoolean();int[] failedGattAttempts={0};
        new RecordingSyncRunner(()->{
            if(failedGattAttempts[0]++!=0)throw new RecordingSyncRunner.ActionRequired("stop GATT fixture");
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync()throws IOException{throw new RecordingSyncRunner.LinkFailure("Bluetooth write failed (133)");}
                public boolean disconnected(){return false;}public void close(){failedGattClosed.set(true);}
            };
        },listener,millis->{if(!failedGattClosed.get())throw new AssertionError("failed GATT retained during reconnect");}).run();
        if(failedGattAttempts[0]!=2||!states.contains("reconnecting"))throw new AssertionError("GATT failure was not retried");
        states.clear();CountDownLatch started=new CountDownLatch(1),release=new CountDownLatch(1);AtomicBoolean closed=new AtomicBoolean();
        RecordingSyncRunner runner=new RecordingSyncRunner(()->new RecordingSyncRunner.Connection(){
            public RecordingLibrary.Session sync()throws IOException {started.countDown();try{release.await();}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("interrupted",e);}throw new IOException("closed");}
            public boolean disconnected(){return false;}public void close(){closed.set(true);release.countDown();}
        },listener,millis->{});
        Thread t=new Thread(runner::run);t.start();if(!started.await(5,TimeUnit.SECONDS))throw new AssertionError("sync did not start");
        runner.stop();t.join(5000);if(t.isAlive()||!closed.get()||!states.contains("stopped")||states.contains("error"))throw new AssertionError("stop did not close active connection cleanly");
        states.clear();CountDownLatch waiting=new CountDownLatch(1);
        RecordingSyncRunner retrying=new RecordingSyncRunner(()->{throw new RecordingSyncRunner.LinkFailure("offline");},listener,millis->{waiting.countDown();Thread.sleep(millis);});
        Thread retryThread=new Thread(retrying::run);retryThread.start();
        if(!waiting.await(5,TimeUnit.SECONDS))throw new AssertionError("reconnect wait did not start");
        retrying.stop();retryThread.join(5000);
        if(retryThread.isAlive()||!states.contains("stopped")||states.contains("error"))throw new AssertionError("stop did not interrupt reconnect wait");
        System.out.println("PASS long reconnect, actionable errors, connection cleanup and user stop");
    }
}
