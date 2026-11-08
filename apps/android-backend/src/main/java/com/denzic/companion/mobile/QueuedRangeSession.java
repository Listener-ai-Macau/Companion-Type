package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.function.LongSupplier;

/** Bounded short-recording handoff. One worker durably prepares and submits
 * subsequent ranges while another waits for exact physical receipts. Immutable
 * per-request proofs survive a disconnect without overwriting their predecessor.
 * Neither worker runs before progress() follows the actual first PULL. */
final class QueuedRangeSession implements RangeConsume.Session {
    private final RangeConsume owner;
    private final RecordingClient.Link link;
    private final RangeCheckpoint.DirectorySync sync;
    private final LongSupplier nonce;
    private final RecordingTransferMetrics metrics;
    private final Path directory;
    private final RecorderWire.Descriptor descriptor;
    private final Object monitor=new Object();
    private final ArrayDeque<Task> prepare=new ArrayDeque<>();
    private final List<Task> outstanding=new ArrayList<>();
    private final Thread sender,receipts;
    private IOException failure;
    private boolean started,sourceDone,senderDone,receiptsDone,prepared,closed;
    private int lastEnd;
    private Task last;
    private RangeCheckpoint preceding;
    private final class Task {
        final int first,end;final long token,created;
        RangeCheckpoint.Save save;
        volatile RangeCheckpoint checkpoint;
        long sentAt;boolean confirmed;
        Task(RangeCheckpoint existing){first=existing.firstSector;end=existing.endSector;token=existing.nonce;created=0;checkpoint=existing;}
        Task(int first,int end,long token,long created){this.first=first;this.end=end;this.token=token;this.created=created;}
    }
    QueuedRangeSession(RangeConsume owner,RecordingClient.Link link,RangeCheckpoint.DirectorySync sync,LongSupplier nonce,
            RecordingTransferMetrics metrics,Path directory,RecorderWire.Descriptor descriptor,SegmentReceiver receiver)throws IOException {
        this.owner=owner;this.link=link;this.sync=sync;this.nonce=nonce;this.metrics=metrics;this.directory=directory;this.descriptor=descriptor;
        List<RangeCheckpoint> saved=RangeCheckpoint.queued(directory,descriptor);
        preceding=RangeCheckpoint.confirmedFrontier(directory,descriptor);lastEnd=preceding==null?0:preceding.endSector;
        RangeConsume.Status device=null;
        for(int attempt=0;;attempt++)try{device=owner.exchange(descriptor,nonce.getAsLong(),null);break;}
        catch(RangeConsume.Refused busy){
            if(saved.isEmpty()||attempt>=49)throw busy;
            try{Thread.sleep(100);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("range recovery interrupted; saved proofs retained",e);}
        }
        if(device.nonce==0){if(lastEnd!=0)throw new IOException("device lost its saved range frontier; originals retained");}
        else{
            RangeCheckpoint match=preceding!=null&&preceding.nonce==device.nonce?preceding:null;
            for(RangeCheckpoint proof:saved)if(proof.nonce==device.nonce)match=proof;
            if(match==null||match.firstSector!=device.first||match.endSector!=device.end)
                throw new IOException("device range does not match this receiver's saved proof; originals retained");
            int done=device.pending?device.first:device.end;
            if(done<lastEnd)throw new IOException("device range frontier moved backwards; originals retained");
            for(RangeCheckpoint proof:saved)if(proof.endSector<=done){proof.confirmQueued(directory,sync);preceding=proof;}
            lastEnd=done;
        }
        for(RangeCheckpoint proof:saved){
            if(proof.endSector<=lastEnd)continue;
            if(proof.firstSector!=lastEnd||proof.prefixBytes>receiver.resumeOffset())throw new IOException("queued original prefix is unavailable; originals retained");
            Task task=new Task(proof);prepare.add(task);outstanding.add(task);last=task;lastEnd=proof.endSector;
        }
        sender=new Thread(this::sendLoop,"Companion-range-submit");receipts=new Thread(this::receiptLoop,"Companion-range-receipts");
        sender.setDaemon(true);receipts.setDaemon(true);
    }
    private void check()throws IOException {if(failure!=null)throw failure;if(closed)throw new IOException("range handoff is closed; saved proofs retained");}
    private void fail(Exception error){synchronized(monitor){if(failure==null)failure=error instanceof IOException?(IOException)error:new IOException("queued range handoff failed; originals retained",error);monitor.notifyAll();}}
    private void start(){if(!started){started=true;sender.start();receipts.start();}}
    private void waitChange()throws IOException {
        try{monitor.wait();}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("range handoff interrupted; saved proofs retained",e);}
    }
    @Override public boolean pipelined(){return true;}
    @Override public void progress(SegmentReceiver receiver)throws IOException {
        synchronized(monitor){
            check();start();if(sourceDone||receiver.completeBytesReceived()||outstanding.size()>=3)return;
            int available=(int)((receiver.resumeOffset()/248+1)/16);
            if(available<=lastEnd)return;
            long token;boolean duplicate;
            do{token=nonce.getAsLong();duplicate=preceding!=null&&preceding.nonce==token;for(Task task:outstanding)duplicate|=task.token==token;}while(duplicate);
            Task previous=last;RangeCheckpoint base=preceding;Task task=new Task(lastEnd,available,token,System.nanoTime());
            task.save=receiver.prepareQueuedRangeCheckpoint(directory,task.first,task.end,task.token,sync,()->previous==null?base:previous.checkpoint);
            last=task;lastEnd=available;prepare.add(task);outstanding.add(task);monitor.notifyAll();
        }
    }
    private void sendLoop(){
        try{
            while(true){
                Task task;
                synchronized(monitor){while(prepare.isEmpty()&&!sourceDone){check();waitChange();}check();if(prepare.isEmpty())return;task=prepare.remove();}
                RangeCheckpoint proof=task.checkpoint;
                if(proof==null)proof=task.save.persist();else proof.resyncQueued(directory,sync);
                if(task.created!=0&&metrics!=null)metrics.rangePrepared(task.first,task.end,System.nanoTime()-task.created);
                synchronized(monitor){check();task.checkpoint=proof;task.sentAt=System.nanoTime();monitor.notifyAll();}
                link.write(RecordingClient.RECORDING_CONSUME,RangeConsume.request(descriptor,task.token,proof));
            }
        }catch(Exception error){fail(error);}
        finally{synchronized(monitor){senderDone=true;monitor.notifyAll();}}
    }
    private void receiptLoop(){
        try{
            while(true){
                long began=0;
                synchronized(monitor){
                    while(true){
                        check();for(Task task:outstanding)if(task.sentAt!=0&&(began==0||task.sentAt<began))began=task.sentAt;
                        if(began!=0)break;if(sourceDone&&senderDone&&outstanding.isEmpty())return;waitChange();
                    }
                }
                long remaining=(15_000_000_000L-(System.nanoTime()-began))/1_000_000L;
                if(remaining<=0)throw new java.net.SocketTimeoutException("queued physical receipt timed out; saved proofs retained");
                byte[] wire=link.await(RecordingClient.RECORDING_CONSUME,remaining);
                if(wire==null||!RecorderWire.magic(wire,0,"CRR3")||wire.length<36)throw new IOException("unexpected queued range receipt; pending originals retained");
                long token=RecorderWire.u32(wire,32);Task matching=null;
                synchronized(monitor){for(Task task:outstanding)if(task.token==token){matching=task;break;}}
                if(matching==null)continue;
                RangeConsume.Status state=RangeConsume.reply(descriptor,token,wire);
                if(state==null||state.pending||state.nonce!=token||state.first!=matching.first||state.end!=matching.end)
                    throw new IOException("device did not physically confirm the exact queued range; saved proof retained");
                synchronized(monitor){if(outstanding.get(0)!=matching)throw new IOException("queued physical receipts arrived out of order; proofs retained");}
                long replied=System.nanoTime();matching.checkpoint.confirmQueued(directory,sync);
                if(metrics!=null)metrics.rangeConfirmed(matching.first,matching.end,replied-matching.sentAt,System.nanoTime()-replied);
                synchronized(monitor){matching.confirmed=true;preceding=matching.checkpoint;outstanding.remove(0);monitor.notifyAll();}
            }
        }catch(Exception error){fail(error);}
        finally{synchronized(monitor){receiptsDone=true;monitor.notifyAll();}}
    }
    @Override public void prepareTerminal(SegmentReceiver receiver)throws IOException {
        receiver.verifyOriginal();
        synchronized(monitor){check();start();sourceDone=true;monitor.notifyAll();while(!senderDone){check();waitChange();}check();prepared=true;}
    }
    @Override public void finish(SegmentReceiver receiver)throws IOException {
        if(!prepared)prepareTerminal(receiver);
        synchronized(monitor){while(!receiptsDone){check();waitChange();}check();if(!outstanding.isEmpty())throw new IOException("queued physical receipts remain pending; proofs retained");}
    }
    @Override public void close(){
        synchronized(monitor){if(closed)return;closed=true;monitor.notifyAll();}
        if(!started)return;sender.interrupt();receipts.interrupt();boolean interrupted=false;
        for(Thread worker:new Thread[]{sender,receipts})while(worker.isAlive())try{worker.join();}catch(InterruptedException e){interrupted=true;}
        if(interrupted)Thread.currentThread().interrupt();
    }
}
