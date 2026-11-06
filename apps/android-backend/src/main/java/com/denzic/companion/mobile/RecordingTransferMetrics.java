package com.denzic.companion.mobile;

import java.util.LinkedHashMap;
import java.util.Map;

/** Observations only. Never changes a packet, retry, receipt or file operation.
 * One instance belongs to one foreground-service task across GATT reconnects. */
final class RecordingTransferMetrics {
    interface Clock {long nanoTime();}
    private final Clock clock;
    private final Map<String,Segment> segments=new LinkedHashMap<>();
    private boolean initialSync,started,complete,valid=true,fresh=true,liveFollow,integrityRetry;
    private long firstWindowNanos,completedNanos,windows;
    RecordingTransferMetrics(){this(System::nanoTime);}
    RecordingTransferMetrics(Clock clock){this.clock=clock;}

    final class Segment {
        final long length,initialOffset;
        long highOffset;
        boolean verified;
        Segment(long length,long initialOffset){this.length=length;this.initialOffset=initialOffset;this.highOffset=initialOffset;}
        void accepted(long offset){synchronized(RecordingTransferMetrics.this){
            if(offset<0||offset>length){valid=false;return;}
            highOffset=Math.max(highOffset,offset);
        }}
        void verified(){synchronized(RecordingTransferMetrics.this){verified=true;highOffset=length;}}
    }
    synchronized void initialSync(boolean freshSelection,boolean terminalAvailable){
        if(initialSync)return;
        initialSync=true;fresh&=freshSelection;liveFollow=!terminalAvailable;
    }
    synchronized Segment segment(RecorderWire.Descriptor d,long offset){
        String key=SegmentReceiver.key(d);Segment s=segments.get(key);
        if(s==null){s=new Segment(d.encodedLength,offset);segments.put(key,s);if(offset>0)fresh=false;}
        if(offset<0||offset>d.encodedLength||s.length!=d.encodedLength)valid=false;
        return s;
    }
    synchronized void window(){
        if(!started){firstWindowNanos=clock.nanoTime();started=true;}
        windows++;
    }
    synchronized void integrityRetry(){integrityRetry=true;}
    synchronized void completed(){
        if(complete)return;
        completedNanos=clock.nanoTime();complete=true;
        if(started&&completedNanos-firstWindowNanos<=0)valid=false;
    }
    synchronized String json(){
        long verified=0,accepted=0,cached=0;
        for(Segment s:segments.values()){
            cached+=s.initialOffset;
            accepted+=Math.max(0,s.highOffset-s.initialOffset);
            if(s.verified)verified+=Math.max(0,s.length-s.initialOffset);
        }
        Long nanos=started&&complete&&valid?completedNanos-firstWindowNanos:null;
        Double rate=nanos!=null&&verified>0?verified/1024.0/(nanos/1_000_000_000.0):null;
        return "{\"schema\":\"companion.android.recording-transfer-metrics.v1\",\"timingBasis\":\"host_monotonic_nanos\",\"mode\":\""+
            (liveFollow?"live_follow":"stopped_batch")+"\",\"complete\":"+complete+",\"valid\":"+valid+
            ",\"freshSelection\":"+fresh+",\"integrityRetry\":"+integrityRetry+",\"dataWindows\":"+windows+
            ",\"firstWindowNanos\":"+(started?Long.toString(firstWindowNanos):"null")+
            ",\"completedNanos\":"+(complete?Long.toString(completedNanos):"null")+
            ",\"durationNanos\":"+(nanos==null?"null":nanos.toString())+
            ",\"verifiedNewBytes\":"+verified+",\"acceptedNewBytes\":"+accepted+",\"initialCachedBytes\":"+cached+
            ",\"confirmedKiBps\":"+(rate==null?"null":Double.toString(rate))+
            ",\"endpoint\":\"Before first actual PULL write through terminal session with all exact device receipts and local durable originals verified; no reclaim/backpressure/reconnect wait removed\"}";
    }
}
