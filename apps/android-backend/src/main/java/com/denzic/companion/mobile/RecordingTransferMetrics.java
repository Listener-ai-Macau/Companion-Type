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
    private long firstConnectNanos,firstDirectoryDelayNanos=-1,reconnectStartedNanos,maxReconnectDirectoryDelayNanos=-1;
    private int connectionAttempts,connectionsEstablished,reconnectSequences,unexpectedDisconnections,reusedConnections,reusedCatalogues;
    private int directoryRequests,directoryPages,streamDirectoryRequests;
    private boolean stoppedBatchHintRequested,stoppedBatchHintAccepted;
    private boolean centralHighPriorityRequested,centralHighPriorityRequestAccepted;
    private boolean reconnectPending;
    RecordingTransferMetrics(){this(System::nanoTime);}
    RecordingTransferMetrics(Clock clock){this.clock=clock;}

    final class Segment {
        final long length,initialOffset,recordingId,index;
        long highOffset;
        long firstWindow,verifiedAt,receiptAt;
        long consumeReadyAt=-1,consumeSentAt=-1,consumeReceivedAt=-1;
        long pullWrittenAt=-1,firstPayloadAt=-1,lastPayloadAt=-1;
        boolean verified,windowStarted,receiptConfirmed;
        Segment(RecorderWire.Descriptor d,long initialOffset){this.length=d.encodedLength;this.initialOffset=initialOffset;this.highOffset=initialOffset;this.recordingId=d.recordingId;this.index=d.segmentIndex;}
        void accepted(long offset){synchronized(RecordingTransferMetrics.this){
            if(offset<0||offset>length){valid=false;return;}
            if(offset>highOffset){
                if(firstPayloadAt<0)firstPayloadAt=clock.nanoTime();
                if(offset==length)lastPayloadAt=clock.nanoTime();
                highOffset=offset;
            }
        }}
        void pullWritten(){synchronized(RecordingTransferMetrics.this){if(pullWrittenAt<0)pullWrittenAt=clock.nanoTime();}}
        void verified(){synchronized(RecordingTransferMetrics.this){if(!verified)verifiedAt=clock.nanoTime();verified=true;highOffset=length;}}
    }
    synchronized void initialSync(boolean freshSelection,boolean terminalAvailable){
        if(initialSync)return;
        initialSync=true;fresh&=freshSelection;liveFollow=!terminalAvailable;
    }
    synchronized Segment segment(RecorderWire.Descriptor d,long offset){
        String key=SegmentReceiver.key(d);Segment s=segments.get(key);
        if(s==null){s=new Segment(d,offset);segments.put(key,s);if(offset>0)fresh=false;}
        if(offset<0||offset>d.encodedLength||s.length!=d.encodedLength)valid=false;
        return s;
    }
    synchronized void window(Segment segment){
        long now=clock.nanoTime();
        if(!started){firstWindowNanos=now;started=true;}
        if(!segment.windowStarted){segment.firstWindow=now;segment.windowStarted=true;}
        windows++;
    }
    synchronized void confirmed(RecorderWire.Descriptor d){
        Segment segment=segments.get(SegmentReceiver.key(d));
        if(segment!=null&&!segment.receiptConfirmed){segment.receiptAt=clock.nanoTime();segment.receiptConfirmed=true;}
    }
    synchronized void connecting(){if(connectionAttempts++==0)firstConnectNanos=clock.nanoTime();}
    synchronized void connected(){connectionsEstablished++;}
    synchronized void reusedConnection(){reusedConnections++;}
    synchronized void reusedCatalogue(){reusedCatalogues++;}
    synchronized void directoryRequest(boolean streaming){directoryRequests++;if(streaming)streamDirectoryRequests++;}
    synchronized void directoryPage(){directoryPages++;}
    synchronized void stoppedBatchHint(boolean accepted){stoppedBatchHintRequested=true;stoppedBatchHintAccepted=accepted;}
    synchronized void centralPriority(boolean accepted){centralHighPriorityRequested=true;centralHighPriorityRequestAccepted=accepted;}
    synchronized void consumeStage(RecorderWire.Descriptor d,int stage){
        Segment s=segments.get(SegmentReceiver.key(d));if(s==null)return;
        long now=clock.nanoTime();if(stage==0)s.consumeReadyAt=now;else if(stage==1)s.consumeSentAt=now;else if(stage==2)s.consumeReceivedAt=now;
    }
    synchronized void connectionClosed(boolean unexpected){if(unexpected)unexpectedDisconnections++;}
    synchronized void reconnecting(){if(!reconnectPending){reconnectPending=true;reconnectStartedNanos=clock.nanoTime();reconnectSequences++;}}
    synchronized void directoryAvailable(){
        long now=clock.nanoTime();
        if(firstDirectoryDelayNanos<0&&connectionAttempts>0){firstDirectoryDelayNanos=now-firstConnectNanos;if(firstDirectoryDelayNanos<0)valid=false;}
        if(reconnectPending){long elapsed=now-reconnectStartedNanos;if(elapsed<0)valid=false;else maxReconnectDirectoryDelayNanos=Math.max(maxReconnectDirectoryDelayNanos,elapsed);reconnectPending=false;}
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
        StringBuilder trace=new StringBuilder("[");
        for(Segment s:segments.values()){
            if(trace.length()>1)trace.append(',');
            trace.append("{\"recordingId\":").append(s.recordingId).append(",\"index\":").append(s.index)
                .append(",\"windowExpectedNewBytes\":").append(Math.max(0,s.length-s.initialOffset))
                .append(",\"windowVerifiedNewBytes\":").append(s.verified?Math.max(0,s.length-s.initialOffset):0)
                .append(",\"windowAcceptedNewBytes\":").append(Math.max(0,s.highOffset-s.initialOffset))
                .append(",\"windowStartedNanos\":").append(s.windowStarted?Long.toString(s.firstWindow):"null")
                .append(",\"pullWriteCompletedNanos\":").append(s.pullWrittenAt>=0?Long.toString(s.pullWrittenAt):"null")
                .append(",\"firstPayloadAcceptedNanos\":").append(s.firstPayloadAt>=0?Long.toString(s.firstPayloadAt):"null")
                .append(",\"lastPayloadAcceptedNanos\":").append(s.lastPayloadAt>=0?Long.toString(s.lastPayloadAt):"null")
                .append(",\"originalVerifiedNanos\":").append(s.verified?Long.toString(s.verifiedAt):"null")
                .append(",\"consumeLocalReadyNanos\":").append(s.consumeReadyAt>=0?Long.toString(s.consumeReadyAt):"null")
                .append(",\"consumeWriteCompletedNanos\":").append(s.consumeSentAt>=0?Long.toString(s.consumeSentAt):"null")
                .append(",\"consumeReplyReceivedNanos\":").append(s.consumeReceivedAt>=0?Long.toString(s.consumeReceivedAt):"null")
                .append(",\"receiptDurableNanos\":").append(s.receiptConfirmed?Long.toString(s.receiptAt):"null").append('}');
        }
        trace.append(']');
        return "{\"schema\":\"companion.android.recording-transfer-metrics.v1\",\"timingBasis\":\"host_monotonic_nanos\",\"mode\":\""+
            (liveFollow?"live_follow":"stopped_batch")+"\",\"complete\":"+complete+",\"valid\":"+valid+
            ",\"freshSelection\":"+fresh+",\"integrityRetry\":"+integrityRetry+",\"dataWindows\":"+windows+
            ",\"firstWindowNanos\":"+(started?Long.toString(firstWindowNanos):"null")+
            ",\"completedNanos\":"+(complete?Long.toString(completedNanos):"null")+
            ",\"durationNanos\":"+(nanos==null?"null":nanos.toString())+
            ",\"verifiedNewBytes\":"+verified+",\"acceptedNewBytes\":"+accepted+",\"initialCachedBytes\":"+cached+
            ",\"confirmedKiBps\":"+(rate==null?"null":Double.toString(rate))+
            ",\"connectionAttempts\":"+connectionAttempts+",\"connectionsEstablished\":"+connectionsEstablished+",\"reusedConnections\":"+reusedConnections+",\"reusedCatalogues\":"+reusedCatalogues+
            ",\"directoryRequests\":"+directoryRequests+",\"directoryPages\":"+directoryPages+",\"streamDirectoryRequests\":"+streamDirectoryRequests+
            ",\"stoppedBatchHintRequested\":"+stoppedBatchHintRequested+",\"stoppedBatchHintAccepted\":"+stoppedBatchHintAccepted+
            ",\"centralHighPriorityRequested\":"+centralHighPriorityRequested+",\"centralHighPriorityRequestAccepted\":"+centralHighPriorityRequestAccepted+
            ",\"reconnectSequences\":"+reconnectSequences+",\"unexpectedDisconnections\":"+unexpectedDisconnections+
            ",\"firstPrivateDirectoryDelayNanos\":"+(firstDirectoryDelayNanos<0?"null":Long.toString(firstDirectoryDelayNanos))+
            ",\"maxReconnectDirectoryDelayNanos\":"+(maxReconnectDirectoryDelayNanos<0?"null":Long.toString(maxReconnectDirectoryDelayNanos))+
            ",\"segments\":"+trace+
            ",\"endpoint\":\"Before first actual PULL write through terminal session with all exact device receipts and local durable originals verified; no reclaim/backpressure/reconnect wait removed\"}";
    }
}
