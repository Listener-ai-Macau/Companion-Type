package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/** Actual receiver, filesystem, locked source and durable proof; blocking disk
 * barrier is deterministic. This is a concurrency test, never a radio rate. */
public final class RangeCheckpointOverlapJvmTest {
    static void check(boolean b){if(!b)throw new AssertionError();}
    static RecorderWire.Descriptor descriptor(byte[] data)throws Exception {
        byte[] wire=RangeCheckpointJvmTest.descriptor().wireBytes();
        RangeConsumeClientJvmTest.put(wire,48,data.length,4);
        RangeConsumeClientJvmTest.put(wire,52,RecorderWire.crc(data,0,data.length),4);
        System.arraycopy(MessageDigest.getInstance("SHA-256").digest(data),0,wire,56,32);
        RangeConsumeClientJvmTest.put(wire,108,RecorderWire.crc(wire,0,108),4);
        return RecorderWire.Descriptor.decode(wire);
    }
    static final class Case {
        final byte[] data;final RecorderWire.Descriptor d;final Path dir;
        final RangeConsumeClientJvmTest.Device device;
        final RangeConsumeClientJvmTest.Link link;
        final CountDownLatch diskEntered=new CountDownLatch(1),releaseDisk=new CountDownLatch(1),done=new CountDownLatch(1);
        final AtomicBoolean firstSync=new AtomicBoolean(true);
        final AtomicReference<Throwable> failure=new AtomicReference<>();
        final boolean failDisk;final Thread receiver;
        Case(int bytes,boolean failDisk)throws Exception {
            this.failDisk=failDisk;data=new byte[bytes];for(int i=0;i<bytes;i++)data[i]=(byte)(i*37+13);
            d=descriptor(data);dir=Files.createTempDirectory("companion-range-disk-overlap-");
            device=new RangeConsumeClientJvmTest.Device(d,data);link=new RangeConsumeClientJvmTest.Link(device,dir,false,false,false);
            link.waitForRangeRequest=false;
            receiver=new Thread(()->{
                try{Path file=RangeConsumeClientJvmTest.download(link,d,true,p->{
                    if(firstSync.compareAndSet(true,false)){
                        diskEntered.countDown();boolean interrupted=false;
                        while(true)try{releaseDisk.await();break;}catch(InterruptedException e){interrupted=true;}
                        if(interrupted)Thread.currentThread().interrupt();
                        if(this.failDisk)throw new IOException("controlled directory sync failure");
                    }
                });check(Arrays.equals(data,Files.readAllBytes(file)));}
                catch(Throwable e){failure.set(e);}finally{done.countDown();}
            },"actual-recording-receiver");
            receiver.setDaemon(true);receiver.start();
        }
        boolean dataContinues()throws Exception {
            check(diskEntered.await(2,TimeUnit.SECONDS));
            boolean continued=link.advanced.await(300,TimeUnit.MILLISECONDS);
            check(link.requests==0&&device.end==0); // still no durable authorization
            return continued;
        }
        void releaseAndJoin()throws Exception {releaseDisk.countDown();check(done.await(3,TimeUnit.SECONDS));receiver.join();}
    }
    public static void main(String[] args)throws Exception {
        Case wide=new Case(63000,false);boolean continued;
        try{continued=wide.dataContinues();}finally{wide.releaseAndJoin();}
        if(!continued){System.out.println("FAIL_RECEIVE_BLOCKED_BY_CHECKPOINT_DURABILITY");System.exit(71);}
        check(wide.failure.get()==null&&wide.link.requests==1&&wide.link.receipts==1);
        Case shortFile=new Case(22610,false);
        try{check(shortFile.dataContinues());}finally{shortFile.releaseAndJoin();}
        check(shortFile.failure.get()==null&&shortFile.link.requests==1&&shortFile.link.receipts==1&&shortFile.device.end==1);
        // Failed source durability never sends an erase request, even when all
        // later radio bytes arrived while the first prefix was being synced.
        Case failed=new Case(63000,true);
        try{check(failed.dataContinues());}finally{failed.releaseAndJoin();}
        check(failed.failure.get() instanceof IOException&&failed.link.requests==0&&failed.device.end==0);
        try(SegmentReceiver saved=new SegmentReceiver(failed.dir,failed.d)){check(saved.resumeOffset()==failed.data.length);saved.verifyOriginal();}
        // Simulate an uninterruptible filesystem call, then a user cancellation.
        // Keep the exact file owner until it returns; never send a late request.
        Case cancelled=new Case(63000,false);
        try {
            check(cancelled.dataContinues());cancelled.receiver.interrupt();
            try(SegmentReceiver second=new SegmentReceiver(cancelled.dir,cancelled.d)){throw new AssertionError("receiver lock released while disk worker is live");}
            catch(IOException expected){}
        }finally{cancelled.releaseAndJoin();}
        check(cancelled.failure.get() instanceof IOException&&cancelled.link.requests==0&&cancelled.device.end==0);
        try(SegmentReceiver saved=new SegmentReceiver(cancelled.dir,cancelled.d)){check(saved.resumeOffset()==cancelled.data.length);saved.verifyOriginal();}
        System.out.println("PASS actual audio receive continues during durable checkpoint; zero destructive requests before disk sync or after failure/cancel; owner retained until disk worker stops; exact saved sources retained. Radio/speed NOT_RUN.");
    }
}
