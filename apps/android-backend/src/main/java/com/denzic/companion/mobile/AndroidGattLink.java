package com.denzic.companion.mobile;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.BluetoothStatusCodes;
import android.content.Context;
import android.os.Build;
import java.io.IOException;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Real Android GATT link. The app asks for Bluetooth permission and pairing. */
@SuppressLint("MissingPermission")
public final class AndroidGattLink implements RecordingClient.Link {
    private static final UUID STATUS_SERVICE=UUID.fromString("8f7a0001-7b7d-4f3d-9d6f-6c2d1b7c0000");
    private static final UUID RECORDING_SERVICE=UUID.fromString("8f7a0003-7b7d-4f3d-9d6f-6c2d1b7c0000");
    private static final UUID MEETING_SERVICE=UUID.fromString("8f7a0008-7b7d-4f3d-9d6f-6c2d1b7c0000");
    private static final UUID CCCD=UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    private static final class Event {
        final String kind;final UUID id;final int status,state;final byte[] data;
        Event(String kind,UUID id,int status,int state,byte[] data){this.kind=kind;this.id=id;this.status=status;this.state=state;this.data=data==null?null:data.clone();}
    }
    private final ArrayBlockingQueue<Event> operations=new ArrayBlockingQueue<>(64);
    private final Map<UUID,ArrayBlockingQueue<byte[]>> notifications=new ConcurrentHashMap<>();
    private volatile BluetoothGatt gatt;private volatile boolean connected;private final AtomicBoolean closed=new AtomicBoolean();private volatile String failure;
    private volatile int mtu=23;
    private void operation(Event e){if(!closed.get()&&!operations.offer(e))failure="Bluetooth operation queue overflow";}
    private void notification(UUID id,byte[] value){if(closed.get())return;ArrayBlockingQueue<byte[]> q=notifications.get(id);if(q!=null&&(value==null||!q.offer(value.clone())))failure="Bluetooth notification queue overflow";}
    private final BluetoothGattCallback callbacks=new BluetoothGattCallback(){
        @Override public void onConnectionStateChange(BluetoothGatt g,int status,int state){connected=status==BluetoothGatt.GATT_SUCCESS&&state==BluetoothProfile.STATE_CONNECTED;if(state==BluetoothProfile.STATE_DISCONNECTED)failure="Bluetooth disconnected";operation(new Event("connection",null,status,state,null));}
        @Override public void onServicesDiscovered(BluetoothGatt g,int status){operation(new Event("services",null,status,0,null));}
        @Override public void onMtuChanged(BluetoothGatt g,int value,int status){if(status==BluetoothGatt.GATT_SUCCESS)mtu=value;operation(new Event("mtu",null,status,value,null));}
        @Override public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,int status){operation(new Event("read",c.getUuid(),status,0,c.getValue()));}
        @Override public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,byte[] value,int status){operation(new Event("read",c.getUuid(),status,0,value));}
        @Override public void onCharacteristicWrite(BluetoothGatt g,BluetoothGattCharacteristic c,int status){operation(new Event("write",c.getUuid(),status,0,null));}
        @Override public void onDescriptorWrite(BluetoothGatt g,BluetoothGattDescriptor d,int status){operation(new Event("descriptor",d.getCharacteristic().getUuid(),status,0,null));}
        @Override public void onCharacteristicChanged(BluetoothGatt g,BluetoothGattCharacteristic c){notification(c.getUuid(),c.getValue());}
        @Override public void onCharacteristicChanged(BluetoothGatt g,BluetoothGattCharacteristic c,byte[] value){notification(c.getUuid(),value);}
    };
    private AndroidGattLink(){}

    /** Connect only a device the user has already selected and paired. Call off the main thread. */
    public static AndroidGattLink connect(Context context,BluetoothDevice device) throws IOException {
        if(context==null||device==null)throw new IllegalArgumentException("context and selected device required");
        if(Build.VERSION.SDK_INT<26)throw new IOException("Android 8 or newer required");
        AndroidGattLink link=new AndroidGattLink();boolean ready=false;
        try {
            if(device.getBondState()!=BluetoothDevice.BOND_BONDED)throw new IOException("pair the selected Companion device first");
            link.gatt=device.connectGatt(context.getApplicationContext(),false,link.callbacks,BluetoothDevice.TRANSPORT_LE);
            if(link.gatt==null)throw new IOException("Bluetooth connection could not start");
            Event connection=link.waitOperation("connection",null,15_000);if(connection.state!=BluetoothProfile.STATE_CONNECTED)throw new IOException("Bluetooth connection not established");
            if(!link.gatt.requestMtu(517))throw new IOException("Bluetooth MTU request refused");link.waitOperation("mtu",null,15_000);
            if(link.mtu<139)throw new IOException("Bluetooth MTU too small for recording directory");
            if(!link.gatt.discoverServices())throw new IOException("Bluetooth service discovery refused");link.waitOperation("services",null,15_000);
            ready=true;return link;
        } catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}
        finally{if(!ready)link.close();}
    }
    private void check() throws IOException {if(closed.get())throw new IOException("Bluetooth link closed");if(failure!=null)throw new IOException(failure);if(!connected)throw new IOException("Bluetooth not connected");}
    private Event waitOperation(String kind,UUID id,long timeout) throws IOException {
        long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(timeout);
        try{while(System.nanoTime()<deadline){if(closed.get())throw new IOException("Bluetooth link closed");if(failure!=null)throw new IOException(failure);Event e=operations.poll(100,TimeUnit.MILLISECONDS);if(e==null)continue;
            if(!e.kind.equals(kind)||(id!=null&&!id.equals(e.id)))continue;
            if(e.status!=BluetoothGatt.GATT_SUCCESS){failure="Bluetooth "+kind+" failed ("+e.status+")";throw new IOException(failure);}return e;}}
        catch(InterruptedException e){Thread.currentThread().interrupt();failure="Bluetooth operation interrupted";throw new IOException(failure,e);}
        failure="Bluetooth "+kind+" timed out";throw new IOException(failure);
    }
    private BluetoothGattCharacteristic characteristic(UUID id) throws IOException {
        UUID service=id.equals(RecordingClient.DEVICE_STATUS)?STATUS_SERVICE:
            (id.equals(RecordingClient.MEETING_CONTROL)||id.equals(RecordingClient.MEETING_STATUS)?MEETING_SERVICE:RECORDING_SERVICE);
        BluetoothGattService s=gatt.getService(service);BluetoothGattCharacteristic c=s==null?null:s.getCharacteristic(id);
        if(c==null)throw new IOException("Companion Bluetooth characteristic unavailable: "+id);return c;
    }
    @Override public int mtu(){return mtu;}
    @Override public String deviceAddress() throws IOException {
        check();try{return gatt.getDevice().getAddress();}catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}
    }
    @Override public synchronized byte[] read(UUID id) throws IOException {
        check();try{BluetoothGattCharacteristic c=characteristic(id);if((c.getProperties()&BluetoothGattCharacteristic.PROPERTY_READ)==0||!gatt.readCharacteristic(c))throw new IOException("Bluetooth read refused");Event e=waitOperation("read",id,15_000);if(e.data==null)throw new IOException("Bluetooth read returned no data");return e.data;}
        catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}
    }
    @Override public synchronized void subscribe(UUID id) throws IOException {
        check();try{BluetoothGattCharacteristic c=characteristic(id);if((c.getProperties()&BluetoothGattCharacteristic.PROPERTY_NOTIFY)==0)throw new IOException("Bluetooth notifications unavailable");
            BluetoothGattDescriptor d=c.getDescriptor(CCCD);if(d==null)throw new IOException("Bluetooth notification descriptor unavailable");
            notifications.put(id,new ArrayBlockingQueue<>(4096));if(!gatt.setCharacteristicNotification(c,true))throw new IOException("Bluetooth notification setup refused");
            boolean accepted;if(Build.VERSION.SDK_INT>=33)accepted=gatt.writeDescriptor(d,BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)==BluetoothStatusCodes.SUCCESS;
            else{d.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);accepted=gatt.writeDescriptor(d);}
            if(!accepted)throw new IOException("Bluetooth notification subscription refused");waitOperation("descriptor",id,15_000);
        }catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}
    }
    @Override public synchronized void write(UUID id,byte[] value) throws IOException {
        check();try{BluetoothGattCharacteristic c=characteristic(id);int type=id.equals(RecordingClient.RECORDING_PULL)?BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE:BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT;
            int property=type==BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE?BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE:BluetoothGattCharacteristic.PROPERTY_WRITE;
            if((c.getProperties()&property)==0)throw new IOException("Bluetooth write mode unavailable");boolean accepted;
            if(Build.VERSION.SDK_INT>=33)accepted=gatt.writeCharacteristic(c,value,type)==BluetoothStatusCodes.SUCCESS;
            else{c.setWriteType(type);c.setValue(value);accepted=gatt.writeCharacteristic(c);}
            if(!accepted)throw new IOException("Bluetooth write refused");waitOperation("write",id,15_000);
        }catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}
    }
    @Override public byte[] await(UUID id,long timeoutMillis) throws IOException {
        if(timeoutMillis<=0)throw new IOException("Bluetooth wait timed out");ArrayBlockingQueue<byte[]> q=notifications.get(id);if(q==null)throw new IOException("Bluetooth notifications not subscribed");long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(timeoutMillis);
        try{while(System.nanoTime()<deadline){check();byte[] p=q.poll(100,TimeUnit.MILLISECONDS);if(p!=null)return p;}}
        catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("Bluetooth wait interrupted",e);}throw new java.net.SocketTimeoutException("Bluetooth notification timed out");
    }
    @Override public void close() {if(!closed.compareAndSet(false,true))return;BluetoothGatt g=gatt;if(g!=null){try{g.disconnect();}catch(SecurityException ignored){}try{g.close();}catch(SecurityException ignored){}}}
}
