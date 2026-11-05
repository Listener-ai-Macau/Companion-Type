package com.denzic.companion.mobile;

import java.io.IOException;
import java.util.Arrays;
import java.util.UUID;

/** Existing settings plus optional LE Unix date. No recording or cloud writes. */
final class DeviceClock {
    static final UUID SETTINGS=UUID.fromString("8f7a4001-7b7d-4f3d-9d6f-6c2d1b7c0000");
    static byte[] payload(byte[] current,long utc) throws IOException {
        if(current==null||current.length<10||current[0]!=1||utc<=0||utc>0xffffffffL)
            throw new IOException("Invalid device settings or UTC date");
        byte[] out=Arrays.copyOf(current,current.length>=17?17:13);
        long day=utc%86400;
        out[10]=(byte)(day/3600);out[11]=(byte)((day/60)%60);out[12]=(byte)(day%60);
        if(out.length==17)for(int i=0;i<4;i++)out[13+i]=(byte)(utc>>(8*i));
        return out;
    }
    static void verify(byte[] expected,byte[] actual) throws IOException {
        if(actual==null||actual.length<13)throw new IOException("Device clock readback missing");
        int h=actual[10]&255,m=actual[11]&255,s=actual[12]&255;
        if(h>23||m>59||s>59)throw new IOException("Device clock readback invalid");
        int wanted=(expected[10]&255)*3600+(expected[11]&255)*60+(expected[12]&255);
        int delta=Math.abs(h*3600+m*60+s-wanted);
        if(Math.min(delta,86400-delta)>2)throw new IOException("Device clock readback mismatch");
        if(expected.length==17){
            if(actual.length<17)throw new IOException("Device calendar readback missing");
            long a=0,b=0;for(int i=0;i<4;i++){a|=(long)(actual[13+i]&255)<<(8*i);b|=(long)(expected[13+i]&255)<<(8*i);}
            if(a==0||Math.abs(a-b)>2)throw new IOException("Device UTC date readback mismatch");
        }
    }
}
