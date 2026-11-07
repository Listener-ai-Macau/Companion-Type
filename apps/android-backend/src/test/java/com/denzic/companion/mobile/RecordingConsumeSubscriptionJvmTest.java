package com.denzic.companion.mobile;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Exercise the actual download path, stopping at a controlled data wait. */
public final class RecordingConsumeSubscriptionJvmTest {
    static void check(boolean value){if(!value)throw new AssertionError();}
    static final class Link implements RecordingClient.Link {
        final RecordingDirectoryStreamJvmTest.Link base;
        final RecordingTransferMetrics metrics;
        final boolean prepare,failSubscription;
        boolean pulled,awaited;int consumeSubscriptions;
        Link(byte[] golden,RecordingTransferMetrics metrics,boolean prepare,boolean failSubscription){
            base=new RecordingDirectoryStreamJvmTest.Link(golden,66712,false);
            this.metrics=metrics;this.prepare=prepare;this.failSubscription=failSubscription;
        }
        public int mtu(){return 512;}
        public byte[] read(UUID id){return base.read(id);}
        public void close(){}
        public void subscribe(UUID id)throws IOException{
            if(id.equals(RecordingClient.RECORDING_CONSUME)){
                check(prepare&&pulled&&!metrics.json().contains("\"firstWindowNanos\":null"));
                consumeSubscriptions++;
                if(failSubscription)throw new IOException("controlled subscription failure");
            }
        }
        public void write(UUID id,byte[] value)throws IOException{
            check(!id.equals(RecordingClient.RECORDING_CONSUME));
            if(id.equals(RecordingClient.RECORDING_PULL)){check(consumeSubscriptions==0);pulled=true;}
            else base.write(id,value);
        }
        public byte[] await(UUID id,long timeout)throws IOException{
            if(id.equals(RecordingClient.RECORDING_PULL)){
                check(pulled&&consumeSubscriptions==(prepare?1:0));awaited=true;
                throw new IOException("controlled data wait failure");
            }
            return base.await(id,timeout);
        }
    }
    public static void main(String[] args)throws Exception{
        byte[] golden=Files.readAllBytes(Paths.get(args[0]));
        RecorderWire.Descriptor selected=RecorderWire.Descriptor.decode(Arrays.copyOfRange(golden,24,136));
        for(int mode=0;mode<3;mode++){
            boolean prepare=mode!=0,fail=mode==2;
            RecordingTransferMetrics metrics=new RecordingTransferMetrics();Link link=new Link(golden,metrics,prepare,fail);
            Path directory=Files.createTempDirectory("companion-subscribe-");
            try(RecordingClient client=new RecordingClient(link,d->{},prefix->{},metrics)){
                Field current=RecordingClient.class.getDeclaredField("current");current.setAccessible(true);current.set(client,Collections.singletonList(selected));
                try{
                    if(!prepare)client.download(selected.recordingId,directory,null);
                    else {
                        Method download=RecordingClient.class.getDeclaredMethod("download",long.class,Path.class,RecordingClient.Progress.class,boolean.class);
                        download.setAccessible(true);
                        try{download.invoke(client,selected.recordingId,directory,null,true);}
                        catch(InvocationTargetException error){throw (IOException)error.getCause();}
                    }
                    throw new AssertionError("controlled failure was lost");
                }catch(IOException expected){check(expected.getMessage().startsWith("controlled"));}
                check(link.pulled&&link.consumeSubscriptions==(prepare?1:0)&&link.awaited!=fail);
                check(!Files.exists(directory.resolve(".consume-pending")));
                check(metrics.json().contains("\"dataWindows\":1")&&!metrics.json().contains("\"firstWindowNanos\":null"));
            }
        }
        System.out.println("PASS_ACTUAL_DOWNLOAD_SUBSCRIPTION_AFTER_PULL_INSIDE_TIMER_COPY_ONLY_UNCHANGED_NO_EARLY_CONSUME_FAILURE_PROPAGATES");
    }
}
