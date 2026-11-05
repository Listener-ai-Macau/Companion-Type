package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.zip.CRC32;

/** Real JNI control while an actual RecordingClient download holds its session lock. */
public final class LiveControlDuringDownloadJvmTest {
    static void put(byte[] a,int at,long n,int count){for(int i=0;i<count;i++)a[at+i]=(byte)(n>>>(8*i));}
    static long crc(byte[] a){CRC32 c=new CRC32();c.update(a);return c.getValue();}
    public static void main(String[] args)throws Exception {
        Path root=Paths.get(args[0]);Files.createDirectories(root);byte[] golden=Files.readAllBytes(Paths.get(args[1]));
        NativeRecordingControlJvmTest.Fake fake=new NativeRecordingControlJvmTest.Fake(golden);
        byte[] audio=new byte[]{'C','O','P','1',3,1,20,3,(byte)128,62,0,0,1,0,0};byte[] digest=MessageDigest.getInstance("SHA-256").digest(audio);
        byte[] desc=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,desc,0,4);put(desc,4,2,2);put(desc,6,112,2);
        put(desc,8,41,4);put(desc,12,7,8);put(desc,20,7,8);put(desc,40,320,8);put(desc,48,audio.length,4);put(desc,52,crc(audio),4);
        System.arraycopy(digest,0,desc,56,32);put(desc,88,1,4);desc[92]=3;desc[93]=3;System.arraycopy(fake.identity,20,desc,96,12);
        CRC32 dc=new CRC32();dc.update(desc,0,108);put(desc,108,dc.getValue(),4);fake.descriptor=desc;
        CountDownLatch waiting=new CountDownLatch(1),release=new CountDownLatch(1);
        RecordingClient.Link link=new RecordingClient.Link(){
            public int mtu(){return fake.mtu();}public String deviceAddress(){return fake.deviceAddress();}
            public byte[] read(UUID id)throws IOException{return fake.read(id);}public void subscribe(UUID id){fake.subscribe(id);}
            public void write(UUID id,byte[] value)throws IOException{if(!id.equals(RecordingClient.RECORDING_PULL))fake.write(id,value);}
            public byte[] await(UUID id,long timeout)throws IOException {
                if(!id.equals(RecordingClient.RECORDING_PULL))return fake.await(id,timeout);
                waiting.countDown();try{if(!release.await(8,TimeUnit.SECONDS))throw new IOException("test transfer timed out");}
                catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("test interrupted",e);}
                byte[] packet=new byte[56+audio.length];packet[0]=1;packet[1]=1;put(packet,2,audio.length,2);put(packet,4,41,4);put(packet,16,audio.length,4);
                System.arraycopy(digest,0,packet,24,32);System.arraycopy(audio,0,packet,56,audio.length);CRC32 c=new CRC32();c.update(packet,4,16);c.update(audio);put(packet,20,c.getValue(),4);return packet;
            }
            public void close(){release.countDown();fake.close();}
        };
        ExecutorService pool=Executors.newFixedThreadPool(2);
        try(RecordingClient client=new RecordingClient(link,dir->{},prefix->{})) {
            Path control=root.resolve("control");String session=NativeRecordingControl.newSessionId();
            NativeRecordingControlJvmTest.expect(client.control(control,session,NativeRecordingControl.Action.START,120),"recording");
            client.listRecordings();Future<Path> transfer=pool.submit(()->client.download(41,root.resolve("recordings"),null));
            if(!waiting.await(5,TimeUnit.SECONDS))throw new AssertionError("download did not start");
            Future<String> stop=pool.submit(()->client.controlDuringSync(control,session,NativeRecordingControl.Action.STOP,0));
            String result=stop.get(5,TimeUnit.SECONDS);NativeRecordingControlJvmTest.expect(result,"stopped");
            if(transfer.isDone())throw new AssertionError("transfer finished before control test");
            try{client.controlDuringSync(control,session,NativeRecordingControl.Action.START,120);throw new AssertionError("new start was accepted during sync");}catch(IOException expected){}
            release.countDown();Path saved=transfer.get(5,TimeUnit.SECONDS);
            if(!Arrays.equals(Files.readAllBytes(saved),audio)||fake.writes!=2)throw new AssertionError("audio or control command changed");
            System.out.println("PASS stop confirmed during active segment download; original bytes preserved");
        } finally {release.countDown();pool.shutdownNow();}
    }
}
