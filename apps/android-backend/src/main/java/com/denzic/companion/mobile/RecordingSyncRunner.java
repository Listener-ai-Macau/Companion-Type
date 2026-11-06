package com.denzic.companion.mobile;

import java.io.Closeable;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicBoolean;

/** Follow one selected session until completion, an actionable failure, or user stop. */
final class RecordingSyncRunner {
    /** Permission or pairing must be fixed by the user before retrying. */
    static final class ActionRequired extends IOException {
        ActionRequired(String message){super(message);}
        ActionRequired(String message,Throwable cause){super(message,cause);}
    }
    /** A failed Android GATT operation; local files and protocol errors are not link failures. */
    static class LinkFailure extends IOException {
        LinkFailure(String message){super(message);}
    }
    static final class BluetoothOff extends IOException {}
    private static boolean permissionDenied(Throwable error) {
        for(int depth=0;error!=null && depth<16;depth++,error=error.getCause())
            if(error instanceof SecurityException)return true;
        return false;
    }
    private static boolean linkFailure(Throwable error) {
        for(int depth=0;error!=null && depth<16;depth++,error=error.getCause())
            if(error instanceof LinkFailure || error instanceof java.net.SocketTimeoutException)return true;
        return false;
    }
    interface Connector { Connection connect() throws IOException; }
    interface Connection extends Closeable {
        RecordingLibrary.Session sync() throws IOException;
        boolean disconnected();
    }
    interface Listener {
        void status(String state, String detail);
        void finished(RecordingLibrary.Session session);
    }
    interface Delay { void waitMillis(long millis) throws InterruptedException; }
    private final Connector connector;
    private final Listener listener;
    private final Delay delay;
    private final AtomicBoolean stopped = new AtomicBoolean();
    private volatile Connection active;
    private volatile Thread worker;

    RecordingSyncRunner(Connector connector, Listener listener) { this(connector,listener,Thread::sleep); }
    RecordingSyncRunner(Connector connector, Listener listener, Delay delay) {
        this.connector=connector;this.listener=listener;this.delay=delay;
    }
    // A card can become available just after a failed attempt. Keep the
    // next attempt within the normal15s recovery budget, including GATT
    // setup; a30s sleep alone cannot meet it. User stop still interrupts.
    private static final long LINK_RETRY_MILLIS=5000,ADAPTER_WAIT_MILLIS=1000;
    void stop() {
        stopped.set(true);
        Connection c=active;if(c!=null)try{c.close();}catch(IOException ignored){}
        Thread t=worker;if(t!=null)t.interrupt();
    }
    void run() {
        worker=Thread.currentThread();
        try {
            while(!stopped.get()) {
                listener.status("connecting", "正在连接录音卡");
                Connection c;
                try { c=connector.connect(); }
                catch(IOException e) {
                    if(stopped.get()) break;
                    if(permissionDenied(e)){listener.status("error","请允许蓝牙连接后继续接收");return;}
                    if(e instanceof ActionRequired){listener.status("error",e.getMessage());return;}
                    if(!(e instanceof BluetoothOff) && !linkFailure(e)) {
                        listener.status("error","无法读取录音卡信息，请检查设备兼容性及连接后重试；已保存的录音保留");
                        return;
                    }
                    if(e instanceof BluetoothOff){
                        // Adapter-off time is not a failed GATT attempt. Keep
                        // a bounded availability check without increasing the
                        // radio-failure backoff to30s after Bluetooth returns.
                        listener.status("waiting_bluetooth","请开启手机蓝牙，已保存的录音会保留；开启后自动继续接收");
                        delay.waitMillis(ADAPTER_WAIT_MILLIS);continue;
                    }
                    listener.status("reconnecting","等待录音卡重新连接，已保存的录音会保留");
                    delay.waitMillis(LINK_RETRY_MILLIS);continue;
                }
                active=c;
                if(stopped.get()){try{c.close();}catch(IOException ignored){}break;}
                boolean reconnect=false;
                try {
                    while(!stopped.get()) {
                        listener.status("syncing","正在保存录音");
                        RecordingLibrary.Session session=c.sync();
                        RecorderWire.Descriptor last=session.segments.get(session.segments.size()-1).descriptor;
                        if((last.flags&2)!=0){listener.finished(session);return;}
                        listener.status("following","录音进行中，等待下一段");
                        delay.waitMillis(2000);
                    }
                } catch(IOException e) {
                    if(stopped.get())break;
                    if(permissionDenied(e)){listener.status("error","请允许蓝牙连接后继续接收");return;}
                    if(e instanceof ActionRequired){listener.status("error",e.getMessage());return;}
                    // A stalled GATT operation can time out before Android reports a disconnect.
                    // Close that link and resume the same durable session on a fresh connection.
                    // Disconnect may happen at the same time as a disk or
                    // protocol failure. Retry only a classified link error;
                    // AndroidGattLink tags actual disconnects and timeouts.
                    if(!linkFailure(e)){listener.status("error",e.getMessage()==null?"接收未完成，可稍后继续":e.getMessage());return;}
                    listener.status("reconnecting","等待录音卡重新连接，已保存的录音会保留");
                    reconnect=true;
                } finally {active=null;try{c.close();}catch(IOException ignored){}}
                if(reconnect)delay.waitMillis(LINK_RETRY_MILLIS);
            }
        } catch(InterruptedException e) {Thread.currentThread().interrupt();}
        finally {worker=null;if(stopped.get())listener.status("stopped","已停止接收，已保存的录音保留在手机中");}
    }
}
