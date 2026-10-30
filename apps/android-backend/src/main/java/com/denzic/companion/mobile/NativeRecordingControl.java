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
        if(action==Action.START ? seconds<=0||seconds>65535 : seconds!=0)throw new IllegalArgumentException("duration required only for start");
        try{System.loadLibrary("companion_mobile_audio");return executeNative(new Callbacks(link),privateRoot.toAbsolutePath().toString(),hostSession,link.deviceAddress(),action.code,seconds);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile recording control library is not installed for this device",error);}
    }

    /** Calls on the same encrypted GATT link; native code holds the device's control lock. */
    public static final class Callbacks {
        private final RecordingClient.Link link;
        Callbacks(RecordingClient.Link link){this.link=link;}
        public byte[] identity() throws IOException{return link.read(RecordingClient.DEVICE_STATUS);}
        public byte[] status() throws IOException{return link.read(RecordingClient.MEETING_STATUS);}
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
