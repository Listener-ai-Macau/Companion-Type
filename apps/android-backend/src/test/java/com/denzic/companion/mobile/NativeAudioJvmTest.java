package com.denzic.companion.mobile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.zip.CRC32;
import java.io.ByteArrayOutputStream;

/** JVM-to-native bridge test with synthetic silent Opus, no Android device. */
public final class NativeAudioJvmTest {
    private static void put16(byte[] p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
    private static void put32(byte[] p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static void put64(byte[] p,int i,long v){for(int n=0;n<8;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static byte[] packet(byte[] raw,byte[] hash,int offset,int length,int sequence,boolean last) {
        int header=last?56:24;byte[] p=new byte[header+length];p[0]=1;p[1]=(byte)(last?1:0);put16(p,2,length);
        put32(p,4,41);put32(p,8,sequence);put32(p,12,offset);put32(p,16,raw.length);
        if(last)System.arraycopy(hash,0,p,24,32);System.arraycopy(raw,offset,p,header,length);
        CRC32 crc=new CRC32();crc.update(p,4,16);crc.update(raw,offset,length);put32(p,20,crc.getValue());return p;
    }
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory(Paths.get(args[0]),"jni-silence-");
        ByteArrayOutputStream source=new ByteArrayOutputStream();source.write(new byte[]{'C','O','P','1',3,1,20,3,(byte)128,62,0,0});
        int[] opus={184,91,61,13,6,212,119,103,154,112,59,167,214,84,199,215,224,197,21,15,83,26,25,151,74,91,44,201,192,179,8,78,13,165,128,204,28,243,127,83};
        byte[] audio=new byte[42];audio[0]=40;for(int i=0;i<opus.length;i++)audio[i+2]=(byte)opus[i];source.write(audio);source.write(audio);
        while(source.size()%248!=0)source.write(255);byte[] mark=new byte[32];System.arraycopy(new byte[]{'C','P','G','1'},0,mark,2,4);
        mark[6]=4;put32(mark,8,1);put64(mark,12,640);put64(mark,20,40);CRC32 markCrc=new CRC32();markCrc.update(mark,0,28);put32(mark,28,markCrc.getValue());
        source.write(mark);while(source.size()%248!=0)source.write(255);source.write(audio);byte[] raw=source.toByteArray();
        byte[] hash=MessageDigest.getInstance("SHA-256").digest(raw);CRC32 crc=new CRC32();crc.update(raw);
        byte[] d=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,d,0,4);put16(d,4,2);put16(d,6,112);put32(d,8,41);d[12]=1;d[20]=1;put32(d,40,960);put32(d,48,raw.length);put32(d,52,crc.getValue());System.arraycopy(hash,0,d,56,32);put32(d,88,1);d[92]=3;d[93]=3;d[96]=1;crc.reset();crc.update(d,0,108);put32(d,108,crc.getValue());
        RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(d);
        try(SegmentReceiver receiver=new SegmentReceiver(root,descriptor)){
            receiver.accept(packet(raw,hash,0,248,0,false));receiver.accept(packet(raw,hash,248,raw.length-248,1,true));receiver.finish();}
        RecordingLibrary.Session session=RecordingLibrary.sessions(root).get(0);Path wav=root.resolve("output.wav");
        NativeAudio.Result result=NativeAudio.decode(session,wav);byte[] output=Files.readAllBytes(wav);
        if(result.samples!=640||!result.captureComplete||output.length!=1324||!Arrays.equals(Arrays.copyOf(output,4),new byte[]{'R','I','F','F'}))throw new AssertionError("native output mismatch");
        if(result.bookmarks.size()!=1||result.bookmarks.get(0).sequence!=1||result.bookmarks.get(0).sourceSamples!=640||
            result.bookmarks.get(0).playbackSamples!=320||result.bookmarks.get(0).elapsedMillis!=40)throw new AssertionError("device bookmark was not preserved");
        try{NativeAudio.decode(session,wav);throw new AssertionError("existing output replaced");}catch(java.io.IOException expected){}
        if(!Arrays.equals(Files.readAllBytes(wav),output))throw new AssertionError("existing output changed");
        System.out.println("PASS Java-to-native synthetic audio decode and existing-output preservation");
    }
}
