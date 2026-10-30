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
    public static final UUID DEVICE_STATUS=uuid("1001"),RECORDING_CONTROL=uuid("3001"),RECORDING_LIST=uuid("3002"),RECORDING_PULL=uuid("3003");
    private static UUID uuid(String value){return UUID.fromString("8f7a"+value+"-7b7d-4f3d-9d6f-6c2d1b7c0000");}
    /** One connected, encrypted device. Operations are serialized by this client. */
    public interface Link extends Closeable {
        int mtu();
        byte[] read(UUID characteristic) throws IOException;
        void subscribe(UUID characteristic) throws IOException;
        void write(UUID characteristic,byte[] value) throws IOException;
        byte[] await(UUID characteristic,long timeoutMillis) throws IOException;
    }
    public interface Progress { void onBytes(long received,long total); }
    private final Link link;private final RecorderWire.Peer peer;private final SecureRandom random=new SecureRandom();
    private List<RecorderWire.Descriptor> current;private final AtomicBoolean closed=new AtomicBoolean();
    private long nonce(){long n;do{n=random.nextInt()&0xffffffffL;}while(n==0);return n;}

    /** The caller first establishes the user's selected, bonded device link. */
    public RecordingClient(Link link) throws IOException {
        if(link==null)throw new IllegalArgumentException("link required");this.link=link;
        boolean ready=false;
        try {
            link.subscribe(RECORDING_CONTROL);link.subscribe(RECORDING_LIST);link.subscribe(RECORDING_PULL);
            peer=readPublishedPeer(link);
            byte[] request=peer.negotiate(nonce(),link.mtu());link.write(RECORDING_CONTROL,request);
            long deadline=System.nanoTime()+8_000_000_000L;
            while(true){long remaining=(deadline-System.nanoTime())/1_000_000L;if(remaining<=0)throw new IOException("recording negotiation timed out");if(Arrays.equals(request,link.await(RECORDING_CONTROL,remaining)))break;}
            ready=true;
        } finally {if(!ready)link.close();}
    }
    private static RecorderWire.Peer readPublishedPeer(Link link) throws IOException {
        long deadline=System.nanoTime()+2_500_000_000L;byte[] uid=null;
        while(System.nanoTime()<deadline){
            byte[] status=link.read(DEVICE_STATUS);
            if(status==null||status.length==0)throw new IOException("empty device status");
            int schema=status[0]&255;if(schema!=0&&schema!=1)throw new IOException("unsupported device status");
            if(schema==1&&status.length>=20){
                if((status[12]&255)!=0x55||(status[13]&255)!=0x41||(status[14]&255)!=0x42||(status[15]&255)!=0x57)throw new IOException("device does not publish Companion recording capability");
                if(status.length>=36){byte[] observed=Arrays.copyOfRange(status,20,32);boolean zeros=true,ones=true;for(byte b:observed){zeros&=b==0;ones&=(b&255)==255;}if(zeros||ones)throw new IOException("invalid Companion device identity");if(uid!=null&&!Arrays.equals(uid,observed))throw new IOException("device identity changed while reading capability");uid=observed;}
                if(status.length>=116)return RecorderWire.Peer.fromStatus(status);
            }
            try{Thread.sleep(120);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("device status wait interrupted",e);}
        }
        throw new IOException("device recording capability is not ready; try again after reconnecting");
    }
    private void ensureOpen() throws IOException {if(closed.get())throw new IOException("device connection is closed");}

    public synchronized List<RecorderWire.Descriptor> listRecordings() throws IOException {
        ensureOpen();current=null;RecorderWire.Catalog catalog=new RecorderWire.Catalog(peer,nonce());
        while(!catalog.complete()){
            link.write(RECORDING_CONTROL,catalog.request());long deadline=System.nanoTime()+8_000_000_000L;
            while(true){long remaining=(deadline-System.nanoTime())/1_000_000L;if(remaining<=0)throw new IOException("recording directory timed out");if(catalog.accept(link.await(RECORDING_LIST,remaining)))break;}
        }
        current=catalog.entries();return current;
    }

    /** Copy a selected sealed segment to app-private storage, retaining the device copy. */
    public synchronized Path download(long recordingId,Path privateDirectory,Progress progress) throws IOException {
        ensureOpen();if(current==null)throw new IOException("read the recording directory first");
        RecorderWire.Descriptor found=null;for(RecorderWire.Descriptor d:current)if(d.recordingId==recordingId){found=d;break;}
        if(found==null)throw new IOException("recording is not in the current directory");
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
        }
    }
    /** May be called from another thread to interrupt a pending link operation. */
    @Override public void close() throws IOException {if(closed.compareAndSet(false,true))link.close();}
}
