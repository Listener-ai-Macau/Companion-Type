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
        final byte[] status,page0,page1,packet;byte[] control,list,pull,resumedPacket,multiAudio,consumeReply;boolean closed,partialOnce,failOnNextPull,loseConsumeReply,timeoutConsumeReply;int pullCount,consumeWrites;
        final java.util.Map<Long,RecorderWire.Descriptor> segments=new java.util.HashMap<>();
        int directoryRequests,directoryRestarts,staleAt=-1,staleRemaining,refusalResult=8;
        boolean malformedRefusal;long lastDirectoryNonce;
        int bulkRequests,balancedRequests;boolean bulkActive;
        FakeLink(byte[] s,byte[] a,byte[] b,byte[] p){status=s;page0=a;page1=b;packet=p;}
        public int mtu(){return 247;} public byte[] read(UUID id){return status.clone();}
        public void subscribe(UUID id){} public void close(){closed=true;}
        public void setTransferPriority(boolean bulk){if(bulk){if(bulkActive)throw new AssertionError("nested bulk priority");bulkActive=true;bulkRequests++;}else{if(!bulkActive)throw new AssertionError("unmatched balanced restore");bulkActive=false;balancedRequests++;}}
        public void write(UUID id,byte[] value){
            if(id.equals(RecordingClient.RECORDING_CONTROL) && value[1]==0x22) control=value.clone();
            else if(id.equals(RecordingClient.RECORDING_CONTROL) && value[1]==0x20){
                directoryRequests++;
                if(value[12]==0){
                    long fresh=RecorderWire.u32(value,8);
                    if(RecorderWire.u32(value,4)!=0||fresh==lastDirectoryNonce)throw new AssertionError("restart must discard snapshot and nonce");
                    lastDirectoryNonce=fresh;directoryRestarts++;
                }
                if((value[12]&255)==staleAt&&staleRemaining>0){
                    staleRemaining--;list=directoryError(lastDirectoryNonce,refusalResult);
                    if(malformedRefusal)list=Arrays.copyOf(list,12);
                }else{
                    list=(value[12]==0?page0:page1).clone();System.arraycopy(value,8,list,16,4);
                    put32(list,4,directoryRestarts);
                    CRC32 crc=new CRC32();crc.update(list,0,20);crc.update(list,24,list.length-24);put32(list,20,crc.getValue());
                }
            }
            else if(id.equals(RecordingClient.RECORDING_PULL)){if(value[2]!=4)throw new AssertionError("pull must stream the whole segment");pullCount++;
                if(multiAudio!=null){long recording=0,offset=0;for(int i=0;i<4;i++){recording|=(value[4+i]&255L)<<(8*i);offset|=(value[28+i]&255L)<<(8*i);}
                    RecorderWire.Descriptor d=segments.get(recording);if(d==null)throw new AssertionError("unknown requested segment");
                    if(partialOnce){partialOnce=false;failOnNextPull=true;pull=packet(d,multiAudio,0,7,false);}else pull=packet(d,multiAudio,(int)offset,multiAudio.length-(int)offset,true);
                }else pull=(value[28]==7&&resumedPacket!=null?resumedPacket:packet).clone();
            }else if(id.equals(RecordingClient.RECORDING_CONSUME)){consumeWrites++;consumeReply=value.clone();}
            else throw new AssertionError("unexpected command");
        }
        public byte[] await(UUID id,long timeout)throws java.io.IOException {if(id.equals(RecordingClient.RECORDING_CONTROL))return control;if(id.equals(RecordingClient.RECORDING_LIST))return list;if(id.equals(RecordingClient.RECORDING_PULL)){
            if(pull==null&&failOnNextPull){failOnNextPull=false;throw new java.io.IOException("synthetic disconnect");}byte[] result=pull;if(failOnNextPull)pull=null;return result;}
            if(id.equals(RecordingClient.RECORDING_CONSUME)){if(timeoutConsumeReply)throw new java.net.SocketTimeoutException("synthetic lost receipt without disconnect");if(loseConsumeReply)throw new java.io.IOException("synthetic lost receipt");return consumeReply.clone();}
            throw new AssertionError("unexpected notification");}
    }
    private static byte[] directoryError(long nonce,int result){
        byte[] p={'C','R','E','2',2,0,16,0,0,0,0,0,0,0,0,0};put32(p,8,nonce);put32(p,12,result);return p;
    }
    private static byte[] page(RecorderWire.Descriptor a,RecorderWire.Descriptor b){
        byte[] p=new byte[24+224];p[0]=2;p[1]=2;put16(p,2,112);put32(p,4,1);put32(p,8,0);put32(p,12,2);put32(p,16,17);
        System.arraycopy(a.wireBytes(),0,p,24,112);System.arraycopy(b.wireBytes(),0,p,136,112);
        CRC32 c=new CRC32();c.update(p,0,20);c.update(p,24,224);put32(p,20,c.getValue());return p;
    }
    private static byte[] calendarPage(byte[] legacy,long date){
        int count=legacy[1]&255;byte[] p=Arrays.copyOf(legacy,24+count*116);put16(p,2,116);
        for(int i=0;i<count;i++){System.arraycopy(legacy,24+i*112,p,24+i*116,112);put32(p,24+i*116+112,date);}
        CRC32 crc=new CRC32();crc.update(p,0,20);crc.update(p,24,p.length-24);put32(p,20,crc.getValue());return p;
    }
    public static void main(String[] args)throws Exception {
        Path root=Paths.get(args[0]);byte[] d0=Files.readAllBytes(root.resolve("descriptor0.bin"));byte[] page0=Files.readAllBytes(root.resolve("page0.bin"));byte[] page1=Files.readAllBytes(root.resolve("page1.bin"));byte[] audio=Files.readAllBytes(root.resolve("payload.bin"));
        byte[] status=new byte[116];status[0]=1;put32(status,12,0x57424155L);System.arraycopy(d0,96,status,20,12);System.arraycopy(new byte[]{'C','R','V','2'},0,status,84,4);put16(status,88,2);put16(status,90,32);put32(status,92,7);System.arraycopy(d0,12,status,96,8);put16(status,104,64);put16(status,106,1024);put16(status,108,248);CRC32 statusCrc=new CRC32();statusCrc.update(status,84,28);put32(status,112,statusCrc.getValue());
        RecorderWire.Peer peer=RecorderWire.Peer.fromStatus(status);byte[] negotiation=peer.negotiate(23,247);if(negotiation.length!=32||negotiation[1]!=0x22)throw new AssertionError("negotiation");
        RecorderWire.Catalog catalog=new RecorderWire.Catalog(peer,17);if(!catalog.accept(page0)||catalog.complete()||catalog.accept(page0)||!catalog.accept(page1)||!catalog.complete())throw new AssertionError("golden directory or duplicate page");
        if(catalog.entries().size()!=3)throw new AssertionError("missing segments");RecorderWire.Descriptor d=catalog.entries().get(0);if(d.recordingId!=41||d.segmentIndex!=0||d.encodedLength!=audio.length)throw new AssertionError("golden descriptor");
        RecorderWire.Catalog refusal=new RecorderWire.Catalog(peer,17);
        if(refusal.accept(directoryError(18,8)))throw new AssertionError("unrelated stale nonce accepted");
        try{refusal.accept(directoryError(17,8));throw new AssertionError("stale response accepted");}catch(RecorderWire.CatalogChanged expected){}
        for(int reason:new int[]{1,3,4,5,6,9,99}){
            try{refusal.accept(directoryError(17,reason));throw new AssertionError("refusal accepted");}
            catch(RecorderWire.CatalogChanged unsafe){throw new AssertionError("non-stale refusal became retryable",unsafe);}
            catch(java.io.IOException expected){if(!expected.getMessage().contains("result "+reason))throw new AssertionError("device reason lost");}
        }
        expectFailure(()->refusal.accept(Arrays.copyOf(directoryError(17,8),12)));
        byte[] wrongVersion=directoryError(17,8);wrongVersion[4]=1;expectFailure(()->refusal.accept(wrongVersion));
        FakeLink staleLink=new FakeLink(status,page0,page1,null);staleLink.staleAt=2;staleLink.staleRemaining=1;
        try(RecordingClient client=new RecordingClient(staleLink)){
            if(client.listRecordings().size()!=3||staleLink.directoryRestarts!=2||staleLink.directoryRequests!=4)
                throw new AssertionError("stale later page must restart a complete fresh snapshot");
        }
        FakeLink alwaysStale=new FakeLink(status,page0,page1,null);alwaysStale.staleAt=2;alwaysStale.staleRemaining=9;
        try(RecordingClient client=new RecordingClient(alwaysStale)){expectFailure(client::listRecordings);}
        if(alwaysStale.directoryRestarts!=3||alwaysStale.directoryRequests!=6)throw new AssertionError("directory refresh must be bounded");
        for(boolean malformed:new boolean[]{false,true}){
            FakeLink hardFailure=new FakeLink(status,page0,page1,null);hardFailure.staleAt=2;hardFailure.staleRemaining=1;hardFailure.refusalResult=6;hardFailure.malformedRefusal=malformed;
            try(RecordingClient client=new RecordingClient(hardFailure)){expectFailure(client::listRecordings);}
            if(hardFailure.directoryRestarts!=1||hardFailure.consumeWrites!=0)throw new AssertionError("corruption must not refresh or consume");
        }
        long recordingDate=1793856001L;
        RecorderWire.Catalog datedCatalog=new RecorderWire.Catalog(peer,17);datedCatalog.calendar(true);
        if(datedCatalog.request()[2]!=1)throw new AssertionError("calendar request missing");
        datedCatalog.accept(calendarPage(page0,recordingDate));datedCatalog.accept(calendarPage(page1,recordingDate));
        RecorderWire.Descriptor dated=datedCatalog.entries().get(0);
        if(d.startedUnixSeconds!=0||dated.startedUnixSeconds!=recordingDate||
           !Arrays.equals(d.wireBytes(),dated.wireBytes())||dated.metadataBytes().length!=120||
           RecorderWire.Descriptor.decode(dated.metadataBytes()).startedUnixSeconds!=recordingDate)
            throw new AssertionError("recording date changed the sealed audio identity");
        byte[] damagedDate=dated.metadataBytes();damagedDate[112]^=1;
        expectFailure(()->RecorderWire.Descriptor.decode(damagedDate));
        Path datedFolder=Files.createTempDirectory(root,"calendar-restart-");
        for(RecorderWire.Descriptor item:datedCatalog.entries()){
            try(SegmentReceiver receiver=new SegmentReceiver(datedFolder,item)){
                receiver.accept(packet(item,audio,0,audio.length,true));receiver.finish();
            }
        }
        if(RecordingLibrary.sessions(datedFolder).get(0).startedUnixSeconds!=recordingDate)
            throw new AssertionError("recording date was lost after receiver restart");
        // A later legacy read must preserve the known date already saved locally.
        try(SegmentReceiver receiver=new SegmentReceiver(datedFolder,d)){receiver.finish();}
        if(RecordingLibrary.sessions(datedFolder).get(0).startedUnixSeconds!=recordingDate)
            throw new AssertionError("legacy metadata erased the recording date");
        RecorderWire.Catalog changedDateCatalog=new RecorderWire.Catalog(peer,17);changedDateCatalog.calendar(true);
        changedDateCatalog.accept(calendarPage(page0,recordingDate+1));changedDateCatalog.accept(calendarPage(page1,recordingDate+1));
        expectFailure(()->{try(SegmentReceiver ignored=new SegmentReceiver(datedFolder,changedDateCatalog.entries().get(0))) {}});
        // One unrelated damaged recording must not prevent an active session from being received.
        Path isolated=Files.createTempDirectory(root,"unrelated-damage-");
        String[] otherKey=SegmentReceiver.key(d).split("-");otherKey[2]="ffffffff";
        Path unrelated=isolated.resolve(String.join("-",otherKey)+".meta");byte[] brokenMetadata={1,2,3};Files.write(unrelated,brokenMetadata);
        FakeLink isolatedLink=new FakeLink(status,page0,page1,null);isolatedLink.multiAudio=audio;
        isolatedLink.staleAt=2;isolatedLink.staleRemaining=1;
        for(RecorderWire.Descriptor item:catalog.entries())isolatedLink.segments.put(item.recordingId,item);
        try(RecordingClient client=new RecordingClient(isolatedLink,dir->{},prefix->{checkPrefix(prefix);})){
            RecordingLibrary.Session received=client.syncAvailableAndReclaim(d,isolated,null);
            if(received.state!=RecordingLibrary.SessionState.COMPLETE||received.segments.size()!=3)throw new AssertionError("unrelated damaged metadata stopped an intact recording");
            if(isolatedLink.consumeWrites!=3||isolatedLink.directoryRestarts!=2)throw new AssertionError("catalog refresh repeated consumption or lost selected session");
            if(isolatedLink.bulkRequests!=1||isolatedLink.balancedRequests!=1||isolatedLink.bulkActive)throw new AssertionError("successful segment batch left bulk priority active");
            if(client.receiveSession(d,isolated,null).state!=RecordingLibrary.SessionState.COMPLETE)throw new AssertionError("unrelated damage stopped a non-reclaiming receive");
        }
        if(!Arrays.equals(Files.readAllBytes(unrelated),brokenMetadata))throw new AssertionError("unrelated damaged metadata was not preserved");
        expectFailure(()->RecordingLibrary.sessions(isolated)); // The full inventory still reports the damage.
        RecordingLibrary.Inventory inspection=RecordingLibrary.inspect(isolated);
        if(inspection.sessions.size()!=1||inspection.sessions.get(0).state!=RecordingLibrary.SessionState.COMPLETE||
           inspection.problems.size()!=1||!inspection.problems.get(0).file.equals(unrelated)||
           inspection.problems.get(0).detail.isEmpty()||!Arrays.equals(Files.readAllBytes(unrelated),brokenMetadata))
            throw new AssertionError("inventory must retain usable sessions and separately report damaged metadata");
        if(!RecordingLibrary.inspect(Files.createTempDirectory(root,"empty-inventory-")).problems.isEmpty())
            throw new AssertionError("empty inventory must not report a problem");
        Path currentDamage=Files.createTempDirectory(root,"same-session-damage-");
        Path damagedCurrent=currentDamage.resolve(SegmentReceiver.sessionPrefix(d)+"damaged.meta");Files.write(damagedCurrent,brokenMetadata);
        FakeLink protectedLink=new FakeLink(status,page0,page1,null);protectedLink.multiAudio=audio;
        for(RecorderWire.Descriptor item:catalog.entries())protectedLink.segments.put(item.recordingId,item);
        try(RecordingClient client=new RecordingClient(protectedLink,dir->{},prefix->{checkPrefix(prefix);})){
            expectFailure(()->client.syncAvailableAndReclaim(d,currentDamage,null));
        }
        if(protectedLink.consumeWrites!=0||!Arrays.equals(Files.readAllBytes(damagedCurrent),brokenMetadata))
            throw new AssertionError("damaged metadata for the selected session must retain device and local copies");
        if(protectedLink.bulkRequests!=1||protectedLink.balancedRequests!=1||protectedLink.bulkActive)throw new AssertionError("failed segment batch left bulk priority active");
        FakeLink idlePriority=new FakeLink(status,page0,page1,null);idlePriority.staleAt=2;idlePriority.staleRemaining=1;idlePriority.refusalResult=6;
        try(RecordingClient client=new RecordingClient(idlePriority,dir->{},prefix->{checkPrefix(prefix);})){
            expectFailure(()->client.syncAvailableAndReclaim(d,Files.createTempDirectory(root,"priority-no-work-"),null));
        }
        if(idlePriority.bulkRequests!=0||idlePriority.balancedRequests!=0)throw new AssertionError("failed catalog requested high priority without payload");
        byte[] emptyPage=Arrays.copyOf(page0,24);emptyPage[1]=0;put32(emptyPage,12,0);CRC32 emptyCrc=new CRC32();emptyCrc.update(emptyPage,0,20);put32(emptyPage,20,emptyCrc.getValue());
        FakeLink noSealed=new FakeLink(status,emptyPage,page1,null);
        try(RecordingClient client=new RecordingClient(noSealed,dir->{},prefix->{checkPrefix(prefix);})){
            if(client.syncAvailableAndReclaim(d,isolated,null).state!=RecordingLibrary.SessionState.COMPLETE)throw new AssertionError("saved complete prefix lost without new segments");
        }
        if(noSealed.bulkRequests!=0||noSealed.balancedRequests!=0)throw new AssertionError("following without new segments requested high priority");
        RecordingLibrary.Inventory affected=RecordingLibrary.inspect(currentDamage);
        if(affected.problems.size()!=1||affected.sessions.size()!=1||affected.sessions.get(0).state!=RecordingLibrary.SessionState.DAMAGED)
            throw new AssertionError("a damaged metadata file must mark its own visible session damaged");
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
        Path reclaimFolder=Files.createTempDirectory(root,"reclaim-session-");FakeLink lost=new FakeLink(status,page0,page1,null);lost.multiAudio=audio;lost.loseConsumeReply=true;
        for(RecorderWire.Descriptor item:catalog.entries())lost.segments.put(item.recordingId,item);
        try(RecordingClient client=new RecordingClient(lost,dir->{},prefix->{checkPrefix(prefix);})){expectFailure(()->client.syncAvailableAndReclaim(d,reclaimFolder,null));}
        if(lost.consumeWrites!=1||!Files.isRegularFile(reclaimFolder.resolve(".consume-pending")))throw new AssertionError("lost consume confirmation not retained");
        byte[] otherSession=d.wireBytes();otherSession[20]^=1;CRC32 otherSessionCrc=new CRC32();otherSessionCrc.update(otherSession,0,108);put32(otherSession,108,otherSessionCrc.getValue());
        RecorderWire.Descriptor otherSelection=RecorderWire.Descriptor.decode(otherSession);
        FakeLink otherAttempt=new FakeLink(status,page0,page1,null);otherAttempt.multiAudio=audio;
        try(RecordingClient client=new RecordingClient(otherAttempt,dir->{},prefix->{checkPrefix(prefix);})){
            expectFailure(()->client.syncAvailableAndReclaim(otherSelection,reclaimFolder,null));
            if(otherAttempt.consumeWrites!=0||otherAttempt.pullCount!=0||!RecordingLibrary.pendingConfirmation(reclaimFolder).sameContent(d))
                throw new AssertionError("switching sessions touched an unrelated pending receipt");
        }
        FakeLink reconnected=new FakeLink(status,page(catalog.entries().get(1),catalog.entries().get(2)),page1,null);reconnected.multiAudio=audio;
        for(RecorderWire.Descriptor item:catalog.entries())reconnected.segments.put(item.recordingId,item);
        try(RecordingClient client=new RecordingClient(reconnected,dir->{},prefix->{checkPrefix(prefix);})){
            RecordingLibrary.Session session=client.syncAvailableAndReclaim(d,reclaimFolder,null);
            if(session.state!=RecordingLibrary.SessionState.COMPLETE||session.segments.size()!=3||reconnected.consumeWrites!=3||reconnected.pullCount!=2)
                throw new AssertionError("lost receipt and absent original were not reconciled");
            client.syncAvailableAndReclaim(d,reclaimFolder,null);
            if(reconnected.consumeWrites!=3||reconnected.pullCount!=2)throw new AssertionError("confirmed segments were repeated");
            if(client.followSessionAndReclaim(d,reclaimFolder,null).state!=RecordingLibrary.SessionState.COMPLETE)
                throw new AssertionError("following did not stop on the original terminal segment");
        }
        // The card may finish consuming a segment while its reply times out before
        // Android emits a disconnect. Resume the exact pending receipt on a new link.
        Path timeoutFolder=Files.createTempDirectory(root,"timeout-receipt-session-");
        FakeLink timeoutLink=new FakeLink(status,page0,page1,null);timeoutLink.multiAudio=audio;timeoutLink.timeoutConsumeReply=true;
        FakeLink timeoutRecovery=new FakeLink(status,page(catalog.entries().get(1),catalog.entries().get(2)),page1,null);timeoutRecovery.multiAudio=audio;
        for(RecorderWire.Descriptor item:catalog.entries()){timeoutLink.segments.put(item.recordingId,item);timeoutRecovery.segments.put(item.recordingId,item);}
        int[] timeoutConnections={0};boolean[] pendingOnClose={false};RecordingLibrary.Session[] timeoutResult={null};
        new RecordingSyncRunner(()->{
            FakeLink chosen=timeoutConnections[0]++==0?timeoutLink:timeoutRecovery;
            RecordingClient client=new RecordingClient(chosen,dir->{},prefix->{checkPrefix(prefix);});
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync()throws java.io.IOException{return client.syncAvailableAndReclaim(d,timeoutFolder,null);}
                public boolean disconnected(){return false;}
                public void close()throws java.io.IOException{if(chosen==timeoutLink)pendingOnClose[0]=Files.isRegularFile(timeoutFolder.resolve(".consume-pending"));client.close();}
            };
        },new RecordingSyncRunner.Listener(){
            public void status(String state,String detail){if(state.equals("error"))throw new AssertionError("timeout treated as terminal: "+detail);}
            public void finished(RecordingLibrary.Session session){timeoutResult[0]=session;}
        },millis->{}).run();
        if(timeoutConnections[0]!=2||!pendingOnClose[0]||!timeoutLink.closed||timeoutLink.consumeWrites!=1||timeoutRecovery.consumeWrites!=3||
           timeoutRecovery.pullCount!=2||timeoutResult[0]==null||timeoutResult[0].state!=RecordingLibrary.SessionState.COMPLETE||
           Files.exists(timeoutFolder.resolve(".consume-pending")))throw new AssertionError("timed-out receipt did not resume safely");
        byte[] absentWire=d.wireBytes();put32(absentWire,8,99);put32(absentWire,28,10);
        long absentOffset=d.sampleCount*10;for(int i=0;i<8;i++)absentWire[32+i]=(byte)(absentOffset>>>(8*i));
        CRC32 absentCrc=new CRC32();absentCrc.update(absentWire,0,108);put32(absentWire,108,absentCrc.getValue());
        RecorderWire.Descriptor absent=RecorderWire.Descriptor.decode(absentWire);Path absentFolder=Files.createTempDirectory(root,"reclaim-unknown-");
        FakeLink unselected=new FakeLink(status,page0,page1,null);unselected.multiAudio=audio;
        for(RecorderWire.Descriptor item:catalog.entries())unselected.segments.put(item.recordingId,item);
        try(RecordingClient client=new RecordingClient(unselected,dir->{},prefix->{checkPrefix(prefix);})){
            expectFailure(()->client.syncAvailableAndReclaim(absent,absentFolder,null));
            if(unselected.pullCount!=0||unselected.consumeWrites!=0)throw new AssertionError("unknown selection touched the device session");
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
    private static void checkPrefix(RecordingLibrary.Session prefix)throws java.io.IOException {
        if(prefix.segments.isEmpty()||prefix.segments.get(0).descriptor.segmentIndex!=0)throw new java.io.IOException("missing local prefix");
    }
}
