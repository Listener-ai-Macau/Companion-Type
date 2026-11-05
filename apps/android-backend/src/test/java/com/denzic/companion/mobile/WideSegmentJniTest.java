package com.denzic.companion.mobile;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.List;
import java.util.zip.CRC32;
/** Synthetic 1025-file local session, no device and no network. */
public final class WideSegmentJniTest {
    private static void put16(byte[] p,int i,int n){p[i]=(byte)n;p[i+1]=(byte)(n>>>8);}
    private static void put32(byte[] p,int i,long n){for(int j=0;j<4;j++)p[i+j]=(byte)(n>>>(8*j));}
    private static void put64(byte[] p,int i,long n){for(int j=0;j<8;j++)p[i+j]=(byte)(n>>>(8*j));}
    public static void main(String[] args)throws Exception {
        final int count=1025;
        Path root=Files.createTempDirectory(Paths.get(args[0]),"wide-jni-");
        byte[] raw={'C','O','P','1',1,1,20,0,(byte)0x80,0x3e,0,0,3,0,(byte)0xf8,(byte)0xff,(byte)0xfe,3,0,(byte)0xf8,(byte)0xff,(byte)0xfe};
        byte[] hash=MessageDigest.getInstance("SHA-256").digest(raw);CRC32 crc=new CRC32();crc.update(raw);long audioCrc=crc.getValue();
        for(int i=0;i<count;i++) {
            byte[] d=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,d,0,4);put16(d,4,2);put16(d,6,112);
            put32(d,8,i+1);put64(d,12,1);put64(d,20,7);put32(d,28,i);put64(d,32,(long)i*640);put64(d,40,640);
            put32(d,48,raw.length);put32(d,52,audioCrc);System.arraycopy(hash,0,d,56,32);if(i==count-1)put32(d,88,count);
            d[92]=(byte)(i==count-1?3:1);d[93]=3;d[96]=1;crc.reset();crc.update(d,0,108);put32(d,108,crc.getValue());
            RecorderWire.Descriptor desc=RecorderWire.Descriptor.decode(d);String key=SegmentReceiver.key(desc);
            Files.write(root.resolve(key+".meta"),d);Files.write(root.resolve(key+".cop1"),raw);
        }
        List<RecordingLibrary.Session> sessions=RecordingLibrary.sessions(root);
        if(sessions.size()!=1||sessions.get(0).state!=RecordingLibrary.SessionState.COMPLETE||sessions.get(0).segments.size()!=count)
            throw new AssertionError("session did not include every segment");
        NativeAudio.VerifiedPrefix prefix=NativeAudio.inspectPrefix(sessions.get(0));
        if(!prefix.captureComplete||prefix.encodedSamples!=(long)count*640)throw new AssertionError("JNI lost segment samples");
        System.out.println("PASS 1025 synthetic segments through actual Java-to-host-JNI prefix inspection");
    }
}
