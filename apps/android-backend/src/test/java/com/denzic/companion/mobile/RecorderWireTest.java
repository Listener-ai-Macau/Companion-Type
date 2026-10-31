package com.denzic.companion.mobile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.UUID;
import java.util.zip.CRC32;

/** Runs against the existing Windows/firmware synthetic V2 golden vectors. */
public final class RecorderWireTest {
    private static void put16(byte[] p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
    private static void put32(byte[] p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static byte[] packet(RecorderWire.Descriptor d,byte[] audio,int start,int length,boolean last){
        int header=last?56:24;byte[] p=new byte[header+length];p[0]=1;p[1]=(byte)(last?1:0);put16(p,2,length);put32(p,4,d.recordingId);put32(p,8,0);put32(p,12,start);put32(p,16,audio.length);if(last)System.arraycopy(d.sha256(),0,p,24,32);System.arraycopy(audio,start,p,header,length);CRC32 c=new CRC32();c.update(p,4,16);c.update(p,header,length);put32(p,20,c.getValue());return p;
    }
    private static void expectFailure(Checked c)throws Exception{try{c.run();throw new AssertionError("corrupt data was accepted");}catch(java.io.IOException expected){}}
    private interface Checked{void run()throws Exception;}
    private static final class FakeLink implements RecordingClient.Link {
        final byte[] status,page0,page1,packet;byte[] control,list,pull,resumedPacket,multiAudio;boolean closed,partialOnce,failOnNextPull;int pullCount;
        final java.util.Map<Long,RecorderWire.Descriptor> segments=new java.util.HashMap<>();
        FakeLink(byte[] s,byte[] a,byte[] b,byte[] p){status=s;page0=a;page1=b;packet=p;}
        public int mtu(){return 247;} public byte[] read(UUID id){return status.clone();}
        public void subscribe(UUID id){} public void close(){closed=true;}
        public void write(UUID id,byte[] value){
            if(id.equals(RecordingClient.RECORDING_CONTROL) && value[1]==0x22) control=value.clone();
            else if(id.equals(RecordingClient.RECORDING_CONTROL) && value[1]==0x20){list=(value[12]==0?page0:page1).clone();System.arraycopy(value,8,list,16,4);CRC32 crc=new CRC32();crc.update(list,0,20);crc.update(list,24,list.length-24);put32(list,20,crc.getValue());}
            else if(id.equals(RecordingClient.RECORDING_PULL)){if(value[2]!=4)throw new AssertionError("pull must stream the whole segment");pullCount++;
                if(multiAudio!=null){long recording=0,offset=0;for(int i=0;i<4;i++){recording|=(value[4+i]&255L)<<(8*i);offset|=(value[28+i]&255L)<<(8*i);}
                    RecorderWire.Descriptor d=segments.get(recording);if(d==null)throw new AssertionError("unknown requested segment");
                    if(partialOnce){partialOnce=false;failOnNextPull=true;pull=packet(d,multiAudio,0,7,false);}else pull=packet(d,multiAudio,(int)offset,multiAudio.length-(int)offset,true);
                }else pull=(value[28]==7&&resumedPacket!=null?resumedPacket:packet).clone();
            }else throw new AssertionError("unexpected command");
        }
        public byte[] await(UUID id,long timeout)throws java.io.IOException {if(id.equals(RecordingClient.RECORDING_CONTROL))return control;if(id.equals(RecordingClient.RECORDING_LIST))return list;if(id.equals(RecordingClient.RECORDING_PULL)){
            if(pull==null&&failOnNextPull){failOnNextPull=false;throw new java.io.IOException("synthetic disconnect");}byte[] result=pull;if(failOnNextPull)pull=null;return result;}
            throw new AssertionError("unexpected notification");}
    }
    public static void main(String[] args)throws Exception {
        Path root=Paths.get(args[0]);byte[] d0=Files.readAllBytes(root.resolve("descriptor0.bin"));byte[] page0=Files.readAllBytes(root.resolve("page0.bin"));byte[] page1=Files.readAllBytes(root.resolve("page1.bin"));byte[] audio=Files.readAllBytes(root.resolve("payload.bin"));
        byte[] status=new byte[116];status[0]=1;put32(status,12,0x57424155L);System.arraycopy(d0,96,status,20,12);System.arraycopy(new byte[]{'C','R','V','2'},0,status,84,4);put16(status,88,2);put16(status,90,32);put32(status,92,7);System.arraycopy(d0,12,status,96,8);put16(status,104,64);put16(status,106,1024);put16(status,108,248);CRC32 statusCrc=new CRC32();statusCrc.update(status,84,28);put32(status,112,statusCrc.getValue());
        RecorderWire.Peer peer=RecorderWire.Peer.fromStatus(status);byte[] negotiation=peer.negotiate(23,247);if(negotiation.length!=32||negotiation[1]!=0x22)throw new AssertionError("negotiation");
        RecorderWire.Catalog catalog=new RecorderWire.Catalog(peer,17);if(!catalog.accept(page0)||catalog.complete()||catalog.accept(page0)||!catalog.accept(page1)||!catalog.complete())throw new AssertionError("golden directory or duplicate page");
        if(catalog.entries().size()!=3)throw new AssertionError("missing segments");RecorderWire.Descriptor d=catalog.entries().get(0);if(d.recordingId!=41||d.segmentIndex!=0||d.encodedLength!=audio.length)throw new AssertionError("golden descriptor");
        byte[] receipt=peer.consumeReceipt(d), expected=new byte[84];
        System.arraycopy(new byte[]{'C','R','A','2',2,0,84,0},0,expected,0,8);System.arraycopy(d0,96,expected,8,12);
        System.arraycopy(d0,12,expected,20,8);System.arraycopy(d0,20,expected,28,8);System.arraycopy(d0,28,expected,36,4);
        System.arraycopy(d0,8,expected,40,4);System.arraycopy(d0,48,expected,44,4);System.arraycopy(d0,56,expected,48,32);
        CRC32 receiptCrc=new CRC32();receiptCrc.update(expected,0,80);put32(expected,80,receiptCrc.getValue());
        if(!Arrays.equals(receipt,expected)||!peer.receiptMatches(d,receipt))throw new AssertionError("exact protected receipt differs");
        if(peer.receiptMatches(d,peer.consumeReceipt(catalog.entries().get(1)))||peer.receiptMatches(d,null))throw new AssertionError("another receipt confirmed the original");
        byte[] forged=receipt.clone();forged[48]^=1;expectFailure(()->peer.receiptMatches(d,forged));
        byte[] foreign=status.clone();foreign[20]^=1;statusCrc.reset();statusCrc.update(foreign,84,28);put32(foreign,112,statusCrc.getValue());
        RecorderWire.Peer other=RecorderWire.Peer.fromStatus(foreign);expectFailure(()->other.consumeReceipt(d));
        Path whole=Files.createTempDirectory(root,"whole-session-");FakeLink firstLink=new FakeLink(status,page0,page1,null);firstLink.multiAudio=audio;firstLink.partialOnce=true;
        for(RecorderWire.Descriptor item:catalog.entries())firstLink.segments.put(item.recordingId,item);
        try(RecordingClient client=new RecordingClient(firstLink)){expectFailure(()->client.receiveSession(d,whole,null));}
        if(RecordingLibrary.list(whole).stream().noneMatch(e->e.state==RecordingLibrary.State.PARTIAL))throw new AssertionError("interrupted session must retain partial audio");
        FakeLink secondLink=new FakeLink(status,page0,page1,null);secondLink.multiAudio=audio;for(RecorderWire.Descriptor item:catalog.entries())secondLink.segments.put(item.recordingId,item);
        try(RecordingClient client=new RecordingClient(secondLink)){
            RecordingLibrary.Session received=client.receiveSession(d,whole,null);if(received.state!=RecordingLibrary.SessionState.COMPLETE||received.segments.size()!=3||secondLink.pullCount!=3)throw new AssertionError("whole session did not resume");
            client.receiveSession(d,whole,null);if(secondLink.pullCount!=3)throw new AssertionError("verified session retransmitted");
            byte[] changed=d.wireBytes();changed[94]=2;CRC32 changedCrc=new CRC32();changedCrc.update(changed,0,108);put32(changed,108,changedCrc.getValue());
            expectFailure(()->client.receiveSession(RecorderWire.Descriptor.decode(changed),whole,null));if(secondLink.pullCount!=3)throw new AssertionError("conflicting identity started transfer");
        }
        byte[] shorter=page0.clone();put32(shorter,12,2);CRC32 shorterCrc=new CRC32();shorterCrc.update(shorter,0,20);shorterCrc.update(shorter,24,shorter.length-24);put32(shorter,20,shorterCrc.getValue());
        FakeLink incompleteLink=new FakeLink(status,shorter,page1,null);incompleteLink.multiAudio=audio;for(RecorderWire.Descriptor item:catalog.entries())incompleteLink.segments.put(item.recordingId,item);
        try(RecordingClient client=new RecordingClient(incompleteLink)){if(client.receiveSession(d,Files.createTempDirectory(root,"session-incomplete-"),null).state!=RecordingLibrary.SessionState.INCOMPLETE)throw new AssertionError("missing final segment shown as complete");}
        byte[] broken=d0.clone();broken[32]^=1;expectFailure(()->RecorderWire.Descriptor.decode(broken));byte[] badPage=page0.clone();badPage[25]^=1;expectFailure(()->new RecorderWire.Catalog(peer,17).accept(badPage));
        expectFailure(()->new RecorderWire.Catalog(peer,17).accept(page1));byte[] altered=status.clone();altered[90]^=1;expectFailure(()->RecorderWire.Peer.fromStatus(altered));
        byte[] p=new byte[56+audio.length];p[0]=1;p[1]=1;put16(p,2,audio.length);put32(p,4,d.recordingId);put32(p,8,0);put32(p,12,0);put32(p,16,audio.length);System.arraycopy(d.sha256(),0,p,24,32);System.arraycopy(audio,0,p,56,audio.length);CRC32 c=new CRC32();c.update(p,4,16);c.update(audio);put32(p,20,c.getValue());
        if(!Arrays.equals(audio,RecorderWire.packet(d,p,0,0)))throw new AssertionError("golden chunk");expectFailure(()->RecorderWire.packet(d,p,1,0));
        FakeLink link=new FakeLink(status,page0,page1,p);Path saved;Path folder=Files.createTempDirectory(root,"private-recordings-");
        Path repairFolder=Files.createTempDirectory(root,"corrupt-resume-");
        try(SegmentReceiver stale=new SegmentReceiver(repairFolder,d)){stale.accept(p);}
        Path corruptPath=repairFolder.resolve(SegmentReceiver.key(d)+".part");byte[] damaged=Files.readAllBytes(corruptPath);damaged[0]^=1;Files.write(corruptPath,damaged);
        try(RecordingClient repair=new RecordingClient(new FakeLink(status,page0,page1,p))){
            repair.listRecordings();Path repaired=repair.download(41,repairFolder,null);
            if(!Arrays.equals(Files.readAllBytes(repaired),audio))throw new AssertionError("corrupt resume must be recovered from the device");
        }
        try(java.nio.file.DirectoryStream<Path> backups=Files.newDirectoryStream(repairFolder,"damaged-*.part")){
            java.util.Iterator<Path> it=backups.iterator();if(!it.hasNext()||!Arrays.equals(Files.readAllBytes(it.next()),damaged)||it.hasNext())throw new AssertionError("damaged partial copy was not retained");
        }
        Path interruptedFolder=Files.createTempDirectory(root,"corrupt-interrupted-");
        try(SegmentReceiver stale=new SegmentReceiver(interruptedFolder,d)){stale.accept(packet(d,audio,0,7,false));}
        Path interrupted=interruptedFolder.resolve(SegmentReceiver.key(d)+".part");byte[] badPrefix=Files.readAllBytes(interrupted);badPrefix[0]^=1;Files.write(interrupted,badPrefix);
        FakeLink interruptedLink=new FakeLink(status,page0,page1,p);interruptedLink.resumedPacket=packet(d,audio,7,audio.length-7,true);
        try(RecordingClient repair=new RecordingClient(interruptedLink)){repair.listRecordings();Path repaired=repair.download(41,interruptedFolder,null);if(!Arrays.equals(Files.readAllBytes(repaired),audio)||interruptedLink.pullCount!=2)throw new AssertionError("corrupt prefix must resume then retry once from the start");}
        Path repeatedFolder=Files.createTempDirectory(root,"corrupt-twice-");
        try(SegmentReceiver stale=new SegmentReceiver(repeatedFolder,d)){stale.accept(p);}
        Files.write(repeatedFolder.resolve(SegmentReceiver.key(d)+".part"),damaged);
        byte[] wrongAudio=audio.clone();wrongAudio[0]^=1;byte[] wrongPacket=packet(d,wrongAudio,0,wrongAudio.length,true);
        try(RecordingClient repair=new RecordingClient(new FakeLink(status,page0,page1,wrongPacket))){repair.listRecordings();expectFailure(()->repair.download(41,repeatedFolder,null));}
        int retained=0;try(java.nio.file.DirectoryStream<Path> backups=Files.newDirectoryStream(repeatedFolder,"damaged-*.part")){for(Path ignored:backups)retained++;}
        if(retained!=2||Files.exists(repeatedFolder.resolve(SegmentReceiver.key(d)+".cop1")))throw new AssertionError("repeated integrity failure must stop with both copies retained");
        Path oversizedFolder=Files.createTempDirectory(root,"oversized-partial-");
        try(SegmentReceiver stale=new SegmentReceiver(oversizedFolder,d)){stale.accept(p);}
        byte[] oversized=Arrays.copyOf(audio,audio.length+1);oversized[oversized.length-1]=42;Files.write(oversizedFolder.resolve(SegmentReceiver.key(d)+".part"),oversized);
        try(RecordingClient repair=new RecordingClient(new FakeLink(status,page0,page1,p))){repair.listRecordings();Path repaired=repair.download(41,oversizedFolder,null);if(!Arrays.equals(Files.readAllBytes(repaired),audio))throw new AssertionError("oversized partial should be replaced by a fresh transfer");}
        try(java.nio.file.DirectoryStream<Path> backups=Files.newDirectoryStream(oversizedFolder,"damaged-*.part")){
            java.util.Iterator<Path> it=backups.iterator();if(!it.hasNext()||!Arrays.equals(Files.readAllBytes(it.next()),oversized)||it.hasNext())throw new AssertionError("oversized partial must be retained");
        }
        try(RecordingClient client=new RecordingClient(link)){
            if(client.readDeviceStatus().previousRecordingDamageReported)throw new AssertionError("normal status should not report a damaged tail");
            link.status[3]|=8;if(!client.readDeviceStatus().previousRecordingDamageReported)throw new AssertionError("reported old damaged tail must reach the caller");
            link.status[3]&=~8;
            link.status[20]^=1;expectFailure(()->client.readDeviceStatus());link.status[20]^=1;
            if(client.listRecordings().size()!=3)throw new AssertionError("client catalog");saved=client.download(41,folder,null);
            if(!client.download(41,folder,null).equals(saved)||link.pullCount!=1)throw new AssertionError("existing verified copy should be reused");
            byte[] brokenCopy=Files.readAllBytes(saved);brokenCopy[0]^=1;Files.write(saved,brokenCopy);
            if(!client.download(41,folder,null).equals(saved)||!Arrays.equals(Files.readAllBytes(saved),audio)||link.pullCount!=2)throw new AssertionError("damaged local copy should be reloaded");
            try(java.nio.file.DirectoryStream<Path> backups=Files.newDirectoryStream(folder,"damaged-*.cop1")){
                java.util.Iterator<Path> it=backups.iterator();if(!it.hasNext()||!Arrays.equals(Files.readAllBytes(it.next()),brokenCopy)||it.hasNext())throw new AssertionError("damaged local copy must be preserved");
            }
        }
        if(!link.closed||!Arrays.equals(Files.readAllBytes(saved),audio))throw new AssertionError("client durable copy");
        if(RecordingLibrary.list(folder).size()!=1||RecordingLibrary.list(folder).get(0).state!=RecordingLibrary.State.VERIFIED)throw new AssertionError("local recording inventory");
        if(RecordingLibrary.sessions(folder).size()!=1||RecordingLibrary.sessions(folder).get(0).state!=RecordingLibrary.SessionState.INCOMPLETE)throw new AssertionError("missing tail is not a complete session");
        RecorderWire.Descriptor second=catalog.entries().get(1);Path resumed;
        try(SegmentReceiver first=new SegmentReceiver(folder,second)){
            first.accept(packet(second,audio,0,7,false));if(first.resumeOffset()!=7)throw new AssertionError("partial progress");
            if(RecordingLibrary.list(folder).stream().filter(e->e.state==RecordingLibrary.State.PARTIAL).count()!=1)throw new AssertionError("partial must be visible");
            expectFailure(()->new SegmentReceiver(folder,second));
        }
        try(SegmentReceiver again=new SegmentReceiver(folder,second)){
            if(again.resumeOffset()!=7)throw new AssertionError("restart must retain partial copy");
            byte[] wrong=packet(second,audio,7,audio.length-7,true);wrong[wrong.length-1]^=1;expectFailure(()->again.accept(wrong));
            if(again.resumeOffset()!=7)throw new AssertionError("bad packet advanced file");again.accept(packet(second,audio,7,audio.length-7,true));resumed=again.finish();
        }
        if(!Arrays.equals(Files.readAllBytes(resumed),audio))throw new AssertionError("resumed recording differs");
        if(RecordingLibrary.list(folder).stream().filter(e->e.state==RecordingLibrary.State.VERIFIED).count()!=2)throw new AssertionError("resumed inventory");
        RecorderWire.Descriptor third=catalog.entries().get(2);
        try(SegmentReceiver receiver=new SegmentReceiver(folder,third)){receiver.accept(packet(third,audio,0,audio.length,true));receiver.finish();}
        RecordingLibrary.Session session=RecordingLibrary.sessions(folder).get(0);
        if(session.state!=RecordingLibrary.SessionState.COMPLETE||session.segments.size()!=3||session.segments.get(2).descriptor.segmentIndex!=2)throw new AssertionError("complete session must group ordered verified segments");
        Files.write(resumed,new byte[]{1,2,3});
        if(RecordingLibrary.list(folder).stream().filter(e->e.state==RecordingLibrary.State.DAMAGED).count()!=1)throw new AssertionError("damaged copy must not appear verified");
        if(RecordingLibrary.sessions(folder).get(0).state!=RecordingLibrary.SessionState.DAMAGED)throw new AssertionError("a damaged segment must damage the session");
        p[p.length-1]^=1;expectFailure(()->RecorderWire.packet(d,p,0,0));
        System.out.println("PASS Windows golden directory, packet, client transfer and corruption paths");
    }
}
