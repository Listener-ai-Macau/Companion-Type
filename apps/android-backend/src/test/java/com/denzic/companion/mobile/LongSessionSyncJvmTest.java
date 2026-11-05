package com.denzic.companion.mobile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.zip.CRC32;

/** More than two hours of synthetic Opus through the real Java/JNI backend. */
public final class LongSessionSyncJvmTest {
    private static final int SEGMENTS=58, FRAMES=6300;
    private static void put16(byte[] p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
    private static void put32(byte[] p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static void put64(byte[] p,int i,long v){for(int n=0;n<8;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static long u32(byte[] p,int i){long n=0;for(int j=0;j<4;j++)n|=(p[i+j]&255L)<<(8*j);return n;}
    private static byte[] audio()throws Exception {
        ByteArrayOutputStream out=new ByteArrayOutputStream();out.write(new byte[]{'C','O','P','1',3,1,20,3,(byte)128,62,0,0});
        int[] opus={184,91,61,13,6,212,119,103,154,112,59,167,214,84,199,215,224,197,21,15,83,26,25,151,74,91,44,201,192,179,8,78,13,165,128,204,28,243,127,83};
        byte[] frame=new byte[42];frame[0]=40;for(int i=0;i<opus.length;i++)frame[i+2]=(byte)opus[i];
        for(int i=0;i<FRAMES;i++)out.write(frame);return out.toByteArray();
    }
    private static RecorderWire.Descriptor descriptor(int index,byte[] audio,byte[] sha,long audioCrc)throws Exception {
        byte[] d=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,d,0,4);put16(d,4,2);put16(d,6,112);
        put32(d,8,41+index);put64(d,12,1);put64(d,20,7);put32(d,28,index);put64(d,32,(long)index*FRAMES*320);put64(d,40,(long)FRAMES*320);
        put32(d,48,audio.length);put32(d,52,audioCrc);System.arraycopy(sha,0,d,56,32);if(index==SEGMENTS-1)put32(d,88,SEGMENTS);
        d[92]=(byte)(index==SEGMENTS-1?3:1);d[93]=3;d[96]=1;CRC32 c=new CRC32();c.update(d,0,108);put32(d,108,c.getValue());return RecorderWire.Descriptor.decode(d);
    }
    private static byte[] status(){
        byte[] s=new byte[116];s[0]=1;put32(s,12,0x57424155L);s[20]=1;System.arraycopy(new byte[]{'C','R','V','2'},0,s,84,4);
        put16(s,88,2);put16(s,90,32);put32(s,92,7);put64(s,96,1);put16(s,104,64);put16(s,106,1024);put16(s,108,248);
        CRC32 c=new CRC32();c.update(s,84,28);put32(s,112,c.getValue());return s;
    }
    private static byte[] packet(RecorderWire.Descriptor d,byte[] raw,int offset,int seq){
        int n=Math.min(190,raw.length-offset);boolean last=offset+n==raw.length;int header=last?56:24;
        byte[] p=new byte[header+n];p[0]=1;p[1]=(byte)(last?1:0);put16(p,2,n);put32(p,4,d.recordingId);put32(p,8,seq);put32(p,12,offset);put32(p,16,raw.length);
        if(last)System.arraycopy(d.sha256(),0,p,24,32);System.arraycopy(raw,offset,p,header,n);
        CRC32 c=new CRC32();c.update(p,4,16);c.update(p,header,n);put32(p,20,c.getValue());return p;
    }
    private static final class Device {
        final LinkedHashMap<Long,RecorderWire.Descriptor> available=new LinkedHashMap<>();
        final LinkedHashMap<Long,byte[]> recent=new LinkedHashMap<>();final byte[] raw;boolean lostOnce,stalledOnce,gattFailedOnce;int consumeWrites,resumedOffset,gattResumedOffset;
        Device(byte[] data){raw=data;}
        void record(byte[] receipt)throws IOException {
            long id=u32(receipt,40);byte[] old=recent.get(id);
            if(old!=null){if(!Arrays.equals(old,receipt))throw new IOException("wrong replay");return;}
            RecorderWire.Descriptor selected=available.get(id);
            if(selected==null||!Arrays.equals(RecorderWire.Peer.fromStatus(status()).consumeReceipt(selected),receipt))
                throw new IOException("not the exact available segment");
            available.remove(id);
            recent.put(id,receipt.clone());if(recent.size()>4)recent.remove(recent.keySet().iterator().next());
        }
    }
    private static final class Link implements RecordingClient.Link {
        final Device device;byte[] control,list,receipt;RecorderWire.Descriptor current;int offset,seq;boolean failReply,disconnected;
        Link(Device device){this.device=device;}
        public int mtu(){return 247;}public byte[] read(UUID id){return status();}public void subscribe(UUID id){}public void close(){}
        public void write(UUID id,byte[] value)throws IOException {
            if(id.equals(RecordingClient.RECORDING_CONTROL)&&value[1]==0x22){control=value.clone();return;}
            if(id.equals(RecordingClient.RECORDING_CONTROL)&&value[1]==0x20){
                List<RecorderWire.Descriptor> rows=new ArrayList<>(device.available.values());int start=(int)u32(value,12),n=Math.min(2,rows.size()-start);
                if(n<0)throw new IOException("bad catalog cursor");list=new byte[24+n*112];list[0]=2;list[1]=(byte)n;put16(list,2,112);put32(list,4,1);put32(list,8,start);put32(list,12,rows.size());System.arraycopy(value,8,list,16,4);
                for(int i=0;i<n;i++)System.arraycopy(rows.get(start+i).wireBytes(),0,list,24+i*112,112);
                CRC32 crc=new CRC32();crc.update(list,0,20);crc.update(list,24,n*112);put32(list,20,crc.getValue());return;
            }
            if(id.equals(RecordingClient.RECORDING_PULL)){
                current=device.available.get(u32(value,4));if(current==null)throw new IOException("segment unavailable");offset=(int)u32(value,28);if(current.recordingId==43&&offset>0)device.resumedOffset=offset;if(current.recordingId==44&&offset>0)device.gattResumedOffset=offset;seq=0;return;
            }
            if(id.equals(RecordingClient.RECORDING_CONSUME)){
                device.consumeWrites++;device.record(value);receipt=value.clone();
                if(u32(value,40)==51&&!device.lostOnce){device.lostOnce=true;failReply=true;}return;
            }
            throw new IOException("unknown test command");
        }
        public byte[] await(UUID id,long timeout)throws IOException {
            if(id.equals(RecordingClient.RECORDING_CONTROL))return control;
            if(id.equals(RecordingClient.RECORDING_LIST))return list;
            if(id.equals(RecordingClient.RECORDING_CONSUME)){if(failReply){failReply=false;disconnected=true;throw new RecordingSyncRunner.LinkFailure("synthetic lost response");}return receipt;}
            if(id.equals(RecordingClient.RECORDING_PULL)){
                if(current.recordingId==43&&offset>600&&!device.stalledOnce){device.stalledOnce=true;throw new java.net.SocketTimeoutException("synthetic stalled notification without disconnect");}
                if(current.recordingId==44&&offset>600&&!device.gattFailedOnce){device.gattFailedOnce=true;throw new RecordingSyncRunner.LinkFailure("synthetic GATT failure without disconnect");}
                byte[] p=packet(current,device.raw,offset,seq++);offset+=Math.min(190,device.raw.length-offset);return p;
            }
            throw new IOException("unknown test notification");
        }
    }
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory(Paths.get(args[0]),"long-session-");byte[] raw=audio(),sha=MessageDigest.getInstance("SHA-256").digest(raw);CRC32 crc=new CRC32();crc.update(raw);
        Device device=new Device(raw);RecorderWire.Descriptor first=null;
        for(int i=0;i<SEGMENTS;i++){RecorderWire.Descriptor d=descriptor(i,raw,sha,crc.getValue());device.available.put(d.recordingId,d);if(first==null)first=d;}
        final RecorderWire.Descriptor selected=first;int[] checks={0};
        DurableConsume.PrefixCheck verify=prefix->{NativeAudio.inspectPrefix(prefix);checks[0]++;};
        final RecordingLibrary.Session[] finished={null};final int[] connections={0},offlineAttempts={0};final long[] elapsed={0};final boolean[] pendingSeen={false};final java.util.List<String> states=new java.util.ArrayList<>();
        RecordingSyncRunner runner=new RecordingSyncRunner(()->{
            connections[0]++;
            if(device.lostOnce&&offlineAttempts[0]++<10)throw new RecordingSyncRunner.LinkFailure("synthetic long disconnect");
            Link link=new Link(device);RecordingClient client=new RecordingClient(link,dir->{},verify);
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync() throws IOException{return client.syncAvailableAndReclaim(selected,root,null);}
                public boolean disconnected(){return link.disconnected;}
                public void close()throws IOException {if(link.disconnected)pendingSeen[0]=Files.isRegularFile(root.resolve(".consume-pending"));client.close();}
            };
        },new RecordingSyncRunner.Listener(){
            public void status(String state,String detail){states.add(state);}
            public void finished(RecordingLibrary.Session session){finished[0]=session;}
        },millis->{elapsed[0]+=millis;});
        runner.run();RecordingLibrary.Session session=finished[0];
        if(!pendingSeen[0]||connections[0]!=14||elapsed[0]<174034||!states.contains("reconnecting")||!device.lostOnce||!device.stalledOnce||device.resumedOffset<=0||!device.gattFailedOnce||device.gattResumedOffset<=0||!device.available.isEmpty()||
           session==null||session.state!=RecordingLibrary.SessionState.COMPLETE||session.segments.size()!=SEGMENTS)
            throw new AssertionError("automatic reconnect did not resolve same-session lost receipt");
        final int[] failedConnections={0};final java.util.List<String> errors=new java.util.ArrayList<>();
        new RecordingSyncRunner(()->{failedConnections[0]++;return new RecordingSyncRunner.Connection(){
            public RecordingLibrary.Session sync()throws IOException{throw new IOException("local file error");}
            public boolean disconnected(){return false;}public void close(){}
        };},new RecordingSyncRunner.Listener(){public void status(String state,String detail){errors.add(state);}
          public void finished(RecordingLibrary.Session s){throw new AssertionError("unexpected success");}},millis->{}).run();
        if(failedConnections[0]!=1||!errors.contains("error"))throw new AssertionError("local error retried as Bluetooth loss");
        NativeAudio.VerifiedPrefix verified=NativeAudio.inspectPrefix(session);
        if(verified.encodedSamples!=(long)SEGMENTS*FRAMES*320||verified.encodedSamples/16000<7200||!verified.captureComplete||checks[0]<SEGMENTS)
            throw new AssertionError("long session sample count or verification changed");
        Path wav=root.resolve("meeting.wav");NativeAudio.Result decoded=NativeAudio.decode(session,wav);
        if(decoded.samples/16000<7200||!decoded.captureComplete||Files.size(wav)!=decoded.samples*2+44)throw new AssertionError("long recording did not decode");
        // Exercise a recording that grows in real time instead of an already sealed catalogue.
        Path liveRoot=Files.createTempDirectory(Paths.get(args[0]),"live-session-");Device live=new Device(raw);
        List<RecorderWire.Descriptor> stages=new ArrayList<>();
        for(int i=0;i<SEGMENTS;i++)stages.add(descriptor(i,raw,sha,crc.getValue()));
        live.available.put(stages.get(0).recordingId,stages.get(0));
        int[] next={1},liveConnections={0};RecordingLibrary.Session[] liveFinished={null};
        RecordingSyncRunner liveRunner=new RecordingSyncRunner(()->{
            liveConnections[0]++;Link link=new Link(live);RecordingClient client=new RecordingClient(link,dir->{},verify);
            return new RecordingSyncRunner.Connection(){
                public RecordingLibrary.Session sync()throws IOException{return client.syncAvailableAndReclaim(stages.get(0),liveRoot,null);}
                public boolean disconnected(){return link.disconnected;}
                public void close()throws IOException{client.close();}
            };
        },new RecordingSyncRunner.Listener(){
            public void status(String state,String detail){
                if(state.equals("following")&&next[0]<stages.size()){
                    if(!live.available.isEmpty())throw new AssertionError("prior live segment was not reclaimed");
                    RecorderWire.Descriptor fresh=stages.get(next[0]++);live.available.put(fresh.recordingId,fresh);
                }
            }
            public void finished(RecordingLibrary.Session result){liveFinished[0]=result;}
        },millis->{});
        liveRunner.run();
        if(next[0]!=SEGMENTS||liveConnections[0]!=4||!live.lostOnce||!live.stalledOnce||live.resumedOffset<=0||!live.gattFailedOnce||live.gattResumedOffset<=0||!live.available.isEmpty()||liveFinished[0]==null||
           liveFinished[0].state!=RecordingLibrary.SessionState.COMPLETE||liveFinished[0].segments.size()!=SEGMENTS||
           NativeAudio.inspectPrefix(liveFinished[0]).encodedSamples/16000<7200)
            throw new AssertionError("live growing session did not survive following and a lost receipt");
        System.out.println("PASS 58 live-arrival segments, stalled notification and GATT failure resume, reconnect and more than two hours of saved audio");
        System.out.println("PASS synthetic continuous seconds="+(decoded.samples/16000)+" segments="+SEGMENTS+" physicalReceipts="+device.consumeWrites+" lostReceiptRecovered=true");
    }
}
