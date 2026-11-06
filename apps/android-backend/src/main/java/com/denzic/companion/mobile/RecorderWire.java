package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.zip.CRC32;

/** Companion sealed-recording V2 wire format; independent of Android UI and GATT. */
public final class RecorderWire {
    private RecorderWire() {}
    private static IOException invalid(String why) { return new IOException("recording protocol: " + why); }
    static int u8(byte[] p, int i) { return p[i] & 255; }
    private static int u16(byte[] p, int i) { return u8(p,i) | (u8(p,i+1) << 8); }
    static long u32(byte[] p, int i) { return (u16(p,i) | ((long)u16(p,i+2) << 16)); }
    static long u64(byte[] p, int i) { return ByteBuffer.wrap(p,i,8).order(ByteOrder.LITTLE_ENDIAN).getLong(); }
    private static void put16(byte[] p,int i,int v) { p[i]=(byte)v;p[i+1]=(byte)(v>>>8); }
    static void put32(byte[] p,int i,long v) { for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n)); }
    static void put64(byte[] p,int i,long v) { for(int n=0;n<8;n++)p[i+n]=(byte)(v>>>(8*n)); }
    static long crc(byte[] p,int start,int length) { CRC32 c=new CRC32();c.update(p,start,length);return c.getValue(); }
    private static boolean uniform(byte[] p,int value) { for(byte b:p)if((b&255)!=value)return false;return true; }
    static boolean magic(byte[] p,int offset,String value) { if(p.length<offset+value.length())return false;for(int i=0;i<value.length();i++)if(p[offset+i]!=(byte)value.charAt(i))return false;return true; }

    public static final class Peer {
        private final byte[] uid;
        public final long epoch;
        public final int capacity, maxValueBytes;
        private Peer(byte[] uid,long epoch,int capacity,int maxValueBytes) {this.uid=uid;this.epoch=epoch;this.capacity=capacity;this.maxValueBytes=maxValueBytes;}
        public byte[] uid() {return uid.clone();}

        /** Require actual V2 publication; an absent suffix is not V1 support. */
        public static Peer fromStatus(byte[] status) throws IOException {
            if(status==null || !magic(status,84,"CRV2")) throw invalid("V2 capability not available");
            if(status.length!=116 || u8(status,0)!=1 || u32(status,12)!=0x57424155L)throw invalid("invalid V2 status");
            int p=84;long caps=u32(status,p+8),epoch=u64(status,p+12);int capacity=u16(status,p+20),max=u16(status,p+24);
            byte[] uid=Arrays.copyOfRange(status,20,32);
            if(u16(status,p+4)!=2 || u16(status,p+6)!=32 || (caps&7)!=7 || (caps&~2047L)!=0 || epoch==0
                    || ((caps&1024)!=0&&(caps&256)==0)
                    || ((caps&512)!=0&&(caps&256)==0) || ((caps&256)!=0&&(caps&192)!=192)
                    || ((caps&128)!=0&&(caps&88)!=88) || ((caps&64)!=0&&(caps&24)!=24)
                    || capacity==0 || capacity>64 || u16(status,p+22)!=1024 || max<248 || max>509
                    || u16(status,p+26)!=0 || uniform(uid,0) || uniform(uid,255)
                    || crc(status,p,28)!=u32(status,p+28)) throw invalid("unsupported or corrupt V2 capability");
            return new Peer(uid,epoch,capacity,max);
        }
        public byte[] negotiate(long nonce,int mtu) throws IOException {
            if(nonce<=0||nonce>0xffffffffL)throw invalid("invalid negotiation nonce");
            if(mtu<139)throw invalid("MTU too small for recording directory");
            byte[] p=new byte[32];p[0]=2;p[1]=0x22;
            if(maxValueBytes>248){int value=Math.min(maxValueBytes,mtu-3);if(value<136)throw invalid("MTU too small");put16(p,2,value);}
            put32(p,4,nonce);System.arraycopy(uid,0,p,8,12);put64(p,20,epoch);put32(p,28,crc(p,0,28));return p;
        }
        public void validate(Descriptor d) throws IOException {
            if(!Arrays.equals(uid,d.uid)||epoch!=d.epoch)throw invalid("descriptor belongs to another device or format epoch");
        }
        public byte[] pull(Descriptor d,long offset) throws IOException {
            validate(d);if(offset<0||offset>=d.encodedLength)throw invalid("invalid pull offset");
            byte[] p=new byte[32];p[0]=2;p[1]=0x21;p[2]=4;put32(p,4,d.recordingId);put64(p,8,epoch);put64(p,16,d.sessionId);put32(p,24,d.segmentIndex);put32(p,28,offset);return p;
        }
        /** Build an exact protected segment receipt; this method sends nothing. */
        byte[] consumeReceipt(Descriptor d) throws IOException {
            if(d==null)throw invalid("missing recording descriptor");validate(d);
            byte[] p=new byte[84];System.arraycopy(new byte[]{'C','R','A','2',2,0,84,0},0,p,0,8);
            System.arraycopy(uid,0,p,8,12);put64(p,20,epoch);put64(p,28,d.sessionId);
            put32(p,36,d.segmentIndex);put32(p,40,d.recordingId);put32(p,44,d.encodedLength);
            System.arraycopy(d.sha,0,p,48,32);put32(p,80,crc(p,0,80));return p;
        }
        /** Accept only the identical full receipt for this protected peer. */
        boolean receiptMatches(Descriptor d,byte[] payload) throws IOException {
            byte[] expected=consumeReceipt(d);
            if(Arrays.equals(expected,payload))return true;
            if(payload!=null && payload.length>=8 && magic(payload,0,"CRA2")) {
                if(payload.length!=84 || u16(payload,4)!=2 || u16(payload,6)!=84 ||
                    !Arrays.equals(Arrays.copyOfRange(payload,8,20),uid) || u64(payload,20)!=epoch || crc(payload,0,80)!=u32(payload,80))
                    throw invalid("invalid physical consume receipt");
            }
            return false;
        }
    }

    public static final class Descriptor {
        private final byte[] uid,sha,wire;
        public final long epoch,sessionId,recordingId,segmentIndex,sampleOffset,sampleCount,encodedLength,contentCrc,totalSegments;
        public final int flags,codec,sourceMode,syncState;
        public final long startedUnixSeconds;
        private Descriptor(byte[] p,long date) throws IOException {
            if(p==null||p.length!=112||!magic(p,0,"CRS2")||u16(p,4)!=2||u16(p,6)!=112||crc(p,0,108)!=u32(p,108))throw invalid("invalid descriptor framing or CRC");
            wire=p.clone();
            startedUnixSeconds=date;
            recordingId=u32(p,8);epoch=u64(p,12);sessionId=u64(p,20);segmentIndex=u32(p,28);sampleOffset=u64(p,32);sampleCount=u64(p,40);encodedLength=u32(p,48);contentCrc=u32(p,52);
            sha=Arrays.copyOfRange(p,56,88);totalSegments=u32(p,88);flags=u8(p,92);codec=u8(p,93);sourceMode=u8(p,94);syncState=u8(p,95);uid=Arrays.copyOfRange(p,96,108);
            if(recordingId==0||epoch==0||sessionId==0||segmentIndex>=0xffffffffL||codec!=3||sourceMode>2||syncState>2||(flags&~63)!=0||(flags>>>3)>5
                    ||((flags&56)!=0&&(flags&2)==0)||(flags&1)==0||encodedLength<15||encodedLength>64L*1024*1024
                    ||sampleOffset<0||sampleCount<=0||sampleCount%320!=0||sampleOffset%320!=0||sampleOffset>Long.MAX_VALUE-sampleCount
                    ||sampleCount/320>(encodedLength-12)/3||uniform(uid,0)||uniform(uid,255)||uniform(sha,0)
                    ||((flags&2)!=0?totalSegments!=segmentIndex+1:totalSegments!=0))throw invalid("invalid sealed descriptor");
        }
        public static Descriptor decode(byte[] payload) throws IOException {
            if(payload!=null&&payload.length==120){
                if(crc(payload,0,116)!=u32(payload,116))throw invalid("local calendar metadata CRC");
                return new Descriptor(Arrays.copyOf(payload,112),u32(payload,112));
            }
            return new Descriptor(payload,0);
        }
        public byte[] metadataBytes(){
            if(startedUnixSeconds==0)return wireBytes();
            byte[] out=Arrays.copyOf(wire,120);put32(out,112,startedUnixSeconds);put32(out,116,crc(out,0,116));return out;
        }
        public byte[] uid() {return uid.clone();}
        public byte[] sha256() {return sha.clone();}
        public byte[] wireBytes() {return wire.clone();}
        boolean sameContent(Descriptor other) {
            byte[] a=wire.clone(), b=other.wire.clone();
            a[95]=b[95]=0;
            Arrays.fill(a,108,112,(byte)0); Arrays.fill(b,108,112,(byte)0);
            return Arrays.equals(a,b);
        }
    }

    /** Only the explicit device STALE_SNAPSHOT result permits a fresh directory request. */
    public static final class CatalogChanged extends IOException {
        CatalogChanged(){super("recording directory snapshot changed (device result 8)");}
    }

    /** One immutable paginated directory snapshot; callers start a fresh one after a stale response. */
    public static final class Catalog {
        private final Peer peer; private final long nonce; private long snapshot,total=-1;
        private boolean calendar;
        private final ArrayList<Descriptor> entries=new ArrayList<>(); private final Set<Long> ids=new HashSet<>(); private final Map<Long,byte[]> pages=new HashMap<>();
        public Catalog(Peer peer,long nonce) throws IOException {if(peer==null||nonce<=0||nonce>0xffffffffL)throw invalid("invalid catalog nonce");this.peer=peer;this.nonce=nonce;}
        public void calendar(boolean value){if(total!=-1)throw new IllegalStateException("catalog already started");calendar=value;}
        public byte[] request() {byte[] p=new byte[16];p[0]=2;p[1]=0x20;p[2]=(byte)(calendar?1:0);put32(p,4,snapshot);put32(p,8,nonce);put32(p,12,entries.size());return p;}
        /** Returns false for an unrelated nonce, otherwise accepts exactly the next page. */
        public boolean accept(byte[] p) throws IOException {
            if(p==null)throw invalid("missing directory response");
            if(magic(p,0,"CRE2")) {
                if(p.length!=16||u16(p,4)!=2||u16(p,6)!=16)throw invalid("invalid directory error");
                if(u32(p,8)!=nonce)return false;
                long result=u32(p,12);
                if(result==8)throw new CatalogChanged();
                throw invalid("device refused directory (result "+result+")");
            }
            if(p.length<20||u8(p,0)!=2)return false;
            if(u32(p,16)!=nonce)return false;
            int stride=calendar?116:112;
            if(p.length<24||u8(p,1)>2||u16(p,2)!=stride||p.length!=24+u8(p,1)*stride)throw invalid("invalid directory page");
            CRC32 c=new CRC32();c.update(p,0,20);c.update(p,24,p.length-24);if(c.getValue()!=u32(p,20))throw invalid("directory CRC mismatch");
            long version=u32(p,4),start=u32(p,8),count=u32(p,12);int n=u8(p,1);
            if(version==0||count>1024||count>peer.capacity||start>count||n>count-start||(count!=0&&n==0))throw invalid("invalid directory snapshot or cursor");
            if(total!=-1&&(snapshot!=version||total!=count))throw invalid("directory changed; refresh catalog");
            if(pages.containsKey(start)){if(Arrays.equals(pages.get(start),p))return false;throw invalid("conflicting directory page");}
            if(start!=entries.size())throw invalid("missing or out-of-order directory page");
            ArrayList<Descriptor> page=new ArrayList<>();Set<Long> newIds=new HashSet<>();
            for(int i=0;i<n;i++){int at=24+i*stride;Descriptor d=new Descriptor(Arrays.copyOfRange(p,at,at+112),calendar?u32(p,at+112):0);peer.validate(d);if(ids.contains(d.recordingId)||!newIds.add(d.recordingId))throw invalid("duplicate recording id");page.add(d);}
            snapshot=version;total=count;entries.addAll(page);ids.addAll(newIds);pages.put(start,p.clone());return true;
        }
        public boolean complete(){return total>=0&&entries.size()==total;}
        public List<Descriptor> entries() throws IOException {if(!complete())throw invalid("catalog is incomplete");return Collections.unmodifiableList(new ArrayList<>(entries));}
    }

    /** Decode and verify one V2 chunk before it is written to a local file. */
    public static byte[] packet(Descriptor d,byte[] p,long sequence,long offset) throws IOException {
        if(d==null||p==null||p.length<20||p.length>509||u8(p,0)!=1)throw invalid("invalid chunk framing");
        int flags=u8(p,1),length=u16(p,2),header=(flags&129)!=0?56:(flags&8)!=0?20:24;
        if((flags&~9)!=0||p.length!=header+length||length==0||u32(p,4)!=d.recordingId||u32(p,8)!=sequence||u32(p,12)!=offset||offset<0||offset>d.encodedLength||length>d.encodedLength-offset)throw invalid("chunk identity, sequence or length mismatch");
        long total=header==20?0:u32(p,16);int crcAt=header==20?16:20;if(total!=0&&total!=d.encodedLength)throw invalid("chunk total changed");
        CRC32 c=new CRC32();c.update(p,4,12);byte[] t=new byte[4];put32(t,0,d.encodedLength);c.update(t);c.update(p,header,length);if(c.getValue()!=u32(p,crcAt))throw invalid("chunk CRC mismatch");
        if((flags&1)!=0&&(offset+length!=d.encodedLength||total!=d.encodedLength||!Arrays.equals(Arrays.copyOfRange(p,24,56),d.sha)))throw invalid("invalid final chunk");
        if((flags&1)==0&&offset+length==d.encodedLength)throw invalid("missing final chunk flag");
        return Arrays.copyOfRange(p,header,p.length);
    }
}
