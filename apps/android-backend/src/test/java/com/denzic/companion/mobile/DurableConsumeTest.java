package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.UUID;
import java.util.zip.CRC32;

/** Synthetic device receipts; never connects to a recording card. */
public final class DurableConsumeTest {
    private static void put16(byte[] p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
    private static void put32(byte[] p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    private interface Checked{void run()throws Exception;}
    private static void fails(Checked run)throws Exception{try{run.run();throw new AssertionError("operation should fail");}catch(IOException expected){}}
    private static final class FakeLink implements RecordingClient.Link {
        int writes;boolean loseReply,wrongReply;byte[] sent;boolean subscribed;
        public int mtu(){return 247;} public byte[] read(UUID id){throw new AssertionError();}
        public void subscribe(UUID id){check(id.equals(RecordingClient.RECORDING_CONSUME),"wrong subscription");subscribed=true;}
        public void write(UUID id,byte[] value){check(subscribed&&id.equals(RecordingClient.RECORDING_CONSUME),"wrong channel");writes++;sent=value.clone();}
        public byte[] await(UUID id,long timeout)throws IOException {
            if(loseReply)throw new IOException("synthetic lost reply");
            if(wrongReply){byte[] bad=sent.clone();bad[48]^=1;return bad;}
            return sent.clone();
        }
        public void close(){}
    }
    private static void save(Path directory,RecorderWire.Descriptor d,byte[] audio)throws IOException {
        Files.createDirectories(directory);String key=SegmentReceiver.key(d);
        Files.write(directory.resolve(key+".meta"),d.wireBytes());Files.write(directory.resolve(key+".cop1"),audio);
    }
    private static RecorderWire.Peer peer(byte[] d0)throws Exception {
        byte[] status=new byte[116];status[0]=1;put32(status,12,0x57424155L);System.arraycopy(d0,96,status,20,12);
        System.arraycopy(new byte[]{'C','R','V','2'},0,status,84,4);put16(status,88,2);put16(status,90,32);put32(status,92,7);
        System.arraycopy(d0,12,status,96,8);put16(status,104,64);put16(status,106,1024);put16(status,108,248);
        CRC32 crc=new CRC32();crc.update(status,84,28);put32(status,112,crc.getValue());return RecorderWire.Peer.fromStatus(status);
    }
    public static void main(String[] args)throws Exception {
        check(DurableConsume.receiptTimeoutMillis(270336)==15000,"ordinary segment budget changed");
        check(DurableConsume.receiptTimeoutMillis(16L*1024*1024)>200000,"large segment needs a longer physical receipt budget");
        Path fixture=Paths.get(args[0]);byte[] raw=Files.readAllBytes(fixture.resolve("payload.bin"));
        byte[] wire=Files.readAllBytes(fixture.resolve("descriptor0.bin"));RecorderWire.Peer peer=peer(wire);
        RecorderWire.Catalog catalog=new RecorderWire.Catalog(peer,17);
        catalog.accept(Files.readAllBytes(fixture.resolve("page0.bin")));catalog.accept(Files.readAllBytes(fixture.resolve("page1.bin")));
        RecorderWire.Descriptor first=catalog.entries().get(0),second=catalog.entries().get(1);
        Path directory=Files.createTempDirectory(fixture,"durable-consume-");FakeLink link=new FakeLink();
        int[] checks={0},syncs={0};DurableConsume.DirectorySync sync=d->{syncs[0]++;};
        DurableConsume.PrefixCheck prefix=s->{checks[0]++;check(s.segments.size()>0,"missing prefix");};
        DurableConsume consume=new DurableConsume(peer,link,sync,prefix);
        fails(()->consume.consume(directory,first));check(link.writes==0,"unsaved segment was consumed");
        save(directory,first,raw);link.loseReply=true;fails(()->consume.consume(directory,first));
        check(link.writes==1&&Files.isRegularFile(directory.resolve(".consume-pending")),"lost reply did not stay pending");
        byte[] otherWire=first.wireBytes();otherWire[20]^=1;
        CRC32 otherCrc=new CRC32();otherCrc.update(otherWire,0,108);put32(otherWire,108,otherCrc.getValue());
        RecorderWire.Descriptor other=RecorderWire.Descriptor.decode(otherWire);
        check(other.sessionId!=first.sessionId,"fixture must select a different session");
        link.loseReply=false;int beforeOther=link.writes;
        fails(()->consume.consume(directory,other));
        fails(()->consume.reconcilePending(directory,other));
        check(link.writes==beforeOther&&Files.isRegularFile(directory.resolve(".consume-pending")),"another session unexpectedly reconciled the old pending receipt");
        link.loseReply=true;
        byte[] original=link.sent.clone();save(directory,second,raw);
        fails(()->consume.consume(directory,second));check(link.writes==2&&Arrays.equals(original,link.sent),"later segment overtook unconfirmed receipt");
        link.loseReply=false;DurableConsume restarted=new DurableConsume(peer,link,sync,prefix);
        check(RecordingLibrary.pendingConfirmation(directory).sameContent(first),"pending selection unavailable to host");
        check(restarted.reconcilePending(directory,first),"pending receipt was not resumed");
        check(Arrays.equals(original,link.sent)&&!Files.exists(directory.resolve(".consume-pending")),"wrong receipt reconciled");
        check(RecordingLibrary.pendingConfirmation(directory)==null,"completed confirmation still shown as pending");
        check(!restarted.consume(directory,first),"confirmed segment was consumed twice");
        check(restarted.consume(directory,second),"next saved segment was not consumed");
        check(link.writes==4&&checks[0]>=4&&syncs[0]>=8,"durability or ordered validation skipped");
        Path corrupt=Files.createTempDirectory(fixture,"durable-corrupt-");save(corrupt,first,raw);
        Path body=corrupt.resolve(SegmentReceiver.key(first)+".cop1");byte[] changed=raw.clone();changed[0]^=1;Files.write(body,changed);
        int before=link.writes;fails(()->restarted.consume(corrupt,first));check(link.writes==before,"damaged audio was consumed");
        Path failure=Files.createTempDirectory(fixture,"durable-sync-failure-");save(failure,first,raw);
        DurableConsume broken=new DurableConsume(peer,link,d->{throw new IOException("synthetic fsync failure");},prefix);
        fails(()->broken.consume(failure,first));check(link.writes==before&&!Files.exists(failure.resolve(".consume-pending")),"failed durability still sent a receipt");
        Path invalidAudio=Files.createTempDirectory(fixture,"durable-invalid-audio-");save(invalidAudio,first,raw);
        DurableConsume badPrefix=new DurableConsume(peer,link,sync,s->{throw new IOException("invalid COP1 or bookmark timeline");});
        fails(()->badPrefix.consume(invalidAudio,first));check(link.writes==before,"invalid audio structure was consumed");
        Path ackDisk=Files.createTempDirectory(fixture,"durable-confirm-sync-");save(ackDisk,first,raw);int[] count={0};
        DurableConsume failedAfterReply=new DurableConsume(peer,link,d->{if(++count[0]==4)throw new IOException("confirmation directory sync failed");},prefix);
        fails(()->failedAfterReply.consume(ackDisk,first));check(link.writes==before+1&&Files.isRegularFile(ackDisk.resolve(".consume-pending")),"failed confirmation save lost pending state");
        check(restarted.reconcilePending(ackDisk,first),"saved confirmation did not recover");
        check(link.writes==before+1&&!Files.exists(ackDisk.resolve(".consume-pending")),"recovery repeated a confirmed device receipt");
        Path deferred=Files.createTempDirectory(fixture,"durable-deferred-");save(deferred,first,raw);save(deferred,other,raw);
        FakeLink deferredLink=new FakeLink();deferredLink.loseReply=true;DurableConsume deferredClient=new DurableConsume(peer,deferredLink,sync,prefix);
        fails(()->deferredClient.consume(deferred,first));int unresolvedWrites=deferredLink.writes;
        fails(()->DurableConsume.deferUnreadable(deferred,sync));
        check(Files.isRegularFile(deferred.resolve(".consume-pending")),"valid pending record was misclassified as unreadable");
        fails(()->deferredClient.consume(deferred,other));
        check(deferredLink.writes==unresolvedWrites,"other session sent a pending receipt");
        fails(()->DurableConsume.defer(deferred,other,sync));
        String token=DurableConsume.defer(deferred,first,sync);
        check(!Files.exists(deferred.resolve(".consume-pending"))&&deferredLink.writes==unresolvedWrites,"defer touched device or retained active pending");
        check(RecordingLibrary.deferredConfirmations(deferred).size()==1&&RecordingLibrary.deferredConfirmations(deferred).get(0).descriptor.sameContent(first),"deferred receipt was not discoverable");
        check(RecordingLibrary.verifiedPrefix(deferred,first).segments.size()==1,"defer lost original audio");
        deferredLink.loseReply=false;check(deferredClient.consume(deferred,other),"another recording could not proceed after explicit defer");
        check(RecordingLibrary.verifiedPrefix(deferred,other).segments.size()==1,"new recording was not retained");
        int afterOther=deferredLink.writes;DurableConsume.restore(deferred,token,first,sync);
        check(deferredLink.writes==afterOther&&RecordingLibrary.deferredConfirmations(deferred).isEmpty(),"restore touched device or failed to move receipt");
        check(deferredClient.reconcilePending(deferred,first),"restored pending receipt could not be retried");
        // A damaged old local copy must not make every other recording
        // permanently unsynchronizable. Deferral is a local rename, not ACK.
        Path damagedDeferred=Files.createTempDirectory(fixture,"damaged-deferred-");
        save(damagedDeferred,first,raw);save(damagedDeferred,other,raw);
        FakeLink damagedLink=new FakeLink();damagedLink.loseReply=true;
        DurableConsume damagedClient=new DurableConsume(peer,damagedLink,sync,prefix);
        fails(()->damagedClient.consume(damagedDeferred,first));int beforeDefer=damagedLink.writes;
        Path damagedBody=damagedDeferred.resolve(SegmentReceiver.key(first)+".cop1");
        Files.write(damagedBody,changed);
        String damagedToken=DurableConsume.defer(damagedDeferred,first,sync);
        check(damagedLink.writes==beforeDefer&&!Files.exists(damagedDeferred.resolve(".consume-pending")),"deferring damaged old copy sent a device receipt");
        check(Arrays.equals(Files.readAllBytes(damagedBody),changed),"deferring damaged old copy changed it");
        damagedLink.loseReply=false;
        check(damagedClient.consume(damagedDeferred,other),"damaged prior recording blocked a different recording");
        int afterNew=damagedLink.writes;
        fails(()->DurableConsume.restore(damagedDeferred,damagedToken,first,sync));
        check(damagedLink.writes==afterNew&&RecordingLibrary.deferredConfirmations(damagedDeferred).size()==1,"bad old copy was restored or consumed");
        Files.write(damagedBody,raw);DurableConsume.restore(damagedDeferred,damagedToken,first,sync);
        check(damagedClient.reconcilePending(damagedDeferred,first),"repaired original could not retry its exact receipt");
        Path missingDeferred=Files.createTempDirectory(fixture,"missing-deferred-");
        save(missingDeferred,first,raw);save(missingDeferred,other,raw);
        FakeLink missingLink=new FakeLink();missingLink.loseReply=true;
        DurableConsume missingClient=new DurableConsume(peer,missingLink,sync,prefix);
        fails(()->missingClient.consume(missingDeferred,first));int missingBefore=missingLink.writes;
        Files.delete(missingDeferred.resolve(SegmentReceiver.key(first)+".cop1"));
        String missingToken=DurableConsume.defer(missingDeferred,first,sync);
        check(missingLink.writes==missingBefore,"deferring absent copy sent a device receipt");
        missingLink.loseReply=false;
        check(missingClient.consume(missingDeferred,other),"absent old local recording blocked another recording");
        int missingAfter=missingLink.writes;
        fails(()->DurableConsume.restore(missingDeferred,missingToken,first,sync));
        check(missingLink.writes==missingAfter&&RecordingLibrary.deferredConfirmations(missingDeferred).size()==1,"missing old copy was restored or consumed");
        Path unreadable=Files.createTempDirectory(fixture,"unreadable-deferred-");save(unreadable,other,raw);
        byte[] unreadableBytes={1,2,3,4};Files.write(unreadable.resolve(".consume-pending"),unreadableBytes);
        fails(()->RecordingLibrary.pendingConfirmation(unreadable));
        FakeLink unreadableLink=new FakeLink();DurableConsume unreadableClient=new DurableConsume(peer,unreadableLink,sync,prefix);
        fails(()->unreadableClient.consume(unreadable,other));check(unreadableLink.writes==0,"invalid pending was sent to device");
        String unreadableToken=DurableConsume.deferUnreadable(unreadable,sync);
        check(!Files.exists(unreadable.resolve(".consume-pending"))&&Arrays.equals(unreadableBytes,Files.readAllBytes(unreadable.resolve(unreadableToken))),"unreadable bytes were not preserved");
        check(RecordingLibrary.unreadableConfirmations(unreadable).equals(java.util.Collections.singletonList(unreadableToken)),"unreadable record was not discoverable after reopen");
        check(unreadableClient.consume(unreadable,other)&&unreadableLink.writes==1,"unreadable old record blocked another recording");
        Path badCrc=Files.createTempDirectory(fixture,"bad-crc-deferred-");byte[] corruptWire=first.wireBytes();corruptWire[40]^=1;
        Files.write(badCrc.resolve(".consume-pending"),corruptWire);String badCrcToken=DurableConsume.deferUnreadable(badCrc,sync);
        check(Arrays.equals(corruptWire,Files.readAllBytes(badCrc.resolve(badCrcToken))),"CRC-damaged pending bytes were not retained");
        Path forged=Files.createTempDirectory(fixture,"durable-forged-");save(forged,first,raw);link.wrongReply=true;
        fails(()->restarted.consume(forged,first));check(Files.isRegularFile(forged.resolve(".consume-pending")),"invalid reply was accepted");
        System.out.println("PASS durable segment receipt, loss recovery, exact identity and local data preservation");
    }
}
