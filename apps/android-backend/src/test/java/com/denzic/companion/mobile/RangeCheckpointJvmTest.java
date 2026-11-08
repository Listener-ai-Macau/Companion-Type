package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.zip.CRC32;

/** Actual SegmentReceiver resume/save paths; synthetic bytes, no device/audio qualification. */
public final class RangeCheckpointJvmTest {
    interface Action {void run()throws Exception;}
    static void check(boolean b){if(!b)throw new AssertionError();}
    static void refused(Action a)throws Exception {try{a.run();throw new AssertionError("missing refusal");}catch(IOException expected){}}
    static void put(byte[] p,int at,long v,int n){for(int i=0;i<n;i++)p[at+i]=(byte)(v>>>(i*8));}
    static long crc(byte[] p,int n){CRC32 c=new CRC32();c.update(p,0,n);return c.getValue();}
    static final byte[] data=new byte[9000];
    static RecorderWire.Descriptor descriptor()throws Exception {
        byte[] p=new byte[112];System.arraycopy(new byte[]{'C','R','S','2',2,0,112,0},0,p,0,8);
        put(p,8,353,4);put(p,12,7,8);put(p,20,353,8);put(p,40,16000,8);
        put(p,48,data.length,4);put(p,52,crc(data,data.length),4);
        System.arraycopy(MessageDigest.getInstance("SHA-256").digest(data),0,p,56,32);
        put(p,88,1,4);p[92]=3;p[93]=3;p[95]=1;
        for(int i=0;i<12;i++)p[96+i]=(byte)(i+1);put(p,108,crc(p,108),4);
        return RecorderWire.Descriptor.decode(p);
    }
    static Path dir(RecorderWire.Descriptor d)throws Exception {
        Path p=Files.createTempDirectory("companion-range-");Files.write(p.resolve(SegmentReceiver.key(d)+".part"),data);return p;
    }
    public static void main(String[] args)throws Exception {
        for(int i=0;i<data.length;i++)data[i]=(byte)(i*37+13);
        RecorderWire.Descriptor d=descriptor();Path dir=dir(d);AtomicInteger syncs=new AtomicInteger();
        RangeCheckpoint first;
        try(SegmentReceiver receiver=new SegmentReceiver(dir,d)){
            first=receiver.checkpointRange(dir,0,1,100,p->syncs.incrementAndGet());
            check(syncs.get()==3&&first.prefixBytes==3720&&!first.confirmed);
            byte[] expected=MessageDigest.getInstance("SHA-256").digest(Arrays.copyOfRange(data,0,3720));
            check(Arrays.equals(expected,first.rangeSha()));
            check(receiver.checkpointRange(dir,0,1,100,p->syncs.incrementAndGet()).nonce==100);
            refused(()->receiver.checkpointRange(dir,0,1,101,p->{}));
            refused(()->receiver.checkpointRange(dir,-1,1,101,p->{}));
            refused(()->receiver.checkpointRange(dir,0,4,101,p->{}));
            refused(()->receiver.checkpointRange(dir.getParent(),0,1,100,p->{}));
            first.confirm(dir,p->syncs.incrementAndGet());
            check(RangeCheckpoint.read(dir,d).confirmed);
            refused(()->receiver.checkpointRange(dir,0,3,102,p->{}));
            RangeCheckpoint second=receiver.checkpointRange(dir,1,3,102,p->{});
            check(second.prefixBytes==data.length&&second.firstSector==1);
            refused(()->first.confirm(dir,p->{}));
            second.confirm(dir,p->{});
        }
        try(SegmentReceiver resumed=new SegmentReceiver(dir,d)){
            check(resumed.resumeOffset()==data.length);
            Path finished=resumed.finish();check(Files.isRegularFile(finished)&&Arrays.equals(Files.readAllBytes(finished),data));
        }
        RangeCheckpoint.verifySavedPrefix(dir,d);
        System.out.println("PASS_RANGE_HOST exact_prefix_and_range_SHA=1 data_metadata_parent_and_checkpoint_synced_before_proof=1 contiguous_frontier=1 pending_proof_not_overwritten=1 resume_and_final_original_unchanged=1");

        // Persisted proof after a failed directory sync must be re-synced on
        // retry, rather than treated as permission merely because it exists.
        Path retry=dir(d);AtomicInteger retries=new AtomicInteger();
        try(SegmentReceiver receiver=new SegmentReceiver(retry,d)){
            refused(()->receiver.checkpointRange(retry,0,1,200,p->{
                if(Files.exists(retry.resolve(SegmentReceiver.key(d)+".range")))throw new IOException("controlled final directory sync failure");
            }));
            RangeCheckpoint c=receiver.checkpointRange(retry,0,1,200,p->retries.incrementAndGet());
            check(c.nonce==200&&retries.get()==2);
        }
        System.out.println("PASS_RANGE_HOST_SYNC_FAILURE no_sendable_result_on_failed_sync=1 exact_retry_resyncs_source_metadata_proof_and_directories=1");

        for(int mode=0;mode<3;mode++){
            Path broken=dir(d);String key=SegmentReceiver.key(d);
            try(SegmentReceiver receiver=new SegmentReceiver(broken,d)){
                receiver.checkpointRange(broken,0,1,300,p->{});
            }
            if(mode==0){byte[] changed=data.clone();changed[10]^=1;Files.write(broken.resolve(key+".part"),changed);}
            if(mode==1)Files.write(broken.resolve(key+".range"),new byte[]{1,2,3});
            if(mode<2)refused(()->{try(SegmentReceiver ignored=new SegmentReceiver(broken,d)){throw new AssertionError();}});
            else {
                byte[] changed=data.clone();changed[8500]^=1;Files.write(broken.resolve(key+".part"),changed);
                try(SegmentReceiver resumed=new SegmentReceiver(broken,d)){
                    try{resumed.finish();throw new AssertionError();}
                    catch(SegmentReceiver.IntegrityMismatch unsafeRestart){throw new AssertionError("partial reclaim must not permit automatic zero restart",unsafeRestart);}
                    catch(IOException expected){}
                }
            }
            check(Files.exists(broken.resolve(key+".part")));
            try(java.util.stream.Stream<Path> files=Files.list(broken)){check(files.noneMatch(p->p.getFileName().toString().startsWith("damaged-")));}
        }
        // Unnegotiated ordinary copy still retains the original integrity retry.
        Path ordinary=dir(d);byte[] damaged=data.clone();damaged[8500]^=1;
        Files.write(ordinary.resolve(SegmentReceiver.key(d)+".part"),damaged);
        try(SegmentReceiver receiver=new SegmentReceiver(ordinary,d)){
            try{receiver.finish();throw new AssertionError();}catch(SegmentReceiver.IntegrityMismatch expected){}
        }
        System.out.println("PASS_RANGE_HOST_RECOVERY damaged_prefix_or_checkpoint_retains_sources=1 damaged_tail_no_zero_restart_after_partial_reclaim=1 ordinary_copy_integrity_behavior_retained=1 no_BLE_commands=1");
    }
}
