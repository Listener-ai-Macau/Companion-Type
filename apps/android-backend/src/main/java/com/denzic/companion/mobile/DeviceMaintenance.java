package com.denzic.companion.mobile;

import java.io.IOException;
import java.util.UUID;
import static com.denzic.companion.mobile.RecorderWire.*;

/** Existing encrypted CRM1 maintenance, serialized with the recording client. */
public final class DeviceMaintenance {
    private DeviceMaintenance() {}
    static final UUID CONTROL=UUID.fromString("8f7a4003-7b7d-4f3d-9d6f-6c2d1b7c0000");
    public enum Operation {QUERY,OPEN_PAIRING,RESTORE_SETTINGS,CLEAR_PAIRINGS}
    public static final class Status {
        public final Operation operation;
        public final boolean settingsSaved,defaultSettings,radioEnabled,bondCountValid;
        public final int bonds;
        public final long preferencesGeneration,bondGeneration;
        private Status(Operation operation,byte[] p) {
            this.operation=operation;int flags=u8(p,6);settingsSaved=(flags&1)!=0;defaultSettings=(flags&2)!=0;
            bondCountValid=(flags&4)!=0;radioEnabled=(flags&8)!=0;bonds=u8(p,7);
            preferencesGeneration=u32(p,12);bondGeneration=u32(p,20);
        }
    }
    static byte[] request(Operation op,long nonce)throws IOException {
        if(op==null||nonce==0)throw new IOException("设备维护请求无效");
        byte[] p=new byte[16];System.arraycopy(new byte[]{'C','R','M','1'},0,p,0,4);p[4]=(byte)op.ordinal();put32(p,8,nonce);put32(p,12,crc(p,0,12));return p;
    }
    static Status perform(RecordingClient.Link link,Operation operation,long nonce)throws IOException {
        link.subscribe(CONTROL);link.write(CONTROL,request(operation,nonce));
        long deadline=System.nanoTime()+20_000_000_000L;
        while(true) {
            long remaining=(deadline-System.nanoTime())/1_000_000L;
            if(remaining<=0)throw new IOException("设备维护结果尚未确认，请重新连接后读取状态");
            byte[] p;
            try{p=link.await(CONTROL,Math.min(remaining,8000));}catch(java.net.SocketTimeoutException e){continue;}
            if(p==null||p.length!=32||!magic(p,0,"CRM1")||u8(p,4)!=operation.ordinal()||u32(p,8)!=nonce)continue;
            if(u32(p,28)!=crc(p,0,28))throw new IOException("设备维护回执校验失败，请重新读取状态");
            int result=u8(p,5);if(result==1)continue;
            if(result==2)throw new IOException("设备正在录音或整理存储，请完成后再操作；录音没有停止");
            if(result!=0)throw new IOException("设备维护未完成，请重新连接后读取状态");
            return new Status(operation,p);
        }
    }
}
