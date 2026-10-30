package com.denzic.companion.mobile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.zip.CRC32;

/** JVM-to-native bridge test with synthetic silent Opus, no Android device. */
public final class NativeAudioJvmTest {
    private static void put16(byte[] p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
    private static void put32(byte[] p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory(Paths.get(args[0]),"jni-silence-");
        byte[] raw=new byte[]{'C','O','P','1',1,1,20,0,(byte)128,62,0,0,3,0,(byte)248,(byte)255,(byte)254,3,0,(byte)248,(byte)255,(byte)254,3,0,(byte)248,(byte)255,(byte)254};
        byte[] hash=MessageDigest.getInstance("SHA-256").digest(raw);CRC32 crc=new CRC32();crc.update(raw);
        byte[] d=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,d,0,4);put16(d,4,2);put16(d,6,112);put32(d,8,41);d[12]=1;d[20]=1;put32(d,40,960);put32(d,48,raw.length);put32(d,52,crc.getValue());System.arraycopy(hash,0,d,56,32);put32(d,88,1);d[92]=3;d[93]=3;d[96]=1;crc.reset();crc.update(d,0,108);put32(d,108,crc.getValue());
        RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(d);
        byte[] packet=new byte[56+raw.length];packet[0]=1;packet[1]=1;put16(packet,2,raw.length);put32(packet,4,41);put32(packet,16,raw.length);System.arraycopy(hash,0,packet,24,32);System.arraycopy(raw,0,packet,56,raw.length);crc.reset();crc.update(packet,4,16);crc.update(raw);put32(packet,20,crc.getValue());
        try(SegmentReceiver receiver=new SegmentReceiver(root,descriptor)){receiver.accept(packet);receiver.finish();}
        RecordingLibrary.Session session=RecordingLibrary.sessions(root).get(0);Path wav=root.resolve("output.wav");
        NativeAudio.Result result=NativeAudio.decode(session,wav);byte[] output=Files.readAllBytes(wav);
        if(result.samples!=640||!result.captureComplete||output.length!=1324||!Arrays.equals(Arrays.copyOf(output,4),new byte[]{'R','I','F','F'}))throw new AssertionError("native output mismatch");
        try{NativeAudio.decode(session,wav);throw new AssertionError("existing output replaced");}catch(java.io.IOException expected){}
        if(!Arrays.equals(Files.readAllBytes(wav),output))throw new AssertionError("existing output changed");
        System.out.println("PASS Java-to-native synthetic audio decode and existing-output preservation");
    }
}
