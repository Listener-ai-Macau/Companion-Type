package com.denzic.companion.mobile;

import java.io.DataInputStream;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.zip.CRC32;

/** Replay previously captured synthetic Android diagnostic packets, never real recordings. */
public final class SavedSyntheticWireReplay {
    private static void put16(byte[] p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
    private static void put32(byte[] p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static byte[] hex(String s){byte[] b=new byte[s.length()/2];for(int i=0;i<b.length;i++)b[i]=(byte)Integer.parseInt(s.substring(2*i,2*i+2),16);return b;}
    public static void main(String[] args)throws Exception {
        byte[] expected=hex("c0f6db45bf7d7610cc10e346467efce8c0f2ba7669ef45f5a79335fe79ef2c2f");
        byte[] d=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,d,0,4);put16(d,4,2);put16(d,6,112);put32(d,8,65536);d[12]=1;d[20]=1;put32(d,40,320);put32(d,48,2097152);System.arraycopy(expected,0,d,56,32);put32(d,88,1);d[92]=3;d[93]=3;d[94]=1;for(int i=0;i<12;i++)d[96+i]=(byte)(i+1);CRC32 c=new CRC32();c.update(d,0,108);put32(d,108,c.getValue());RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(d);
        MessageDigest digest=MessageDigest.getInstance("SHA-256");int offset=0,sequence=0;boolean corruptRejected=false;
        try(DataInputStream in=new DataInputStream(new FileInputStream(args[0]))){while(in.available()>0){int n=in.readInt();if(n<1||n>509)throw new AssertionError("bad saved capture");byte[] packet=new byte[n];in.readFully(packet);byte[] bytes=RecorderWire.packet(descriptor,packet,sequence,offset);
            if(sequence==0){byte[] bad=packet.clone();bad[bad.length-1]^=1;try{RecorderWire.packet(descriptor,bad,sequence,offset);}catch(java.io.IOException expectedError){corruptRejected=true;}}
            digest.update(bytes);offset+=bytes.length;sequence++;}}
        if(offset!=2097152||sequence!=10509||!Arrays.equals(digest.digest(),expected)||!corruptRejected)throw new AssertionError("replay did not match original synthetic bytes");
        System.out.println("PASS actual saved Android synthetic wire: 10509 packets, 2 MiB, SHA matched, corrupted packet rejected");
    }
}
