package com.denzic.companion.mobile;

import java.io.Closeable;
import java.io.IOException;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.function.LongSupplier;

/** One negotiated receiver with at most one physical range confirmation in
 * flight. Original data notifications continue while the separate60B receipt
 * lane waits. All erases begin after the caller's first actual PULL write;
 * terminal whole-recording consumption remains the original CRA2 path. */
final class RangeConsume {
    private final RecorderWire.Peer peer;
    private final RecordingClient.Link link;
    private final RangeCheckpoint.DirectorySync sync;
    private final LongSupplier nonce;
    private volatile RecordingTransferMetrics metrics;
    void observe(RecordingTransferMetrics metrics){this.metrics=metrics;if(metrics!=null)metrics.rangeNegotiated();}
    RangeConsume(RecorderWire.Peer peer,RecordingClient.Link link,RangeCheckpoint.DirectorySync sync,LongSupplier nonce){
        this.peer=peer;this.link=link;this.sync=sync;this.nonce=nonce;
    }
    static long binding(RecorderWire.Descriptor d){
        byte[] p=d.wireBytes();p[95]=2;RecorderWire.put32(p,108,RecorderWire.crc(p,0,108));
        return RecorderWire.crc(p,0,p.length);
    }
    private static void put16(byte[] p,int at,int value){p[at]=(byte)value;p[at+1]=(byte)(value>>>8);}
    private static int u16(byte[] p,int at){return(p[at]&255)|((p[at+1]&255)<<8);}
    static byte[] request(RecorderWire.Descriptor d,long token,RangeCheckpoint checkpoint)throws IOException {
        if(token<=0||token>0xffffffffL)throw new IOException("invalid range request nonce");
        byte[] p=new byte[96];System.arraycopy(new byte[]{'C','R','G','3',3,0,96,0},0,p,0,8);
        System.arraycopy(d.uid(),0,p,8,12);RecorderWire.put64(p,20,d.epoch);RecorderWire.put64(p,28,d.sessionId);
        RecorderWire.put32(p,36,d.segmentIndex);RecorderWire.put32(p,40,d.recordingId);RecorderWire.put32(p,44,token);
        RecorderWire.put32(p,52,binding(d));
        if(checkpoint!=null){
            if(!checkpoint.descriptor.sameContent(d)||checkpoint.nonce!=token)throw new IOException("range proof identity changed");
            put16(p,48,checkpoint.firstSector);put16(p,50,checkpoint.endSector);
            System.arraycopy(checkpoint.rangeSha(),0,p,56,32);p[88]=1;
        }
        RecorderWire.put32(p,92,RecorderWire.crc(p,0,92));return p;
    }
    static final class Status {
        final long nonce;final int first,end;final boolean pending;
        Status(long nonce,int first,int end,boolean pending){this.nonce=nonce;this.first=first;this.end=end;this.pending=pending;}
    }
    static final class Refused extends IOException {
        final long result;
        Refused(long result){super("device range confirmation failed ("+result+"); saved source retained");this.result=result;}
    }
    static Status reply(RecorderWire.Descriptor d,long token,byte[] p)throws IOException {
        if(p==null||!RecorderWire.magic(p,0,"CRR3"))return null;
        if(p.length!=60||u16(p,4)!=3||u16(p,6)!=60||RecorderWire.crc(p,0,56)!=RecorderWire.u32(p,56)||
           !Arrays.equals(Arrays.copyOfRange(p,8,20),d.uid())||RecorderWire.u64(p,20)!=d.epoch)
            throw new IOException("invalid device range receipt");
        if(RecorderWire.u32(p,28)!=d.recordingId||RecorderWire.u32(p,32)!=token)return null;
        if(RecorderWire.u32(p,52)!=binding(d)||p[48]<0||p[48]>1||p[49]!=0||p[50]!=0||p[51]!=0)
            throw new IOException("device range identity changed");
        long result=RecorderWire.u32(p,44);if(result!=0)throw new Refused(result);
        long previous=RecorderWire.u32(p,36);int first=u16(p,40),end=u16(p,42);
        long used=(((d.encodedLength+247)/248+1)*256+4095)/4096;
        if(previous==0?(first!=0||end!=0||p[48]!=0):(end<=first||end>used))throw new IOException("invalid physical range frontier");
        return new Status(previous,first,end,p[48]==1);
    }
    private Status exchange(RecorderWire.Descriptor d,long token,RangeCheckpoint checkpoint)throws IOException {
        link.write(RecordingClient.RECORDING_CONSUME,request(d,token,checkpoint));
        long deadline=System.nanoTime()+15_000_000_000L;
        while(true){
            long remaining=(deadline-System.nanoTime())/1_000_000L;
            if(remaining<=0)throw new java.net.SocketTimeoutException("physical range confirmation pending; saved source retained");
            Status result=reply(d,token,link.await(RecordingClient.RECORDING_CONSUME,remaining));
            if(result!=null)return result;
        }
    }
    final class Session implements Closeable {
        private final Path directory;
        private final RecorderWire.Descriptor descriptor;
        private int frontier;
        private RangeCheckpoint resume;
        private Pending pending;
        private long lastNonce;
        private boolean completeCopy,closed;
        private final class Pending {
            final RangeCheckpoint checkpoint;final CountDownLatch finished=new CountDownLatch(1);
            final Thread thread;volatile IOException error;
            Pending(RangeCheckpoint checkpoint){
                this.checkpoint=checkpoint;
                thread=new Thread(()->{
                    try{
                        long began=System.nanoTime();
                        Status result=exchange(descriptor,checkpoint.nonce,checkpoint);
                        if(result.pending||result.nonce!=checkpoint.nonce||result.first!=checkpoint.firstSector||result.end!=checkpoint.endSector)
                            throw new IOException("device did not confirm the exact physical range; saved proof retained");
                        long replied=System.nanoTime();
                        checkpoint.confirmOwned(directory,sync);
                        RecordingTransferMetrics m=metrics;if(m!=null)m.rangeConfirmed(checkpoint.firstSector,checkpoint.endSector,replied-began,System.nanoTime()-replied);
                    }catch(IOException e){error=e;}catch(RuntimeException e){error=new IOException("range confirmation failed; saved source retained",e);}
                    finally{finished.countDown();}
                },"Companion-range-confirmation");
                thread.setDaemon(true);thread.start();
            }
        }
        Session(Path directory,RecorderWire.Descriptor d,SegmentReceiver receiver)throws IOException {
            this.directory=directory;descriptor=d;
            peer.validate(d);
            Status device=exchange(d,nonce.getAsLong(),null); // read-only, no erase
            if(RangeCheckpoint.exists(directory,d)){
                RangeCheckpoint saved=RangeCheckpoint.read(directory,d);
                lastNonce=saved.nonce;
                if(saved.prefixBytes>receiver.resumeOffset())throw new IOException("saved recording range prefix is unavailable");
                if(device.nonce==saved.nonce&&device.first==saved.firstSector&&device.end==saved.endSector){
                    if(device.pending){frontier=saved.firstSector;resume=saved;}
                    else{saved.confirmOwned(directory,sync);frontier=saved.endSector;}
                }else if(!saved.confirmed&&!device.pending&&device.end==saved.firstSector){
                    frontier=saved.firstSector;resume=saved; // prior write never committed
                }else throw new IOException("device range progress does not match this phone's saved proof; sources retained");
            }else if(device.nonce!=0){
                // A verified complete local original may finish through the
                // unchanged whole-consume path. A fresh phone cannot invent an
                // already-reclaimed prefix from remaining device bytes.
                if(receiver.completeBytesReceived()&&!device.pending){frontier=device.end;completeCopy=true;}
                else throw new IOException("recording has a saved prefix on its original receiver; resume with that saved copy");
            }
        }
        private void settle(boolean wait)throws IOException {
            Pending p=pending;if(p==null)return;
            if(!wait&&p.finished.getCount()!=0)return;
            if(wait)try{p.finished.await();}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("range confirmation interrupted; saved proof retained",e);}
            if(p.error!=null)throw p.error;
            frontier=p.checkpoint.endSector;pending=null;
        }
        /** Called only after the actual PULL was written, or to reconcile a
         * previously complete cached file (which cannot qualify as fresh rate). */
        void progress(SegmentReceiver receiver)throws IOException {
            if(closed)throw new IOException("range receiver is closed");
            settle(false);if(pending!=null||completeCopy)return;
            if(resume!=null){RangeCheckpoint saved=resume;resume=null;pending=new Pending(saved);return;}
            if(receiver.completeBytesReceived())return;
            int available=(int)((receiver.resumeOffset()/248+1)/16);
            // Keep full32K erase runs intact. Sending each4K as soon as it
            // arrives destroys block coalescing and can make physical reclaim
            // slower than the radio, even when the two overlap.
            available=available/8*8;
            if(available<=frontier)return;
            long token;do{token=nonce.getAsLong();}while(token==lastNonce);
            long began=System.nanoTime();
            RangeCheckpoint saved=receiver.checkpointRange(directory,frontier,available,token,sync);
            RecordingTransferMetrics m=metrics;if(m!=null)m.rangePrepared(frontier,available,System.nanoTime()-began);
            lastNonce=token;pending=new Pending(saved);
        }
        void finish(SegmentReceiver receiver)throws IOException {
            if(!receiver.completeBytesReceived())throw new IOException("recording range receiver is incomplete");
            receiver.verifyOriginal();
            // Settle only proofs already issued (including a durable proof
            // recovered after disconnect). The unchanged whole CRA2 request
            // owns the final tail and the terminal receipt. A fresh final
            // range here would erase the tail once, then run CRA2 again.
            if(resume!=null){RangeCheckpoint saved=resume;resume=null;pending=new Pending(saved);}
            settle(true);
        }
        @Override public void close(){
            if(closed)return;closed=true;Pending p=pending;if(p==null)return;
            // Retain the receiver's file lock until its worker has actually
            // stopped; a cancelled Future alone would not prove that.
            p.thread.interrupt();boolean interrupted=false;
            while(p.finished.getCount()!=0)try{p.finished.await();}catch(InterruptedException e){interrupted=true;}
            if(interrupted)Thread.currentThread().interrupt();
        }
    }
    Session open(Path directory,RecorderWire.Descriptor d,SegmentReceiver receiver)throws IOException {
        long used=(((d.encodedLength+247)/248+1)*256+4095)/4096;
        if(used<16&&!RangeCheckpoint.exists(directory,d)){
            // Less than two blocks leaves too little radio work to hide a
            // separate durable range transaction. Whole consume can coalesce
            // the final erase even when the reservation is unaligned. Preserve existing
            // partial proofs: those must still reconcile their exact frontier.
            RecordingTransferMetrics m=metrics;if(m!=null)m.rangeShortWholeFallback();
            return null;
        }
        try{return new Session(directory,d,receiver);}
        catch(Refused busy){
            // A read-only probe may find live capture or its existing NOR
            // owner. Preserve the established live/whole-consume path; no
            // destructive range request has been issued by this constructor.
            if(busy.result==4)return null;
            throw busy;
        }
    }
}
