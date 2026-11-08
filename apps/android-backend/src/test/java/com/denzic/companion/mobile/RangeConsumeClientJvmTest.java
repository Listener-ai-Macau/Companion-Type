package com.denzic.companion.mobile;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.zip.CRC32;

/** Actual private download path; deterministic link model, not physical timing. */
public final class RangeConsumeClientJvmTest {
    static void check(boolean b){if(!b)throw new AssertionError();}
    static void put(byte[] p,int at,long n,int size){for(int i=0;i<size;i++)p[at+i]=(byte)(n>>>(8*i));}
    static int u16(byte[] p,int at){return(p[at]&255)|((p[at+1]&255)<<8);}
    static final class Device {
        final RecorderWire.Descriptor d;final byte[] bytes;
        long nonce;int first,end;boolean pending;
        Device(RecorderWire.Descriptor d,byte[] bytes){this.d=d;this.bytes=bytes;}
    }
    static final class Link implements RecordingClient.Link {
        final Device device;final Path directory;final boolean legacy,busy,disconnect;
        final CountDownLatch requested=new CountDownLatch(1),advanced=new CountDownLatch(1);
        volatile byte[] control,range;volatile int offset,sequence,queries,requests,receipts;
        volatile boolean pulled,dataComplete,closed;
        boolean expectRange=true,waitForRangeRequest=true;volatile int firstWriteOffset;
        Link(Device d,Path directory,boolean legacy,boolean busy,boolean disconnect){this.device=d;this.directory=directory;this.legacy=legacy;this.busy=busy;this.disconnect=disconnect;}
        public int mtu(){return 512;}
        public void subscribe(UUID id){}
        public void close(){closed=true;}
        public byte[] read(UUID id){
            byte[] p=new byte[116];p[0]=1;put(p,4,66743,4);put(p,12,0x57424155L,4);
            System.arraycopy(device.d.uid(),0,p,20,12);System.arraycopy(new byte[]{'C','R','V','2',2,0,32,0},0,p,84,8);
            put(p,92,2047,4);put(p,96,device.d.epoch,8);put(p,104,64,2);put(p,106,1024,2);put(p,108,509,2);
            put(p,112,RecorderWire.crc(p,84,28),4);return p;
        }
        public void write(UUID id,byte[] p)throws IOException {
            if(id.equals(RecordingClient.RECORDING_CONTROL)){
                control=p.clone();if(legacy){control[3]&=(byte)0xbf;put(control,28,RecorderWire.crc(control,0,28),4);}return;
            }
            if(id.equals(RecordingClient.RECORDING_PULL)){
                offset=(int)RecorderWire.u32(p,28);sequence=0;pulled=true;
                int missing=device.end==0?0:Math.min(device.bytes.length,(device.end*16-1)*248);
                if(offset<missing)throw new IOException("model cannot reread physically reclaimed prefix");
                return;
            }
            check(id.equals(RecordingClient.RECORDING_CONSUME)&&p.length==96&&RecorderWire.magic(p,0,"CRG3"));
            check(RecorderWire.crc(p,0,92)==RecorderWire.u32(p,92)&&RecorderWire.u32(p,52)==RangeConsume.binding(device.d));
            range=p.clone();if(p[88]==0){queries++;return;}
            if(!pulled){
                Path part=directory.resolve(SegmentReceiver.key(device.d)+".part"),complete=directory.resolve(SegmentReceiver.key(device.d)+".cop1");
                check(Files.size(Files.exists(complete)?complete:part)==device.bytes.length);
                offset=device.bytes.length;dataComplete=true;
            }
            requests++;
            RangeCheckpoint saved=RangeCheckpoint.read(directory,device.d);
            check(saved.nonce==RecorderWire.u32(p,44)&&!saved.confirmed);
            int first=u16(p,48),end=u16(p,50),begin=first==0?0:(first*16-1)*248;
            if(requests==1&&device.bytes.length==63000&&device.end==0)check(first==0&&end==8);
            int limit=Math.min(device.bytes.length,(end*16-1)*248);
            try{check(Arrays.equals(MessageDigest.getInstance("SHA-256").digest(Arrays.copyOfRange(device.bytes,begin,limit)),Arrays.copyOfRange(p,56,88)));}
            catch(java.security.NoSuchAlgorithmException e){throw new AssertionError(e);}
            boolean exactPendingReplay=device.pending&&device.nonce==RecorderWire.u32(p,44)&&first==device.first&&end==device.end;
            check(first==device.end||exactPendingReplay);device.first=first;device.end=end;device.nonce=RecorderWire.u32(p,44);device.pending=false;
            firstWriteOffset=offset;requested.countDown();if(dataComplete)advanced.countDown();
        }
        private byte[] rangeReply(byte[] q)throws IOException {
            if(q[88]!=0){
                if(disconnect)throw new RecordingSyncRunner.LinkFailure("controlled disconnect after durable range intent");
                try{check(advanced.await(2,TimeUnit.SECONDS));}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
                receipts++;
            }
            byte[] p=new byte[60];System.arraycopy(new byte[]{'C','R','R','3',3,0,60,0},0,p,0,8);
            System.arraycopy(device.d.uid(),0,p,8,12);put(p,20,device.d.epoch,8);put(p,28,device.d.recordingId,4);
            put(p,32,RecorderWire.u32(q,44),4);put(p,36,device.nonce,4);put(p,40,device.first,2);put(p,42,device.end,2);
            put(p,44,busy?4:0,4);p[48]=(byte)(device.pending?1:0);put(p,52,RangeConsume.binding(device.d),4);
            put(p,56,RecorderWire.crc(p,0,56),4);return p;
        }
        public byte[] await(UUID id,long timeout)throws IOException {
            if(id.equals(RecordingClient.RECORDING_CONTROL))return control.clone();
            if(id.equals(RecordingClient.RECORDING_CONSUME))return rangeReply(range.clone());
            check(id.equals(RecordingClient.RECORDING_PULL)&&pulled);
            if(waitForRangeRequest&&expectRange&&!legacy&&!busy&&device.end==0&&offset>=31600&&requests==0){
                try{check(requested.await(2,TimeUnit.SECONDS));}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
            }
            int n=Math.min(400,device.bytes.length-offset);boolean last=offset+n==device.bytes.length;int header=last?56:20;
            byte[] p=new byte[header+n];p[0]=1;p[1]=(byte)(last?1:8);put(p,2,n,2);put(p,4,device.d.recordingId,4);put(p,8,sequence++,4);put(p,12,offset,4);
            if(last){put(p,16,device.bytes.length,4);System.arraycopy(device.d.sha256(),0,p,24,32);}
            System.arraycopy(device.bytes,offset,p,header,n);CRC32 crc=new CRC32();crc.update(p,4,12);byte[] total=new byte[4];put(total,0,device.bytes.length,4);crc.update(total);crc.update(p,header,n);put(p,last?20:16,crc.getValue(),4);
            offset+=n;dataComplete=last;
            int limit=device.end==0?0:Math.min(device.bytes.length,(device.end*16-1)*248);
            if((requests>0&&offset>firstWriteOffset)||last)advanced.countDown();return p;
        }
    }
    static Path download(Link link,RecorderWire.Descriptor d,boolean consume)throws Exception {
        return download(link,d,consume,p->{});
    }
    static Path download(Link link,RecorderWire.Descriptor d,boolean consume,DurableConsume.DirectorySync sync)throws Exception {
        try(RecordingClient client=new RecordingClient(link,sync,prefix->{})){
            Field current=RecordingClient.class.getDeclaredField("current");current.setAccessible(true);current.set(client,Collections.singletonList(d));
            if(!consume)return client.download(d.recordingId,link.directory,null);
            Method method=RecordingClient.class.getDeclaredMethod("download",long.class,Path.class,RecordingClient.Progress.class,boolean.class);method.setAccessible(true);
            try{return (Path)method.invoke(client,d.recordingId,link.directory,null,true);}
            catch(InvocationTargetException e){throw (Exception)e.getCause();}
        }
    }
    public static void main(String[] args)throws Exception {
        for(int i=0;i<RangeCheckpointJvmTest.data.length;i++)RangeCheckpointJvmTest.data[i]=(byte)(i*37+13);
        byte[] data=new byte[63000];for(int i=0;i<data.length;i++)data[i]=(byte)(i*37+13);
        byte[] wire=RangeCheckpointJvmTest.descriptor().wireBytes();put(wire,48,data.length,4);
        put(wire,52,RecorderWire.crc(data,0,data.length),4);System.arraycopy(MessageDigest.getInstance("SHA-256").digest(data),0,wire,56,32);
        put(wire,108,RecorderWire.crc(wire,0,108),4);RecorderWire.Descriptor d=RecorderWire.Descriptor.decode(wire);
        for(int mode=0;mode<4;mode++){
            Path dir=Files.createTempDirectory("companion-range-client-");Device device=new Device(d,data);
            Link link=new Link(device,dir,mode==1,mode==2,false);link.expectRange=mode==0;Path file=download(link,d,mode!=3);
            check(Arrays.equals(Files.readAllBytes(file),data));
            if(mode==0){check(link.queries==1&&link.requests==1&&link.receipts==1&&device.end==8&&RangeCheckpoint.read(dir,d).confirmed);}
            else check(link.requests==0&&(!Files.exists(dir.resolve(SegmentReceiver.key(d)+".range"))));
        }
        Path dir=Files.createTempDirectory("companion-range-reconnect-");Device device=new Device(d,data);
        Link failed=new Link(device,dir,false,false,true);
        try{download(failed,d,true);throw new AssertionError("missing controlled disconnect");}
        catch(RecordingSyncRunner.LinkFailure expected){}
        check(failed.requests==1&&RangeCheckpoint.exists(dir,d)&&!RangeCheckpoint.read(dir,d).confirmed);
        Link resumed=new Link(device,dir,false,false,false);Path file=download(resumed,d,true);
        check(Arrays.equals(Files.readAllBytes(file),data)&&RangeCheckpoint.read(dir,d).confirmed&&device.end==8&&resumed.requests==0);
        // Fresh tails shorter than two physical blocks use one terminal whole
        // transaction, including the actual43442B field failure geometry.
        for(int bytes:new int[]{32000,40000,43442,59000}){
            byte[] medium=Arrays.copyOf(data,bytes),w=d.wireBytes();put(w,48,bytes,4);
            put(w,52,RecorderWire.crc(medium,0,bytes),4);System.arraycopy(MessageDigest.getInstance("SHA-256").digest(medium),0,w,56,32);
            put(w,108,RecorderWire.crc(w,0,108),4);RecorderWire.Descriptor md=RecorderWire.Descriptor.decode(w);
            Path mediumDir=Files.createTempDirectory("companion-short-two-block-");Device mediumDevice=new Device(md,medium);
            Link mediumLink=new Link(mediumDevice,mediumDir,false,false,false);mediumLink.expectRange=false;
            check(Arrays.equals(Files.readAllBytes(download(mediumLink,md,true)),medium)&&mediumLink.queries==0&&mediumLink.requests==0);
        }
        // Sub-block originals now hand off a prefix while receiving. Tiny
        // files and the previously measured8..15-sector whole path stay put.
        RecorderWire.Descriptor shortD=RangeCheckpointJvmTest.descriptor();byte[] shortData=RangeCheckpointJvmTest.data;
        Path shortDir=Files.createTempDirectory("companion-short-whole-");Device shortDevice=new Device(shortD,shortData);
        Link shortLink=new Link(shortDevice,shortDir,false,false,false);shortLink.waitForRangeRequest=false;
        check(Arrays.equals(Files.readAllBytes(download(shortLink,shortD,true)),shortData)&&shortLink.queries==1&&shortLink.requests>0&&shortLink.receipts==shortLink.requests);
        check(RangeCheckpoint.read(shortDir,shortD).confirmed&&shortDevice.end>0&&shortDevice.end<3);
        for(int bytes:new int[]{1530,5994}){
            byte[] tiny=Arrays.copyOf(data,bytes),w=d.wireBytes();put(w,48,bytes,4);
            put(w,52,RecorderWire.crc(tiny,0,bytes),4);System.arraycopy(MessageDigest.getInstance("SHA-256").digest(tiny),0,w,56,32);
            put(w,108,RecorderWire.crc(w,0,108),4);RecorderWire.Descriptor td=RecorderWire.Descriptor.decode(w);
            Path tinyDir=Files.createTempDirectory("companion-tiny-whole-");Link tinyLink=new Link(new Device(td,tiny),tinyDir,false,false,false);tinyLink.expectRange=false;
            check(Arrays.equals(Files.readAllBytes(download(tinyLink,td,true)),tiny)&&tinyLink.queries==0&&tinyLink.requests==0);
        }
        RecordingLibrary.Session checked=RecordingLibrary.sessions(shortDir,shortD).get(0);
        check(RecordingLibrary.verifiedPrefix(checked,shortD).segments.size()==1);
        Path shortFile=shortDir.resolve(SegmentReceiver.key(shortD)+".cop1");byte[] damaged=shortData.clone();damaged[0]^=1;Files.write(shortFile,damaged);
        try{RecordingLibrary.verifiedPrefix(RecordingLibrary.sessions(shortDir,shortD).get(0),shortD);throw new AssertionError("damaged inventory accepted");}catch(IOException expected){}
        Path oldDir=Files.createTempDirectory("companion-old-short-range-");Files.write(oldDir.resolve(SegmentReceiver.key(shortD)+".part"),shortData);
        try(SegmentReceiver receiver=new SegmentReceiver(oldDir,shortD)){receiver.checkpointRange(oldDir,0,1,99,p->{});}
        Device oldDevice=new Device(shortD,shortData);oldDevice.nonce=99;oldDevice.end=1;
        Link oldLink=new Link(oldDevice,oldDir,false,false,false);oldLink.expectRange=false;
        check(Arrays.equals(Files.readAllBytes(download(oldLink,shortD,true)),shortData)&&oldLink.queries==1&&oldLink.requests==0&&oldDevice.end==1);
        // A previously committed pending range is still settled even when
        // all local bytes already exist; final tail ownership stays with CRA2.
        Path pendingDir=Files.createTempDirectory("companion-old-pending-range-");Files.write(pendingDir.resolve(SegmentReceiver.key(shortD)+".part"),shortData);
        try(SegmentReceiver receiver=new SegmentReceiver(pendingDir,shortD)){receiver.checkpointRange(pendingDir,0,1,100,p->{});}
        Device pendingDevice=new Device(shortD,shortData);pendingDevice.nonce=100;pendingDevice.end=1;pendingDevice.pending=true;
        Link pendingLink=new Link(pendingDevice,pendingDir,false,false,false);pendingLink.expectRange=false;
        check(Arrays.equals(Files.readAllBytes(download(pendingLink,shortD,true)),shortData)&&pendingLink.requests==1&&pendingDevice.end==1&&!pendingDevice.pending);
        System.out.println("PASS_ACTUAL_CLIENT_RANGE_FLOW concurrent_audio_and_receipt=1 durable_source_before_request=1 exact_original_after_reconnect=1 lost_receipt_reconciled=1 legacy_busy_and_copy_only_paths_preserved=1 no_metric_start_or_byte_padding_changes=1");
    }
}
