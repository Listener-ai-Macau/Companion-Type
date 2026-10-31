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
        byte[] original=link.sent.clone();save(directory,second,raw);
        fails(()->consume.consume(directory,second));check(link.writes==2&&Arrays.equals(original,link.sent),"later segment overtook unconfirmed receipt");
        link.loseReply=false;DurableConsume restarted=new DurableConsume(peer,link,sync,prefix);
        check(restarted.reconcilePending(directory),"pending receipt was not resumed");
        check(Arrays.equals(original,link.sent)&&!Files.exists(directory.resolve(".consume-pending")),"wrong receipt reconciled");
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
        check(restarted.reconcilePending(ackDisk),"saved confirmation did not recover");
        check(link.writes==before+1&&!Files.exists(ackDisk.resolve(".consume-pending")),"recovery repeated a confirmed device receipt");
        Path forged=Files.createTempDirectory(fixture,"durable-forged-");save(forged,first,raw);link.wrongReply=true;
        fails(()->restarted.consume(forged,first));check(Files.isRegularFile(forged.resolve(".consume-pending")),"invalid reply was accepted");
        System.out.println("PASS durable segment receipt, loss recovery, exact identity and local data preservation");
    }
}
