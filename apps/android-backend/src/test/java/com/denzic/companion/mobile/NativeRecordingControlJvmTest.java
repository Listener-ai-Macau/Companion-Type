package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.UUID;
import java.util.zip.CRC32;

public final class NativeRecordingControlJvmTest {
    static void put(byte[] a,int p,long value,int n){for(int i=0;i<n;i++)a[p+i]=(byte)(value>>>(8*i));}
    static void crc(byte[] a,int from,int len,int at){CRC32 c=new CRC32();c.update(a,from,len);put(a,at,c.getValue(),4);}
    static final class Fake implements RecordingClient.Link {
        final byte[] golden,identity=new byte[116];byte[] status,negotiation,page,descriptor;int writes;boolean loseAck;
        Fake(byte[] golden){this.golden=golden;identity[0]=1;put(identity,12,0x57424155L,4);
            for(int i=0;i<12;i++)identity[20+i]=(byte)(i+1);
            System.arraycopy(new byte[]{'C','C','P','1'},0,identity,36,4);identity[40]=1;identity[41]=1;identity[43]=7;
            int space=8*1024*1024-8192;put(identity,48,space,4);put(identity,52,space,4);put(identity,56,space,4);put(identity,68,2100,4);put(identity,72,4096,4);put(identity,76,1800,4);
            System.arraycopy(new byte[]{'C','R','V','2'},0,identity,84,4);put(identity,88,2,2);put(identity,90,32,2);put(identity,92,127,4);put(identity,96,7,8);put(identity,104,64,2);put(identity,106,1024,2);put(identity,108,248,2);crc(identity,84,28,112);
            status=vector(0);status[1]=2;crc(status,0,76,76);
        }
        byte[] vector(int n){int at=8+n*137+56;return Arrays.copyOfRange(golden,at,at+80);}
        void rebootWithSealedDirectory(){
            descriptor=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,descriptor,0,4);put(descriptor,4,2,2);put(descriptor,6,112,2);
            System.arraycopy(status,12,descriptor,8,4);System.arraycopy(status,44,descriptor,12,16);put(descriptor,40,1920000,8);
            put(descriptor,48,30000,4);put(descriptor,52,123,4);Arrays.fill(descriptor,56,88,(byte)9);put(descriptor,88,1,4);
            descriptor[92]=19;descriptor[93]=3;descriptor[94]=1;System.arraycopy(identity,20,descriptor,96,12);crc(descriptor,0,108,108);
            byte[] idle=new byte[64];idle[0]=1;idle[1]=2;System.arraycopy(new byte[]{'C','M','S','2'},0,idle,28,4);
            System.arraycopy(identity,20,idle,32,12);System.arraycopy(identity,96,idle,44,8);crc(idle,0,60,60);status=idle;
        }
        public int mtu(){return 251;}
        public String deviceAddress(){return "C8:92:FF:DD:3B:CA";}
        public byte[] read(UUID id)throws IOException {if(id.equals(RecordingClient.DEVICE_STATUS))return identity.clone();if(id.equals(RecordingClient.MEETING_STATUS))return status.clone();throw new IOException("unexpected read");}
        public void subscribe(UUID id){}
        public void write(UUID id,byte[] value)throws IOException {
            if(id.equals(RecordingClient.RECORDING_CONTROL)&&value[1]==0x22){negotiation=value.clone();return;}
            if(id.equals(RecordingClient.RECORDING_CONTROL)&&value[1]==0x20&&descriptor!=null){
                page=new byte[136];page[0]=2;page[1]=1;put(page,2,112,2);put(page,4,1,4);put(page,12,1,4);
                System.arraycopy(value,8,page,16,4);System.arraycopy(descriptor,0,page,24,112);CRC32 c=new CRC32();c.update(page,0,20);c.update(page,24,112);put(page,20,c.getValue(),4);return;
            }
            if(!id.equals(RecordingClient.MEETING_CONTROL))throw new IOException("unexpected write");
            writes++;int n=value[5]==1?0:value[5]==4?2:value[5]==5?5:value[5]==2?8:-1;if(n<0)throw new IOException("unexpected command");
            byte[] previous=status;status=vector(n);if(value[5]!=1)System.arraycopy(previous,32,status,32,28);
            System.arraycopy(value,36,status,8,4);System.arraycopy(value,48,status,60,4);crc(status,0,76,76);
            if(loseAck){loseAck=false;throw new IOException("synthetic dropped confirmation");}
        }
        public byte[] await(UUID id,long timeout)throws IOException {if(id.equals(RecordingClient.RECORDING_CONTROL)&&negotiation!=null)return negotiation.clone();if(id.equals(RecordingClient.RECORDING_LIST)&&page!=null)return page.clone();throw new java.net.SocketTimeoutException("synthetic timeout");}
        public void close(){}
    }
    static void expect(String value,String state){if(!value.contains("\"state\":\""+state+"\""))throw new AssertionError(value);}
    public static void main(String[] args)throws Exception {
        byte[] golden=Files.readAllBytes(Paths.get(args[1]));Path root=Paths.get(args[0]).toAbsolutePath();Files.createDirectories(root);Fake fake=new Fake(golden);
        try(RecordingClient client=new RecordingClient(fake)){
            String session=NativeRecordingControl.newSessionId();
            expect(client.control(root,session,NativeRecordingControl.Action.START,120),"recording");
            expect(client.control(root,session,NativeRecordingControl.Action.PAUSE,0),"paused");
            expect(client.control(root,session,NativeRecordingControl.Action.RESUME,0),"recording");
            expect(client.control(root,session,NativeRecordingControl.Action.STOP,0),"stopped");
            if(fake.writes!=4)throw new AssertionError("unexpected command count");
            String second=NativeRecordingControl.newSessionId();fake.loseAck=true;
            try{client.control(root,second,NativeRecordingControl.Action.START,120);throw new AssertionError("lost acknowledgment hidden");}catch(IOException expected){}
            String inventory=client.controlSessions(root);if(!inventory.contains(second)||!inventory.contains("\"state\":\"pending\""))throw new AssertionError("pending session not discoverable: "+inventory);
            expect(client.control(root,second,NativeRecordingControl.Action.QUERY,0),"recording");
            if(fake.writes!=5)throw new AssertionError("new start was repeated");
            fake.rebootWithSealedDirectory();String recovered=client.reconcileControlFromDirectory(root,second);expect(recovered,"stopped");
            if(!recovered.contains("\"confirmedByCatalogue\":true")||fake.writes!=5)throw new AssertionError("catalogue recovery must not send stop: "+recovered);
            expect(client.control(root,second,NativeRecordingControl.Action.QUERY,0),"stopped");
        }
        byte[] local=Files.readAllBytes(Paths.get(args[2]));Fake physical=new Fake(golden);physical.status=Arrays.copyOfRange(local,8+8*80,8+9*80);
        try(RecordingClient client=new RecordingClient(physical)) {
            Path localRoot=root.resolve("local-button");String result=client.adoptLocalControl(localRoot);expect(result,"recording");
            if(physical.writes!=0)throw new AssertionError("adoption sent a control command");
            String marker="\"hostSession\":\"";int start=result.indexOf(marker);if(start<0)throw new AssertionError(result);
            start+=marker.length();String host=result.substring(start,result.indexOf('"',start));
            physical.status=Arrays.copyOfRange(local,8+10*80,8+11*80);expect(client.adoptLocalControl(localRoot),"paused");
            expect(client.control(localRoot,host,NativeRecordingControl.Action.RESUME,0),"recording");
            if(physical.writes!=1)throw new AssertionError("resume was not the only command");
        }
        System.out.println("NativeRecordingControl JNI fake-link test passed");
    }
}
