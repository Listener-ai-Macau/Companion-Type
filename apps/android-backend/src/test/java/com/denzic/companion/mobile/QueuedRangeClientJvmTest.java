package com.denzic.companion.mobile;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.zip.CRC32;

/** Production client/receiver/filesystem with a deterministic queued-device
 * model. Latches establish execution order; no simulated time counts as BLE,
 * physical erase speed, acoustic integrity, or production durability approval. */
public final class QueuedRangeClientJvmTest {
    static void check(boolean value){if(!value)throw new AssertionError();}
    static void put(byte[] p,int at,long value,int bytes){RangeConsumeClientJvmTest.put(p,at,value,bytes);}
    static int word(byte[] p,int at){return(p[at]&255)|((p[at+1]&255)<<8);}
    static final class Device {
        final byte[] data;final RecorderWire.Descriptor d;
        long token;int first,end,erased;boolean pending,complete;
        Device(int bytes)throws Exception {data=new byte[bytes];for(int i=0;i<bytes;i++)data[i]=(byte)(i*37+13);d=RangeCheckpointOverlapJvmTest.descriptor(data);}
    }
    static final class Link implements RecordingClient.Link {
        final Device device;final Path dir;final boolean queueEnabled,loseFirstReply;
        final LinkedBlockingQueue<byte[]> commands=new LinkedBlockingQueue<>(),notifications=new LinkedBlockingQueue<>();
        final CountDownLatch terminal=new CountDownLatch(1),failed=new CountDownLatch(1),dataComplete=new CountDownLatch(1),firstRange=new CountDownLatch(1);
        final Thread worker;volatile boolean closed,terminalBeforeFirstReceipt;volatile int requests,wholeRequests,queries,rangeReceipts,offset,sequence,acceptedEnd;
        byte[] control,catalogue;boolean dropDuringData,pendingOnly;
        Link(Device device,Path dir,boolean queueEnabled,boolean loseFirstReply){
            this.device=device;this.dir=dir;this.queueEnabled=queueEnabled;this.loseFirstReply=loseFirstReply;acceptedEnd=device.end;
            worker=new Thread(this::physical,"controlled-physical-range-model");worker.setDaemon(true);worker.start();
        }
        public int mtu(){return 512;}
        public void subscribe(UUID id){}
        public boolean preferBulkTransfer(boolean active){return true;}
        public byte[] read(UUID id){
            byte[] status=new RangeConsumeClientJvmTest.Link(new RangeConsumeClientJvmTest.Device(device.d,device.data),dir,false,false,false).read(id);
            put(status,4,66757,4);return status;
        }
        public synchronized void write(UUID id,byte[] wire)throws IOException {
            if(closed)throw new RecordingSyncRunner.LinkFailure("controlled link closed");
            if(id.equals(RecordingClient.RECORDING_CONTROL)){
                if(wire.length==16&&wire[1]==0x20){
                    int stride=(wire[2]&1)!=0?116:112,count=device.complete?0:1;
                    catalogue=new byte[24+stride*count];catalogue[0]=2;catalogue[1]=(byte)count;put(catalogue,2,stride,2);put(catalogue,4,1,4);put(catalogue,12,count,4);put(catalogue,16,RecorderWire.u32(wire,8),4);
                    if(count!=0)System.arraycopy(device.d.metadataBytes(),0,catalogue,24,112);
                    CRC32 crc=new CRC32();crc.update(catalogue,0,20);crc.update(catalogue,24,catalogue.length-24);put(catalogue,20,crc.getValue(),4);return;
                }
                control=wire.clone();if(!queueEnabled){control[3]&=(byte)0xdf;put(control,28,RecorderWire.crc(control,0,28),4);}return;
            }
            if(id.equals(RecordingClient.RECORDING_PULL)){
                offset=(int)RecorderWire.u32(wire,28);sequence=0;
                int missing=device.pending?device.first:device.end;check(offset>=Math.min(device.data.length,Math.max(0,(missing*16-1)*248)));return;
            }
            check(id.equals(RecordingClient.RECORDING_CONSUME));
            if(wire.length==96){
                check(RecorderWire.magic(wire,0,"CRG3")&&RecorderWire.crc(wire,0,92)==RecorderWire.u32(wire,92));
                if(wire[88]==0){queries++;notifications.add(reply(wire,device.token,device.first,device.end,device.pending));return;}
                RangeCheckpoint proof=null;for(RangeCheckpoint saved:RangeCheckpoint.queued(dir,device.d))if(saved.nonce==RecorderWire.u32(wire,44))proof=saved;
                check(proof!=null&&proof.firstSector==word(wire,48)&&proof.endSector==word(wire,50));
                byte[] local=Files.readAllBytes(source());int begin=proof.firstSector==0?0:(proof.firstSector*16-1)*248,limit=Math.min(device.data.length,(proof.endSector*16-1)*248);
                check(local.length>=limit&&Arrays.equals(Arrays.copyOf(local,limit),Arrays.copyOf(device.data,limit)));
                try{check(Arrays.equals(MessageDigest.getInstance("SHA-256").digest(Arrays.copyOfRange(device.data,begin,limit)),Arrays.copyOfRange(wire,56,88)));}
                catch(java.security.NoSuchAlgorithmException impossible){throw new AssertionError(impossible);}
                boolean replay=device.pending&&device.token==proof.nonce&&device.first==proof.firstSector&&device.end==proof.endSector;
                check(replay||proof.firstSector==acceptedEnd);acceptedEnd=proof.endSector;requests++;
                if(commands.isEmpty()&&requests==1){device.token=proof.nonce;device.first=proof.firstSector;device.end=proof.endSector;device.pending=true;}
                commands.add(wire.clone());firstRange.countDown();return;
            }
            check(wire.length==84&&RecorderWire.magic(wire,0,"CRA2")&&RecorderWire.crc(wire,0,80)==RecorderWire.u32(wire,80));
            check(Files.exists(dir.resolve(".consume-pending"))&&Files.exists(dir.resolve(SegmentReceiver.key(device.d)+".cop1")));
            check(Arrays.equals(Files.readAllBytes(source()),device.data));
            if(requests>0){
                try(SegmentReceiver second=new SegmentReceiver(dir,device.d)){throw new AssertionError("receiver owner released before terminal handoff");}
                catch(IOException held){}
            }
            wholeRequests++;terminalBeforeFirstReceipt=requests>0&&rangeReceipts==0;commands.add(wire.clone());terminal.countDown();
        }
        private Path source(){Path ready=dir.resolve(SegmentReceiver.key(device.d)+".cop1");return Files.exists(ready)?ready:dir.resolve(SegmentReceiver.key(device.d)+".part");}
        private byte[] reply(byte[] request,long token,int first,int end,boolean pending){
            byte[] p=new byte[60];System.arraycopy(new byte[]{'C','R','R','3',3,0,60,0},0,p,0,8);
            System.arraycopy(device.d.uid(),0,p,8,12);put(p,20,device.d.epoch,8);put(p,28,device.d.recordingId,4);
            put(p,32,RecorderWire.u32(request,44),4);put(p,36,token,4);put(p,40,first,2);put(p,42,end,2);p[48]=(byte)(pending?1:0);
            put(p,52,RangeConsume.binding(device.d),4);put(p,56,RecorderWire.crc(p,0,56),4);return p;
        }
        private void physical(){
            try{
                check(terminal.await(4,TimeUnit.SECONDS));
                while(!closed){
                    byte[] request=commands.poll(4,TimeUnit.SECONDS);if(request==null)return;
                    if(request.length==84){
                        int used=(int)((((device.data.length+247L)/248+1)*256+4095)/4096);
                        device.erased+=used-device.end;device.complete=true;device.pending=false;notifications.add(request);return;
                    }
                    int first=word(request,48),end=word(request,50);device.first=first;device.end=end;device.token=RecorderWire.u32(request,44);device.pending=false;device.erased+=end-first;
                    if(loseFirstReply){failed.countDown();return;}
                    rangeReceipts++;notifications.add(reply(request,device.token,first,end,false));
                }
            }catch(InterruptedException expected){Thread.currentThread().interrupt();}
        }
        public byte[] await(UUID id,long timeout)throws IOException {
            if(id.equals(RecordingClient.RECORDING_CONTROL))return control.clone();
            if(id.equals(RecordingClient.RECORDING_LIST))return catalogue.clone();
            if(id.equals(RecordingClient.RECORDING_CONSUME)){
                try{
                    while(!closed){
                        if(failed.getCount()==0)throw new RecordingSyncRunner.LinkFailure("controlled loss after first physical commit");
                        byte[] p=notifications.poll(20,TimeUnit.MILLISECONDS);if(p!=null)return p;
                    }
                    throw new RecordingSyncRunner.LinkFailure("controlled link closed");
                }catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
            }
            check(id.equals(RecordingClient.RECORDING_PULL));
            if(dropDuringData&&offset>=8000){
                try{check(firstRange.await(2,TimeUnit.SECONDS));}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
                if(!pendingOnly){device.pending=false;device.erased+=device.end-device.first;}failed.countDown();
                throw new RecordingSyncRunner.LinkFailure("controlled loss with partial original and a committed physical prefix");
            }
            int n=Math.min(400,device.data.length-offset);boolean last=offset+n==device.data.length;int header=last?56:20;
            byte[] p=new byte[header+n];p[0]=1;p[1]=(byte)(last?1:8);put(p,2,n,2);put(p,4,device.d.recordingId,4);put(p,8,sequence++,4);put(p,12,offset,4);
            if(last){put(p,16,device.data.length,4);System.arraycopy(device.d.sha256(),0,p,24,32);}
            System.arraycopy(device.data,offset,p,header,n);CRC32 crc=new CRC32();crc.update(p,4,12);byte[] size=new byte[4];put(size,0,device.data.length,4);crc.update(size);crc.update(p,header,n);put(p,last?20:16,crc.getValue(),4);
            offset+=n;if(last)dataComplete.countDown();return p;
        }
        public void close(){closed=true;worker.interrupt();try{worker.join(2000);}catch(InterruptedException e){Thread.currentThread().interrupt();}check(!worker.isAlive());}
    }
    static RecordingLibrary.Session sync(Link link,DurableConsume.DirectorySync disk)throws Exception {
        try(RecordingClient client=new RecordingClient(link,disk,prefix->{})){
            for(String name:new String[]{"current","handedOffSelection","useHandedOffCatalogue","catalogueReusable"}){
                Field f=RecordingClient.class.getDeclaredField(name);f.setAccessible(true);f.set(client,name.equals("current")?Collections.singletonList(link.device.d):name.equals("handedOffSelection")?link.device.d:Boolean.TRUE);
            }
            return client.syncAvailableAndReclaim(link.device.d,link.dir,null);
        }
    }
    static void exact(Link link)throws Exception {
        RecordingLibrary.Session result=sync(link,p->{});check(result.state==RecordingLibrary.SessionState.COMPLETE&&link.device.complete&&link.wholeRequests==1);
        check(Arrays.equals(Files.readAllBytes(result.segments.get(0).file),link.device.data));
        check(RangeCheckpoint.queued(link.dir,link.device.d).isEmpty());
    }
    public static void main(String[] args)throws Exception {
        java.lang.reflect.Method hex=SegmentReceiver.class.getDeclaredMethod("hex",byte[].class);hex.setAccessible(true);
        byte[] octets=new byte[256];StringBuilder canonical=new StringBuilder();for(int i=0;i<256;i++){octets[i]=(byte)i;canonical.append(String.format(java.util.Locale.ROOT,"%02x",i));}
        check(canonical.toString().equals(hex.invoke(null,(Object)octets)));
        for(int bytes:new int[]{1530,5994,22610,43442,59000})for(boolean queue:new boolean[]{true,false}){
            Device device=new Device(bytes);Link link=new Link(device,Files.createTempDirectory("queued-range-client-"),queue,false);exact(link);
            if(queue&&bytes>=5994)check(link.requests>0&&link.terminalBeforeFirstReceipt);
            if(!queue)check(link.requests==0&&link.queries==0);
        }
        Device interrupted=new Device(22610);Path dir=Files.createTempDirectory("queued-range-lost-receipt-");Link lost=new Link(interrupted,dir,true,true);
        try{sync(lost,p->{});throw new AssertionError("missing injected lost receipt");}catch(RecordingSyncRunner.LinkFailure expected){}
        check(!interrupted.complete&&interrupted.end>0&&!RangeCheckpoint.queued(dir,interrupted.d).isEmpty());
        try(java.nio.file.DirectoryStream<Path> obsolete=Files.newDirectoryStream(dir,SegmentReceiver.key(interrupted.d)+".queued-*")){
            for(Path proof:obsolete){Files.write(proof,new byte[]{1});break;}
        }
        Link resumed=new Link(interrupted,dir,true,false);exact(resumed);
        for(boolean pending:new boolean[]{false,true}){
            Device partial=new Device(22610);Path partialDir=Files.createTempDirectory("queued-range-partial-recovery-");Link partialLink=new Link(partial,partialDir,true,false);partialLink.dropDuringData=true;partialLink.pendingOnly=pending;
            try{sync(partialLink,p->{});throw new AssertionError("missing partial-source disconnect");}catch(RecordingSyncRunner.LinkFailure expected){}
            check(!Files.exists(partialDir.resolve(".consume-pending"))&&!partial.complete&&(pending?partial.pending:partial.erased>0));
            byte[] original=Files.readAllBytes(partialDir.resolve(SegmentReceiver.key(partial.d)+".part"));byte[] corrupt=original.clone();corrupt[0]^=1;Files.write(partialDir.resolve(SegmentReceiver.key(partial.d)+".part"),corrupt);
            Link damaged=new Link(partial,partialDir,true,false);try{sync(damaged,p->{});throw new AssertionError("damaged saved prefix accepted");}catch(IOException expected){check(damaged.requests==0&&damaged.queries==0);}
            Files.write(partialDir.resolve(SegmentReceiver.key(partial.d)+".part"),original);
            Link partialResume=new Link(partial,partialDir,true,false);exact(partialResume);
        }
        Device failedDevice=new Device(22610);Path failedDir=Files.createTempDirectory("queued-range-disk-fail-");Link failedLink=new Link(failedDevice,failedDir,true,false);
        AtomicBoolean fail=new AtomicBoolean(true);
        try{sync(failedLink,p->{if(fail.compareAndSet(true,false))throw new IOException("controlled source directory sync failure");});throw new AssertionError("missing injected disk failure");}
        catch(IOException expected){check(expected.getMessage().contains("controlled"));}
        check(failedLink.requests==0&&failedDevice.erased==0&&Files.exists(failedDir.resolve(SegmentReceiver.key(failedDevice.d)+".part")));
        Link retry=new Link(failedDevice,failedDir,true,false);exact(retry);
        Device secondDevice=new Device(22610);Path secondDir=Files.createTempDirectory("queued-range-second-proof-fail-");Link secondLink=new Link(secondDevice,secondDir,true,false);AtomicBoolean secondFail=new AtomicBoolean(true);
        try{sync(secondLink,p->{if(RangeCheckpoint.queued(secondDir,secondDevice.d).size()>=2&&secondFail.compareAndSet(true,false))throw new IOException("controlled second proof publication sync failure");});throw new AssertionError("second proof barrier not reached");}
        catch(IOException expected){check(expected.getMessage().contains("controlled second"));}
        check(secondLink.requests>0&&secondLink.wholeRequests==0&&!RangeCheckpoint.queued(secondDir,secondDevice.d).isEmpty());
        Link secondRetry=new Link(secondDevice,secondDir,true,false);exact(secondRetry);
        Device cancelledDevice=new Device(22610);Path cancelledDir=Files.createTempDirectory("queued-range-cancel-");Link cancelledLink=new Link(cancelledDevice,cancelledDir,true,false);
        CountDownLatch diskEntered=new CountDownLatch(1),diskReleased=new CountDownLatch(1),receiverDone=new CountDownLatch(1);AtomicBoolean once=new AtomicBoolean(true);AtomicReference<Throwable> error=new AtomicReference<>();
        Thread receiver=new Thread(()->{
            try{sync(cancelledLink,p->{if(once.compareAndSet(true,false)){
                diskEntered.countDown();boolean wasInterrupted=false;while(true)try{diskReleased.await();break;}catch(InterruptedException e){wasInterrupted=true;}
                if(wasInterrupted)Thread.currentThread().interrupt();
            }});}catch(Throwable caught){error.set(caught);}finally{receiverDone.countDown();}
        });receiver.start();check(diskEntered.await(2,TimeUnit.SECONDS));check(cancelledLink.dataComplete.await(2,TimeUnit.SECONDS));receiver.interrupt();
        try(SegmentReceiver next=new SegmentReceiver(cancelledDir,cancelledDevice.d)){throw new AssertionError("owner released during in-flight fsync");}catch(IOException expected){}
        check(cancelledLink.requests==0);diskReleased.countDown();check(receiverDone.await(3,TimeUnit.SECONDS));receiver.join();check(error.get() instanceof IOException&&cancelledLink.requests==0);
        System.out.println("PASS production queued sync: terminal durably submitted before first physical receipt; exact originals and old-device fallback; independent immutable proofs, bounded workers, retained receiver lock; lost physical reply resumes exact queued frontier; disk failure sends no destructive request. Hardware speed NOT_EVALUATED.");
    }
}
