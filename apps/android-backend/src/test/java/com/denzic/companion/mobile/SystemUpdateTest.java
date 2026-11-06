package com.denzic.companion.mobile;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.*;
import org.json.*;
import static com.denzic.companion.mobile.SystemUpdatePackage.*;
/** Official producer package and firmware-shaped fake peripheral. No hardware
 * access and no private keys. These checks cannot qualify physical Android OTA. */
public final class SystemUpdateTest {
    static int checks;static void ok(boolean condition,String why){checks++;if(!condition)throw new AssertionError(why);}
    interface Work{void run()throws Exception;}
    static void reject(Work work,String why)throws Exception{try{work.run();throw new AssertionError("accepted: "+why);}catch(IOException expected){checks++;}}
    static byte[] identity(SystemUpdatePackage p,long fw,boolean installed)throws Exception{byte[] b=new byte[60];System.arraycopy("WSI4".getBytes("UTF-8"),0,b,0,4);put32(b,4,fw);put32(b,8,p.resourceVersion);put32(b,12,p.staticBytes);put32(b,20,1);put32(b,56,p.target);if(installed)System.arraycopy(p.payloadSha,0,b,24,32);return b;}
    static void put16(byte[] b,int at,int v){b[at]=(byte)v;b[at+1]=(byte)(v>>>8);}
    static byte[] peer(boolean other)throws Exception{byte[] b=new byte[116];b[0]=1;put32(b,12,0x57424155L);for(int i=20;i<32;i++)b[i]=(byte)(i+(other?1:0));System.arraycopy("CRV2".getBytes("UTF-8"),0,b,84,4);put16(b,88,2);put16(b,90,32);put32(b,92,7);put32(b,96,1);put16(b,104,64);put16(b,106,1024);put16(b,108,509);put32(b,112,crc(b,84,28));return b;}
    static final class Peripheral implements RecordingClient.Link {
        final SystemUpdatePackage pack;final ByteArrayOutputStream staged=new ByteArrayOutputStream(),durable=new ByteArrayOutputStream();int state,error,begin,finish,aborts,chunk=505,window=8,blockers;long total,accepted,generation=7;boolean installed,closed,wrongOffset,oldGeneration,other,ambiguousFinish;int connects;
        Peripheral(SystemUpdatePackage p){pack=p;}
        public int mtu(){return 512;}public void close(){closed=true;}
        byte[] status()throws Exception{byte[] b=new byte[64];System.arraycopy("DOV1".getBytes("UTF-8"),0,b,0,4);b[4]=1;b[5]=(byte)state;b[6]=(byte)error;put32(b,8,accepted+(wrongOffset&&accepted>0?1:0));put32(b,12,total);put16(b,16,chunk);put16(b,18,window);System.arraycopy("WOC5".getBytes("UTF-8"),0,b,24,4);put16(b,28,505);put16(b,30,509);put16(b,32,64);put16(b,34,53);put16(b,36,16);put32(b,40,generation);System.arraycopy("BLK1".getBytes("UTF-8"),0,b,44,4);return b;}
        public byte[] read(UUID id)throws IOException{try{if(id.equals(RecordingClient.DEVICE_STATUS))return peer(other);if(id.equals(SystemUpdateClient.IDENTITY))return identity(pack,installed?pack.firmwareVersion:pack.firmwareVersion-1,installed);if(id.equals(SystemUpdateClient.STATUS))return status();if(id.equals(SystemUpdateClient.READINESS)){byte[] b=new byte[24];b[0]=1;b[1]=(byte)(blockers==0?1:0);b[3]=(byte)255;put16(b,6,blockers);return b;}throw new IOException("unexpected read");}catch(IOException e){throw e;}catch(Exception e){throw new IOException(e);}}
        public void write(UUID id,byte[] b)throws IOException{if(id.equals(SystemUpdateClient.DATA)){long offset=word(b,0);if(offset!=accepted+staged.size())throw new IOException("bad packet offset");staged.write(b,4,b.length-4);return;}
            if(!id.equals(SystemUpdateClient.CONTROL)||!magic(b,0,"DOV1")||b.length!=20)throw new IOException("bad control");
            switch(b[4]){case 1:begin++;state=2;error=0;total=word(b,8);chunk=u16(b,12);window=u16(b,14);if(!oldGeneration)generation++;accepted=0;staged.reset();durable.reset();break;
                case 2:byte[] saved=staged.toByteArray();durable.write(saved,0,saved.length);accepted+=saved.length;staged.reset();break;
                case 3:finish++;if(accepted!=pack.image.length||!Arrays.equals(durable.toByteArray(),pack.image))throw new IOException("finish before exact full file");state=3;installed=true;if(ambiguousFinish)throw new java.net.SocketTimeoutException("ATT finish reply lost during reboot");break;
                case 4:aborts++;state=0;error=0;total=0;accepted=0;staged.reset();break;default:throw new IOException("bad operation");}
        }
        public void subscribe(UUID id)throws IOException{throw new IOException("not needed for acknowledged transport");}public byte[] await(UUID id,long ms)throws IOException{throw new IOException("not needed");}
        RecordingClient.Link connect(){connects++;closed=false;return this;}
    }
    static final SystemUpdateClient.Progress QUIET=(phase,accepted,total)->{};
    static byte[] zip(String name,byte[] content,String second,byte[] body)throws Exception{ByteArrayOutputStream out=new ByteArrayOutputStream();try(ZipOutputStream zip=new ZipOutputStream(out)){for(int i=0;i<2;i++){zip.putNextEntry(new ZipEntry(i==0?name:second));zip.write(i==0?content:body);zip.closeEntry();}}return out.toByteArray();}
    public static void main(String[] args)throws Exception{
        Path root=Paths.get(args[0]);JSONObject manifest=new JSONObject(new String(Files.readAllBytes(root.resolve("ota_manifest.json")),"UTF-8"));byte[] image=Files.readAllBytes(root.resolve(manifest.getString("file")));
        SystemUpdatePackage p=validate(manifest,image);ok(p.firmwareVersion==66685&&p.resourceVersion==85&&p.image.length==1359700,"real producer package");
        byte[] archive=zip("ota_manifest.json",manifest.toString().getBytes("UTF-8"),manifest.getString("file"),image);ok(SystemUpdatePackage.open(new ByteArrayInputStream(archive)).id.equals(p.id),"unchanged envelope");
        byte[] broken=image.clone();broken[broken.length-1]^=1;reject(()->validate(manifest,broken),"one-byte file corruption");
        JSONObject forged=new JSONObject(manifest.toString()).put("sha256",hash(broken));reject(()->validate(forged,broken),"rewritten outer hash cannot hide payload corruption");
        JSONObject wrong=new JSONObject(manifest.toString()).put("board_target",0x45315643L);reject(()->validate(wrong,image),"different geometry");
        JSONObject decimal=new JSONObject(manifest.toString()).put("firmware_version",66685.5);reject(()->validate(decimal,image),"fractional version");
        reject(()->SystemUpdatePackage.open(new ByteArrayInputStream(zip("../ota_manifest.json",manifest.toString().getBytes("UTF-8"),"companion-update.cup",image))),"zip path traversal");
        byte[] old=identity(p,p.firmwareVersion-1,false);p.admit(old);checks++;reject(()->p.admit(identity(p,p.firmwareVersion,false)),"same-version downgrade gate");byte[] layout=old.clone();put32(layout,56,0x45315643L);reject(()->p.admit(layout),"wrong running target");
        ok(!p.installed(old),"old app is not success");byte[] complete=identity(p,p.firmwareVersion,true);ok(p.installed(complete),"exact new running version SHA");put32(complete,16,100);ok(!p.installed(complete),"workspace must release");complete=identity(p,p.firmwareVersion,true);complete[24]^=1;ok(!p.installed(complete),"matching version alone is not success");
        Peripheral busy=new Peripheral(p);busy.blockers=8;reject(()->SystemUpdateClient.transfer(busy::connect,p,new AtomicBoolean(),QUIET),"low power");ok(busy.begin==0&&busy.finish==0&&busy.closed,"no write before admission");
        Peripheral retained=new Peripheral(p);retained.state=3;reject(()->SystemUpdateClient.transfer(retained::connect,p,new AtomicBoolean(),QUIET),"retained complete file");ok(retained.aborts==0&&retained.begin==0,"never discard complete file");
        Peripheral generation=new Peripheral(p);generation.oldGeneration=true;reject(()->SystemUpdateClient.transfer(generation::connect,p,new AtomicBoolean(),QUIET),"stale BEGIN generation");ok(generation.finish==0&&generation.aborts==1,"stale transfer aborted");
        Peripheral offset=new Peripheral(p);offset.wrongOffset=true;reject(()->SystemUpdateClient.transfer(offset::connect,p,new AtomicBoolean(),QUIET),"wrong durable offset");ok(offset.finish==0&&offset.aborts==1,"never finish unknown durable position");
        Peripheral stopped=new Peripheral(p);AtomicBoolean cancel=new AtomicBoolean();reject(()->SystemUpdateClient.transfer(stopped::connect,p,cancel,(phase,accepted,total)->{if(phase.equals("transferring"))cancel.set(true);}),"cancel after real receipt");ok(stopped.aborts==1&&stopped.finish==0,"cancel cannot install");
        Peripheral malformed=new Peripheral(p);byte[] wire=malformed.status();wire[51]=1;reject(()->new SystemUpdateClient.Status(wire),"malformed live capability");
        Peripheral success=new Peripheral(p);success.state=2;success.accepted=120;success.total=999;success.ambiguousFinish=true;
        SystemUpdateClient.transfer(success::connect,p,new AtomicBoolean(),(phase,accepted,total)->{if(phase.equals("transferring"))ok(success.accepted==accepted&&success.staged.size()==0,"progress only after durable receipt");});
        ok(success.aborts==1&&success.begin==1&&success.finish==1&&success.connects==2&&success.closed,"fresh download, finish once, exact post-boot verification");
        success.other=true;reject(()->SystemUpdateClient.verify(success::connect,p,"1415161718191a1b1c1d1e1f"),"wrong post-boot UID");
        ok(DeviceNames.candidate("Capture",false)&&DeviceNames.candidate("Companion",false)&&!DeviceNames.candidate("Headphones",false),"advertisements are only explicit candidates");
        System.out.println("PASS "+checks+" assertions: actual signed producer package, corruption/target/layout rejection, durable-only progress, preserved complete package, stale generation/wrong offset/power/cancel refusal, lost FINISH reply resolved only by exact running identity; NO_HARDWARE_OTA");
    }
}
