package com.denzic.companion.mobile;
import android.system.Os;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.UUID;
import java.util.zip.CRC32;

/** Host fixture: actual packaged receive/consume logic with a mocked Android OS. */
public final class AndroidDurableIntegrationTest {
    private static void put16(byte[] p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
    private static void put32(byte[] p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    private static final class Link implements RecordingClient.Link {
        byte[] sent;int writes;
        public int mtu(){return 247;}public byte[] read(UUID id){throw new AssertionError();}
        public void subscribe(UUID id){}public void write(UUID id,byte[] value){writes++;sent=value.clone();}
        public byte[] await(UUID id,long millis){return sent.clone();}public void close(){}
    }
    public static void main(String[] args)throws Exception {
        Path fixture=Paths.get(args[0]);byte[] wire=Files.readAllBytes(fixture.resolve("descriptor0.bin"));
        byte[] status=new byte[116];status[0]=1;put32(status,12,0x57424155L);System.arraycopy(wire,96,status,20,12);
        System.arraycopy(new byte[]{'C','R','V','2'},0,status,84,4);put16(status,88,2);put16(status,90,32);put32(status,92,7);
        System.arraycopy(wire,12,status,96,8);put16(status,104,64);put16(status,106,1024);put16(status,108,248);
        CRC32 crc=new CRC32();crc.update(status,84,28);put32(status,112,crc.getValue());
        RecorderWire.Peer peer=RecorderWire.Peer.fromStatus(status);RecorderWire.Catalog catalog=new RecorderWire.Catalog(peer,17);
        catalog.accept(Files.readAllBytes(fixture.resolve("page0.bin")));catalog.accept(Files.readAllBytes(fixture.resolve("page1.bin")));
        RecorderWire.Descriptor first=catalog.entries().get(0);Path dir=Files.createTempDirectory(fixture,"android-fsync-integration-");
        String key=SegmentReceiver.key(first);Files.write(dir.resolve(key+".meta"),first.wireBytes());
        Files.write(dir.resolve(key+".cop1"),Files.readAllBytes(fixture.resolve("payload.bin")));
        Link link=new Link();DurableConsume consume=new DurableConsume(peer,link,AndroidDirectorySync::sync,prefix->{});
        Os.calls.clear();Os.fail="fsync";Os.mode=040000;
        try{consume.consume(dir,first);throw new AssertionError("failed fsync accepted");}catch(IOException expected){}
        check(link.writes==0&&!Files.exists(dir.resolve(".consume-pending")),"card was contacted before local directory fsync succeeded");
        Os.calls.clear();Os.fail="";
        check(consume.consume(dir,first),"verified recording did not consume after recovery");
        check(link.writes==1&&Os.calls.contains("fsync")&&Files.isRegularFile(dir.resolve(key+".receipt")),"exact confirmed receipt not saved");
        check(Files.isRegularFile(dir.resolve(key+".cop1")),"local original missing");
        System.out.println("PASS packaged Android fsync failure keeps device copy; recovery retains local original");
    }
}
