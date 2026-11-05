package com.denzic.companion.mobile;
import java.io.IOException;
import java.util.zip.CRC32;
/** Synthetic wire fixtures only, no radio or customer audio. */
public final class WideSegmentWireTest {
    private static void put16(byte[] p,int i,int n){p[i]=(byte)n;p[i+1]=(byte)(n>>>8);}
    private static void put32(byte[] p,int i,long n){for(int j=0;j<4;j++)p[i+j]=(byte)(n>>>(j*8));}
    private static void crc(byte[] p,int from,int len,int at){CRC32 c=new CRC32();c.update(p,from,len);put32(p,at,c.getValue());}
    private static byte[] status(long caps){
        byte[] s=new byte[116];s[0]=1;put32(s,12,0x57424155L);s[20]=1;
        System.arraycopy(new byte[]{'C','R','V','2'},0,s,84,4);put16(s,88,2);put16(s,90,32);
        put32(s,92,caps);s[96]=1;put16(s,104,64);put16(s,106,1024);put16(s,108,248);crc(s,84,28,112);return s;
    }
    private static byte[] descriptor(long index,long total){
        byte[] d=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,d,0,4);
        put16(d,4,2);put16(d,6,112);put32(d,8,41);d[12]=1;d[20]=1;put32(d,28,index);
        put32(d,40,320);put32(d,48,15);d[56]=1;put32(d,88,total);d[92]=3;d[93]=3;d[96]=1;crc(d,0,108,108);return d;
    }
    public static void main(String[] args)throws Exception {
        RecorderWire.Peer legacy=RecorderWire.Peer.fromStatus(status(7));
        RecorderWire.Peer wide=RecorderWire.Peer.fromStatus(status(2047));
        if(legacy==null||wide==null)throw new AssertionError("old/new capability");
        RecorderWire.Descriptor d=RecorderWire.Descriptor.decode(descriptor(1024,1025));
        wide.validate(d);if(d.segmentIndex!=1024||d.totalSegments!=1025)throw new AssertionError("wide index");
        try{RecorderWire.Descriptor.decode(descriptor(0xffffffffL,0));throw new AssertionError("wrapped terminal count accepted");}catch(IOException expected){}
        try{RecorderWire.Peer.fromStatus(status(4095));throw new AssertionError("unknown capability accepted");}catch(IOException expected){}
        System.out.println("PASS legacy/wide capability and descriptor boundary");
    }
}
