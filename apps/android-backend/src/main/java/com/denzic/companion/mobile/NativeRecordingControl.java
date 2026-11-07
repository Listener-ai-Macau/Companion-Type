package com.denzic.companion.mobile;

import java.io.IOException;
import java.net.SocketTimeoutException;
import java.nio.file.Path;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/** Worker-thread recording control bound to a selected Companion and durable host session. */
public final class NativeRecordingControl {
    private NativeRecordingControl() {}
    public enum Action { QUERY(0), START(1), STOP(2), PAUSE(4), RESUME(5); final int code;Action(int value){code=value;} }
    public static String newSessionId(){return UUID.randomUUID().toString();}
    private static native String executeNative(Callbacks callbacks,String privateRoot,String hostSession,String device,int command,int seconds) throws IOException;
    private static native String listNative(String privateRoot,String device,byte[] identity) throws IOException;
    private static native String adoptNative(Callbacks callbacks,String privateRoot,String device) throws IOException;
    private static native String reconcileNative(Callbacks callbacks,String privateRoot,String hostSession,String device) throws IOException;

    static String reconcile(RecordingClient client,RecordingClient.Link link,Path privateRoot,String hostSession,Path recordingDirectory) throws IOException {
        if(client==null||link==null||privateRoot==null||hostSession==null||hostSession.trim().isEmpty())throw new IllegalArgumentException("device, private directory and session required");
        try{System.loadLibrary("companion_mobile_audio");return reconcileNative(new Callbacks(link,client,recordingDirectory),privateRoot.toAbsolutePath().toString(),hostSession,link.deviceAddress());}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile recording control library is not installed for this device",error);}
    }

    static String adopt(RecordingClient.Link link,Path privateRoot) throws IOException {
        if(link==null||privateRoot==null)throw new IllegalArgumentException("device and private directory required");
        try{System.loadLibrary("companion_mobile_audio");return adoptNative(new Callbacks(link),privateRoot.toAbsolutePath().toString(),link.deviceAddress());}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile recording control library is not installed for this device",error);}
    }

    static String list(RecordingClient.Link link,Path privateRoot) throws IOException {
        if(link==null||privateRoot==null)throw new IllegalArgumentException("device and private directory required");
        try{System.loadLibrary("companion_mobile_audio");return listNative(privateRoot.toAbsolutePath().toString(),link.deviceAddress(),link.read(RecordingClient.DEVICE_STATUS));}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile recording control library is not installed for this device",error);}
    }

    static String execute(RecordingClient.Link link,Path privateRoot,String hostSession,Action action,int seconds) throws IOException {
        if(link==null||privateRoot==null||hostSession==null||hostSession.trim().isEmpty()||action==null)throw new IllegalArgumentException("device, private directory, session and action required");
        if(action==Action.START ? seconds<0||seconds>65535 : seconds!=0)throw new IllegalArgumentException("duration required only for start");
        try{System.loadLibrary("companion_mobile_audio");return executeNative(new Callbacks(link,action==Action.START),privateRoot.toAbsolutePath().toString(),hostSession,link.deviceAddress(),action.code,seconds);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile recording control library is not installed for this device",error);}
    }

    /** Calls on the same encrypted GATT link; native code holds the device's control lock. */
    public static final class Callbacks {
        private final RecordingClient.Link link;
        private final RecordingClient client;
        private final Path recordingDirectory;
        private final boolean preparingStart;
        Callbacks(RecordingClient.Link link){this(link,null,null,false);}
        Callbacks(RecordingClient.Link link,boolean preparingStart){this(link,null,null,preparingStart);}
        Callbacks(RecordingClient.Link link,RecordingClient client,Path recordingDirectory){this(link,client,recordingDirectory,false);}
        private Callbacks(RecordingClient.Link link,RecordingClient client,Path recordingDirectory,boolean preparingStart){this.link=link;this.client=client;this.recordingDirectory=recordingDirectory;this.preparingStart=preparingStart;}
        public byte[] identity() throws IOException{
            byte[] value=link.read(RecordingClient.DEVICE_STATUS);
            if(!preparingStart||!capacityRefreshing(value))return value;
            RecorderWire.Peer first=RecorderWire.Peer.fromStatus(value);
            long deadline=System.nanoTime()+1_000_000_000L;
            while(capacityRefreshing(value)){
                if(System.nanoTime()>=deadline)throw new IOException("录音卡正在更新剩余空间，请稍后再开始；没有发送开录命令。");
                try{Thread.sleep(25);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("录音准备已取消；没有发送开录命令。",error);}
                value=link.read(RecordingClient.DEVICE_STATUS);RecorderWire.Peer current=RecorderWire.Peer.fromStatus(value);
                if(current.epoch!=first.epoch||!java.util.Arrays.equals(current.uid(),first.uid()))throw new IOException("录音卡身份已变化，请重新连接；没有发送开录命令。");
            }
            return value;
        }
        private static boolean capacityRefreshing(byte[] value){
            return value!=null&&value.length>=84&&value[0]==1&&value[36]=='C'&&value[37]=='C'&&value[38]=='Q'&&value[39]=='2'&&value[40]==3&&(value[41]&3)==2;
        }
        public byte[] status() throws IOException{return link.read(RecordingClient.MEETING_STATUS);}
        public byte[][] catalogue() throws IOException {
            if(client==null)throw new IOException("recording directory is unavailable");
            java.util.List<RecorderWire.Descriptor> entries=client.listRecordings();byte[][] result=new byte[entries.size()][];
            for(int i=0;i<result.length;i++)result[i]=entries.get(i).wireBytes();return result;
        }
        public String[] localFiles() throws IOException {
            if(recordingDirectory==null)return new String[0];
            java.util.List<String> files=new java.util.ArrayList<>();
            if(!java.nio.file.Files.exists(recordingDirectory))return new String[0];
            try(java.nio.file.DirectoryStream<Path> metadata=java.nio.file.Files.newDirectoryStream(recordingDirectory,"*.meta")){
                for(Path item:metadata){
                    long metadataBytes=java.nio.file.Files.size(item);
                    if(metadataBytes!=112&&metadataBytes!=120)throw new IOException("invalid local recording metadata");
                    RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(java.nio.file.Files.readAllBytes(item));
                    String name=SegmentReceiver.key(descriptor);if(!item.getFileName().toString().equals(name+".meta"))throw new IOException("recording metadata filename mismatch");
                    Path file=recordingDirectory.resolve(name+".cop1");if(java.nio.file.Files.exists(file))files.add(file.toAbsolutePath().toString());
                }
            }
            return files.toArray(new String[0]);
        }
        public void writeControl(byte[] wire) throws IOException{link.write(RecordingClient.MEETING_CONTROL,wire);}
        public byte[] capacitySlots(byte[] request) throws IOException {
            link.write(RecordingClient.RECORDING_CONTROL,request);
            long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(2);
            while(true){long remaining=TimeUnit.NANOSECONDS.toMillis(deadline-System.nanoTime());if(remaining<=0)return null;
                byte[] reply;try{reply=link.await(RecordingClient.RECORDING_CONTROL,remaining);}catch(SocketTimeoutException e){return null;}
                if(reply!=null&&reply.length>=8&&reply[0]=='C'&&reply[1]=='S'&&reply[2]=='N'&&reply[3]=='1'&&
                    reply[4]==request[4]&&reply[5]==request[5]&&reply[6]==request[6]&&reply[7]==request[7])return reply;
            }
        }
    }
}
