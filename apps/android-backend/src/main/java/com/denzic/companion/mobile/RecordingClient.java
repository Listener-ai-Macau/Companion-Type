package com.denzic.companion.mobile;

import java.io.Closeable;
import java.io.IOException;
import java.nio.file.Path;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

/** Worker-thread backend for reading Companion V2 recordings through a GATT link. */
public final class RecordingClient implements Closeable {
    public static final UUID DEVICE_STATUS=uuid("1001"),RECORDING_CONTROL=uuid("3001"),RECORDING_LIST=uuid("3002"),RECORDING_PULL=uuid("3003"),RECORDING_CONSUME=uuid("6001"),MEETING_CONTROL=uuid("8001"),MEETING_STATUS=uuid("8002");
    private static UUID uuid(String value){return UUID.fromString("8f7a"+value+"-7b7d-4f3d-9d6f-6c2d1b7c0000");}
    /** One connected, encrypted device. Operations are serialized by this client. */
    public interface Link extends Closeable {
        int mtu();
        default boolean calendarSupported() {return false;}
        byte[] read(UUID characteristic) throws IOException;
        void subscribe(UUID characteristic) throws IOException;
        void write(UUID characteristic,byte[] value) throws IOException;
        byte[] await(UUID characteristic,long timeoutMillis) throws IOException;
        /** Stable address of the user-selected paired device. */
        default String deviceAddress() throws IOException {throw new IOException("device address unavailable");}
    }
    public interface Progress { void onBytes(long received,long total); }
    public interface SessionProgress { void onSegment(int index,int count,long received,long total); }
    /** Device-reported observations; absence of a flag is not proof old audio is intact. */
    public static final class DeviceStatus {
        public final int faultBitmap;
        public final boolean previousRecordingDamageReported;
        private DeviceStatus(int faults){faultBitmap=faults;previousRecordingDamageReported=(faults&0x0800)!=0;}
    }
    private final Link link;private final RecorderWire.Peer peer;private final DurableConsume durableConsume;private final SecureRandom random=new SecureRandom();private final Object liveControlLock=new Object();
    private List<RecorderWire.Descriptor> current;private final AtomicBoolean closed=new AtomicBoolean();
    private long nonce(){long n;do{n=random.nextInt()&0xffffffffL;}while(n==0);return n;}

    /** The caller first establishes the user's selected, bonded device link. */
    public RecordingClient(Link link) throws IOException {this(link,null,null);}
    RecordingClient(Link link,DurableConsume.DirectorySync directorySync,DurableConsume.PrefixCheck prefixCheck) throws IOException {
        if(link==null)throw new IllegalArgumentException("link required");this.link=link;
        if((directorySync==null)!=(prefixCheck==null))throw new IllegalArgumentException("both test dependencies are required");
        boolean ready=false;
        try {
            link.subscribe(RECORDING_CONTROL);link.subscribe(RECORDING_LIST);link.subscribe(RECORDING_PULL);
            peer=readPublishedPeer(link);
            byte[] request=peer.negotiate(nonce(),link.mtu());link.write(RECORDING_CONTROL,request);
            long deadline=System.nanoTime()+8_000_000_000L;
            while(true){long remaining=(deadline-System.nanoTime())/1_000_000L;if(remaining<=0)throw new java.net.SocketTimeoutException("recording negotiation timed out");if(Arrays.equals(request,link.await(RECORDING_CONTROL,remaining)))break;}
            durableConsume=directorySync==null&&prefixCheck==null?new DurableConsume(peer,link):new DurableConsume(peer,link,directorySync,prefixCheck);
            ready=true;
        } finally {if(!ready)link.close();}
    }
    static RecorderWire.Peer readPublishedPeer(Link link) throws IOException {
        long deadline=System.nanoTime()+2_500_000_000L;byte[] uid=null;
        while(System.nanoTime()<deadline){
            byte[] status=link.read(DEVICE_STATUS);
            if(status==null||status.length==0)throw new RecordingSyncRunner.LinkFailure("empty device status");
            int schema=status[0]&255;if(schema!=0&&schema!=1)throw new IOException("unsupported device status");
            if(schema==1&&status.length>=20){
                if((status[12]&255)!=0x55||(status[13]&255)!=0x41||(status[14]&255)!=0x42||(status[15]&255)!=0x57)throw new IOException("device does not publish Companion recording capability");
                if(status.length>=36){byte[] observed=Arrays.copyOfRange(status,20,32);boolean zeros=true,ones=true;for(byte b:observed){zeros&=b==0;ones&=(b&255)==255;}if(zeros||ones)throw new IOException("invalid Companion device identity");if(uid!=null&&!Arrays.equals(uid,observed))throw new IOException("device identity changed while reading capability");uid=observed;}
                if(status.length>=116)return RecorderWire.Peer.fromStatus(status);
            }
            try{Thread.sleep(120);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("device status wait interrupted",e);}
        }
        throw new RecordingSyncRunner.LinkFailure("device recording capability is not ready; try again after reconnecting");
    }
    private void ensureOpen() throws IOException {if(closed.get())throw new IOException("device connection is closed");}

    /** Read the current device observation without changing recordings or device state. */
    public synchronized DeviceStatus readDeviceStatus() throws IOException {
        ensureOpen();byte[] status=link.read(DEVICE_STATUS);RecorderWire.Peer observed=RecorderWire.Peer.fromStatus(status);
        if(!Arrays.equals(peer.uid(),observed.uid())||peer.epoch!=observed.epoch)throw new IOException("device identity changed; reconnect before checking status");
        return new DeviceStatus((status[2]&255)|((status[3]&255)<<8));
    }

    /** Explicit user-initiated recording control; use one stable host session ID for retries. */
    public synchronized String control(Path privateDirectory,String hostSession,NativeRecordingControl.Action action,int maxSeconds) throws IOException {
        ensureOpen();return NativeRecordingControl.execute(link,privateDirectory,hostSession,action,maxSeconds);
    }
    /** Existing session control during a streamed download on the same GATT connection.
     * The link serializes GATT operations and receives pull notifications separately.
     * START is excluded because it also uses the recording catalogue channel. */
    String controlDuringSync(Path privateDirectory,String hostSession,NativeRecordingControl.Action action,int maxSeconds) throws IOException {
        if(action==null||action==NativeRecordingControl.Action.START)throw new IOException("请先停止同步，再开始新的录音");
        synchronized(liveControlLock){ensureOpen();return NativeRecordingControl.execute(link,privateDirectory,hostSession,action,maxSeconds);}
    }
    String controlSessionsDuringSync(Path privateDirectory) throws IOException {
        synchronized(liveControlLock){ensureOpen();return NativeRecordingControl.list(link,privateDirectory);}
    }
    /** Find saved recording-control sessions, including any operation awaiting confirmation. */
    public synchronized String controlSessions(Path privateDirectory) throws IOException {
        ensureOpen();return NativeRecordingControl.list(link,privateDirectory);
    }
    /** Bind an existing, verified physical-button capture without sending another START. */
    public synchronized String adoptLocalControl(Path privateDirectory) throws IOException {
        ensureOpen();return NativeRecordingControl.adopt(link,privateDirectory);
    }
    /** Recover a previously confirmed capture from its complete sealed device directory. */
    public synchronized String reconcileControlFromDirectory(Path privateDirectory,String hostSession) throws IOException {
        ensureOpen();return NativeRecordingControl.reconcile(this,link,privateDirectory,hostSession,null);
    }
    /** Also use fully verified copies previously received into this private recording directory. */
    public synchronized String reconcileControlFromDirectory(Path privateDirectory,String hostSession,Path recordingDirectory) throws IOException {
        ensureOpen();if(recordingDirectory==null)throw new IllegalArgumentException("recording directory required");
        return NativeRecordingControl.reconcile(this,link,privateDirectory,hostSession,recordingDirectory);
    }

    public synchronized List<RecorderWire.Descriptor> listRecordings() throws IOException {
        ensureOpen();current=null;RecorderWire.Catalog catalog=new RecorderWire.Catalog(peer,nonce());
        catalog.calendar(link.calendarSupported());
        while(!catalog.complete()){
            link.write(RECORDING_CONTROL,catalog.request());long deadline=System.nanoTime()+8_000_000_000L;
            while(true){long remaining=(deadline-System.nanoTime())/1_000_000L;if(remaining<=0)throw new java.net.SocketTimeoutException("recording directory timed out");if(catalog.accept(link.await(RECORDING_LIST,remaining)))break;}
        }
        current=catalog.entries();return current;
    }

    public synchronized List<DeviceRecordings.Session> listDeviceSessions() throws IOException {
        ensureOpen();return DeviceRecordings.group(listRecordings());
    }
    public synchronized boolean deleteDeviceSession(RecorderWire.Descriptor selected,DeviceRecordings.Confirm confirm) throws IOException {
        ensureOpen();peer.validate(selected);
        if(confirm==null)throw new IllegalArgumentException("confirmation required");
        return DeviceRecordings.delete(link,selected,nonce(),confirm);
    }
    public synchronized DeviceMaintenance.Status maintainDevice(DeviceMaintenance.Operation operation)throws IOException {
        ensureOpen();return DeviceMaintenance.perform(link,operation,nonce());
    }

    /** Receive every currently sealed segment of the selected original session.
     * Reconnect and call again with the same descriptor to resume partial files.
     * A live session without its terminal segment remains INCOMPLETE. */
    public synchronized RecordingLibrary.Session receiveSession(RecorderWire.Descriptor selected,Path privateDirectory,SessionProgress progress) throws IOException {
        ensureOpen();if(selected==null||privateDirectory==null)throw new IllegalArgumentException("recording and private directory required");
        peer.validate(selected);
        List<RecorderWire.Descriptor> entries=listRecordings();java.util.ArrayList<RecorderWire.Descriptor> matches=new java.util.ArrayList<>();
        for(RecorderWire.Descriptor d:entries)if(d.sessionId==selected.sessionId)matches.add(d);
        matches.sort(java.util.Comparator.comparingLong(d->d.segmentIndex));
        RecorderWire.Descriptor previous=null;
        for(RecorderWire.Descriptor d:matches){
            if(d.sourceMode!=selected.sourceMode||(d.segmentIndex==selected.segmentIndex&&!d.sameContent(selected)))throw new IOException("recording session identity changed; originals retained");
            if(previous!=null&&(d.segmentIndex==previous.segmentIndex||(previous.flags&2)!=0||d.sampleOffset<previous.sampleOffset+previous.sampleCount||
                (d.segmentIndex==previous.segmentIndex+1&&d.sampleOffset!=previous.sampleOffset+previous.sampleCount)))throw new IOException("recording session has conflicting segments; originals retained");
            previous=d;
        }
        for(int i=0;i<matches.size();i++){
            final int index=i;RecorderWire.Descriptor d=matches.get(i);
            download(d.recordingId,privateDirectory,progress==null?null:(received,total)->progress.onSegment(index,matches.size(),received,total));
        }
        for(RecordingLibrary.Session session:RecordingLibrary.sessions(privateDirectory,selected)){
            RecorderWire.Descriptor first=session.segments.get(0).descriptor;
            if(first.sessionId==selected.sessionId&&first.epoch==selected.epoch&&Arrays.equals(first.uid(),selected.uid())){
                for(RecordingLibrary.Entry entry:session.segments){RecorderWire.Descriptor d=entry.descriptor;
                    if(d.sourceMode!=selected.sourceMode||(d.segmentIndex==selected.segmentIndex&&!d.sameContent(selected)))throw new IOException("local recording session identity changed; originals retained");
                }
                return session;
            }
        }
        throw new IOException("selected recording has no available sealed segments");
    }

    /**
     * Receive and durably save each sealed segment of the selected original
     * recording, then request an exact device receipt one segment at a time.
     * A lost reply remains pending and is reconciled before any later segment.
     */
    public synchronized RecordingLibrary.Session syncAvailableAndReclaim(RecorderWire.Descriptor selected,Path privateDirectory,SessionProgress progress) throws IOException {
        ensureOpen();if(selected==null||privateDirectory==null)throw new IllegalArgumentException("recording and private directory required");
        peer.validate(selected);durableConsume.reconcilePending(privateDirectory,selected);
        List<RecorderWire.Descriptor> entries=listRecordings();java.util.ArrayList<RecorderWire.Descriptor> matches=new java.util.ArrayList<>();
        for(RecorderWire.Descriptor d:entries)if(d.sessionId==selected.sessionId)matches.add(d);
        matches.sort(java.util.Comparator.comparingLong(d->d.segmentIndex));
        RecorderWire.Descriptor previous=null;boolean selectedOnDevice=false;
        for(RecorderWire.Descriptor d:matches){
            if(d.sourceMode!=selected.sourceMode||(d.segmentIndex==selected.segmentIndex&&!d.sameContent(selected)))
                throw new IOException("recording session identity changed; originals retained");
            if(d.segmentIndex==selected.segmentIndex)selectedOnDevice=true;
            if(previous!=null&&(d.segmentIndex==previous.segmentIndex||(previous.flags&2)!=0||d.sampleOffset<previous.sampleOffset+previous.sampleCount||
                (d.segmentIndex==previous.segmentIndex+1&&d.sampleOffset!=previous.sampleOffset+previous.sampleCount)))
                throw new IOException("recording session has conflicting segments; originals retained");
            previous=d;
        }
        if(!selectedOnDevice)RecordingLibrary.verifiedPrefix(privateDirectory,selected);
        for(int i=0;i<matches.size();i++){
            final int index=i;RecorderWire.Descriptor d=matches.get(i);
            download(d.recordingId,privateDirectory,progress==null?null:(received,total)->progress.onSegment(index,matches.size(),received,total));
            durableConsume.consume(privateDirectory,d);
        }
        for(RecordingLibrary.Session session:RecordingLibrary.sessions(privateDirectory,selected)){
            if(session.segments.isEmpty())continue;
            RecorderWire.Descriptor first=session.segments.get(0).descriptor;
            if(first.sessionId==selected.sessionId&&first.epoch==selected.epoch&&Arrays.equals(first.uid(),selected.uid())){
                if(session.state==RecordingLibrary.SessionState.DAMAGED)throw new IOException("local recording is damaged; originals retained");
                RecordingLibrary.verifiedPrefix(privateDirectory,selected);
                return session;
            }
        }
        throw new IOException("selected recording has no available sealed segments");
    }

    /** Follow without a preset duration; close or interrupt to stop following. */
    public RecordingLibrary.Session followSessionAndReclaim(RecorderWire.Descriptor selected,Path privateDirectory,SessionProgress progress) throws IOException {
        while(true){
            RecordingLibrary.Session session=syncAvailableAndReclaim(selected,privateDirectory,progress);
            RecorderWire.Descriptor last=session.segments.get(session.segments.size()-1).descriptor;
            if((last.flags&2)!=0)return session;
            try{Thread.sleep(2_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("recording follow interrupted; saved audio retained",e);}
        }
    }

    /** Copy a selected sealed segment to app-private storage, retaining the device copy. */
    public synchronized Path download(long recordingId,Path privateDirectory,Progress progress) throws IOException {
        ensureOpen();if(current==null)throw new IOException("read the recording directory first");
        RecorderWire.Descriptor found=null;for(RecorderWire.Descriptor d:current)if(d.recordingId==recordingId){found=d;break;}
        if(found==null)throw new IOException("recording is not in the current directory");
        for(int attempt=0;;attempt++) {
            ensureOpen();
            try(SegmentReceiver receiver=new SegmentReceiver(privateDirectory,found)){
                if(!receiver.completeBytesReceived()){
                    link.write(RECORDING_PULL,peer.pull(found,receiver.resumeOffset()));
                    while(!receiver.completeBytesReceived()){
                        if(Thread.currentThread().isInterrupted())throw new IOException("transfer interrupted; partial copy retained");
                        receiver.accept(link.await(RECORDING_PULL,15_000));
                        if(progress!=null)progress.onBytes(receiver.resumeOffset(),found.encodedLength);
                    }
                }
                return receiver.finish();
            } catch(SegmentReceiver.IntegrityMismatch error) {if(attempt!=0)throw error;}
        }
    }
    /** May be called from another thread to interrupt a pending link operation. */
    @Override public void close() throws IOException {if(closed.compareAndSet(false,true))link.close();}
}
