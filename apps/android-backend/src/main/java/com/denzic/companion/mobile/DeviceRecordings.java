package com.denzic.companion.mobile;

import java.io.IOException;
import java.util.*;
import static com.denzic.companion.mobile.RecorderWire.*;

/** Catalogue-only session rows and the firmware's exact CDS3 removal protocol. */
public final class DeviceRecordings {
    private DeviceRecordings() {}
    public static final class Session {
        public final Descriptor representative;
        public final long startedUnixSeconds,durationMillis,bytes;
        public final int segments;
        public final boolean complete;
        private Session(List<Descriptor> entries) {
            entries.sort(Comparator.comparingLong(d->d.segmentIndex));representative=entries.get(0);
            long date=0,duration=0,size=0,total=0;boolean contiguous=true,recovered=false;int expected=0;
            for(Descriptor d:entries) {
                if(d.segmentIndex==0)date=d.startedUnixSeconds;
                duration+=d.sampleCount/16;size+=d.encodedLength;
                if(d.segmentIndex!=expected++)contiguous=false;
                if((d.flags&2)!=0)total=d.totalSegments;
                if((d.flags&4)!=0)recovered=true;
            }
            startedUnixSeconds=date;durationMillis=duration;bytes=size;segments=entries.size();complete=contiguous&&total==segments&&!recovered;
        }
    }
    public static List<Session> group(List<Descriptor> entries) {
        Map<String,List<Descriptor>> groups=new LinkedHashMap<>();
        for(Descriptor d:entries) {
            if(d.sourceMode!=1)continue;
            String k=Arrays.toString(d.uid())+":"+Long.toUnsignedString(d.epoch)+":"+Long.toUnsignedString(d.sessionId);
            groups.computeIfAbsent(k,unused->new ArrayList<>()).add(d);
        }
        List<Session> out=new ArrayList<>();for(List<Descriptor> group:groups.values())out.add(new Session(group));
        Collections.reverse(out);return out;
    }
    public static final class Offer {
        final byte[] wire;
        public final long sessionId,startedUnixSeconds,durationMillis,encodedBytes,releasableBytes;
        public final int segments;
        private Offer(byte[] p,Descriptor selected,long request)throws IOException {
            if(p==null||p.length!=96||!magic(p,0,"CDS3")||u8(p,4)!=1||u8(p,5)!=0||u32(p,8)!=request||u32(p,92)!=crc(p,0,92))throw new IOException("设备删除预览无效");
            long slots=u64(p,44),samples=u64(p,52);segments=u8(p,7);
            if(!Arrays.equals(Arrays.copyOfRange(p,16,28),selected.uid())||u64(p,28)!=selected.epoch||u64(p,36)!=selected.sessionId)throw new IOException("录音身份已变化，请刷新目录");
            if(u32(p,12)==0||u8(p,6)>=64||(slots&(1L<<u8(p,6)))==0||segments==0||Long.bitCount(slots)!=segments||samples<=0||samples%320!=0||u32(p,60)==0||u32(p,64)<u32(p,60)||u32(p,68)==0||u32(p,72)==0||u32(p,72)%4096!=0||u32(p,80)==0xffffffffL||(u32(p,84)==0&&u32(p,88)==0))throw new IOException("设备删除预览字段无效");
            wire=p.clone();sessionId=selected.sessionId;startedUnixSeconds=u32(p,76);durationMillis=samples/16;encodedBytes=u32(p,68);releasableBytes=u32(p,72);
        }
        byte[] decision(boolean accepted,long elapsedMillis)throws IOException {
            if(accepted&&elapsedMillis>=50000)throw new IOException("删除确认已过期，请重新选择录音");
            byte[] p=wire.clone();p[4]=(byte)(accepted?2:3);put32(p,92,crc(p,0,92));return p;
        }
        void receipt(byte[] p,int op)throws IOException {
            byte[] expected=wire.clone();expected[4]=(byte)op;expected[5]=2;put32(expected,92,crc(expected,0,92));
            if(!Arrays.equals(p,expected))throw new IOException("删除结果未确认，请刷新设备录音核对");
        }
    }
    public interface Confirm {boolean approve(Offer offer)throws IOException;}
    static byte[] selection(Descriptor selected,long request)throws IOException {
        if(selected==null||request==0)throw new IOException("请选择录音");
        byte[] p=new byte[96];System.arraycopy(new byte[]{'C','D','S','3'},0,p,0,4);p[4]=1;put32(p,8,request);
        System.arraycopy(selected.uid(),0,p,16,12);put64(p,28,selected.epoch);put64(p,36,selected.sessionId);put32(p,92,crc(p,0,92));return p;
    }
    static byte[] response(RecordingClient.Link link,long request,int op,long seconds)throws IOException {
        long deadline=System.nanoTime()+seconds*1_000_000_000L;
        while(true) {
            long remaining=(deadline-System.nanoTime())/1_000_000L;if(remaining<=0)throw new IOException("设备操作结果尚未确认，请刷新目录");
            byte[] p;
            try {p=link.await(RecordingClient.RECORDING_CONSUME,Math.min(remaining,8000));}
            catch(java.net.SocketTimeoutException e){continue;}
            if(p.length==16&&magic(p,0,"CDX3")&&u32(p,4)==request&&u32(p,12)==crc(p,0,12))throw new IOException("设备尚未就绪或录音已变化，请刷新后重试");
            if(p.length!=96||!magic(p,0,"CDS3")||u8(p,4)!=op||u32(p,8)!=request||u32(p,12)==0)continue;
            if(u8(p,5)==3)throw new IOException("设备拒绝删除，目录或设备状态已变化");
            if(op!=1&&u8(p,5)!=2)continue;
            return p;
        }
    }
    static boolean delete(RecordingClient.Link link,Descriptor selected,long request,Confirm confirm)throws IOException {
        link.subscribe(RecordingClient.RECORDING_CONSUME);
        byte[] preview=selection(selected,request);link.write(RecordingClient.RECORDING_CONSUME,preview);
        Offer offer=new Offer(response(link,request,1,20),selected,request);long issued=System.nanoTime();
        boolean accepted=confirm.approve(offer);byte[] decision=offer.decision(accepted,(System.nanoTime()-issued)/1_000_000L);
        link.write(RecordingClient.RECORDING_CONSUME,decision);
        offer.receipt(response(link,request,accepted?2:3,accepted?600:20),accepted?2:3);
        return accepted;
    }
}
