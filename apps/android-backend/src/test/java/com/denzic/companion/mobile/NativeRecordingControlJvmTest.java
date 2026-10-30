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
        final byte[] golden,identity=new byte[116];byte[] status,negotiation;int writes;boolean loseAck;
        Fake(byte[] golden){this.golden=golden;identity[0]=1;put(identity,12,0x57424155L,4);
            for(int i=0;i<12;i++)identity[20+i]=(byte)(i+1);
            System.arraycopy(new byte[]{'C','C','P','1'},0,identity,36,4);identity[40]=1;identity[41]=1;identity[43]=7;
            int space=8*1024*1024-8192;put(identity,48,space,4);put(identity,52,space,4);put(identity,56,space,4);put(identity,68,2100,4);put(identity,72,4096,4);put(identity,76,1800,4);
            System.arraycopy(new byte[]{'C','R','V','2'},0,identity,84,4);put(identity,88,2,2);put(identity,90,32,2);put(identity,92,127,4);put(identity,96,7,8);put(identity,104,64,2);put(identity,106,1024,2);put(identity,108,248,2);crc(identity,84,28,112);
            status=vector(0);status[1]=2;crc(status,0,76,76);
        }
        byte[] vector(int n){int at=8+n*137+56;return Arrays.copyOfRange(golden,at,at+80);}
        public int mtu(){return 251;}
        public String deviceAddress(){return "C8:92:FF:DD:3B:CA";}
        public byte[] read(UUID id)throws IOException {if(id.equals(RecordingClient.DEVICE_STATUS))return identity.clone();if(id.equals(RecordingClient.MEETING_STATUS))return status.clone();throw new IOException("unexpected read");}
        public void subscribe(UUID id){}
        public void write(UUID id,byte[] value)throws IOException {
            if(id.equals(RecordingClient.RECORDING_CONTROL)&&value[1]==0x22){negotiation=value.clone();return;}
            if(!id.equals(RecordingClient.MEETING_CONTROL))throw new IOException("unexpected write");
            writes++;int n=value[5]==1?0:value[5]==4?2:value[5]==5?5:value[5]==2?8:-1;if(n<0)throw new IOException("unexpected command");
            status=vector(n);System.arraycopy(value,36,status,8,4);System.arraycopy(value,48,status,60,4);crc(status,0,76,76);
            if(loseAck){loseAck=false;throw new IOException("synthetic dropped confirmation");}
        }
        public byte[] await(UUID id,long timeout)throws IOException {if(id.equals(RecordingClient.RECORDING_CONTROL)&&negotiation!=null)return negotiation.clone();throw new java.net.SocketTimeoutException("synthetic timeout");}
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
        }
        System.out.println("NativeRecordingControl JNI fake-link test passed");
    }
}
