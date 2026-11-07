package com.denzic.companion.mobile;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
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
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Real Android GATT link. The app asks for Bluetooth permission and pairing. */
@SuppressLint("MissingPermission")
public final class AndroidGattLink implements RecordingClient.Link {
    private static final UUID STATUS_SERVICE=UUID.fromString("8f7a0001-7b7d-4f3d-9d6f-6c2d1b7c0000");
    private static final UUID SETTINGS_SERVICE=UUID.fromString("8f7a0004-7b7d-4f3d-9d6f-6c2d1b7c0000");
    private static final UUID RECORDING_SERVICE=UUID.fromString("8f7a0003-7b7d-4f3d-9d6f-6c2d1b7c0000");
    private static final UUID PRIVACY_SERVICE=UUID.fromString("8f7a0006-7b7d-4f3d-9d6f-6c2d1b7c0000");
    private static final UUID MEETING_SERVICE=UUID.fromString("8f7a0008-7b7d-4f3d-9d6f-6c2d1b7c0000");
    private static final UUID CCCD=UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    private static final class Event {
        final String kind;final UUID id;final int status,state;final byte[] data;
        Event(String kind,UUID id,int status,int state,byte[] data){this.kind=kind;this.id=id;this.status=status;this.state=state;this.data=data==null?null:data.clone();}
    }
    private final ArrayBlockingQueue<Event> operations=new ArrayBlockingQueue<>(64);
    private final Map<UUID,ArrayBlockingQueue<byte[]>> notifications=new ConcurrentHashMap<>();
    private volatile BluetoothGatt gatt;private volatile boolean connected;private volatile boolean disconnected;private final AtomicBoolean closed=new AtomicBoolean();private volatile String failure;
    private volatile int mtu=23;
    private volatile int initialConnectionStatus=-1;
    private volatile boolean connectedOnce;
    private boolean calendarSupported;
    private final CountDownLatch disconnectAcknowledged=new CountDownLatch(1);
    private final long traceStartedNanos=System.nanoTime();
    private Context traceContext;
    private volatile String traceStage="construct",connectError="";
    private volatile int callbackStatus=-1,callbackState=-1;
    private int inputAddressType=-1,requestedAddressType=-1;
    private long closeElapsedNanos;
    private GattConnectionOwner connectionOwner;
    private long ownerWaitNanos;
    private final GattBulkPriority bulkPriority=new GattBulkPriority(this::requestBulkPriority,(millis,task)->{
        android.os.Handler handler=new android.os.Handler(android.os.Looper.getMainLooper());
        handler.postDelayed(task,millis);return ()->handler.removeCallbacks(task);
    });
    private void operation(Event e){if(!closed.get()&&!operations.offer(e))failure="Bluetooth operation queue overflow";}
    private void notification(UUID id,byte[] value){if(closed.get())return;ArrayBlockingQueue<byte[]> q=notifications.get(id);if(q!=null&&(value==null||!q.offer(value.clone())))failure="Bluetooth notification queue overflow";}
    private final BluetoothGattCallback callbacks=new BluetoothGattCallback(){
        @Override public void onConnectionStateChange(BluetoothGatt g,int status,int state){
            callbackStatus=status;callbackState=state;
            if(status!=BluetoothGatt.GATT_SUCCESS&&!connectedOnce)initialConnectionStatus=status;
            connected=status==BluetoothGatt.GATT_SUCCESS&&state==BluetoothProfile.STATE_CONNECTED;
            if(connected)connectedOnce=true;
            if(state==BluetoothProfile.STATE_DISCONNECTED){disconnected=true;failure="Bluetooth disconnected";disconnectAcknowledged.countDown();}
            operation(new Event("connection",null,status,state,null));
        }
        @Override public void onServicesDiscovered(BluetoothGatt g,int status){operation(new Event("services",null,status,0,null));}
        @Override public void onMtuChanged(BluetoothGatt g,int value,int status){if(status==BluetoothGatt.GATT_SUCCESS)mtu=value;operation(new Event("mtu",null,status,value,null));}
        @Override public void onPhyUpdate(BluetoothGatt g,int txPhy,int rxPhy,int status){android.util.Log.i("CompanionBle","phy tx="+txPhy+" rx="+rxPhy+" status="+status);}
        @Override public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,int status){operation(new Event("read",c.getUuid(),status,0,c.getValue()));}
        @Override public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,byte[] value,int status){operation(new Event("read",c.getUuid(),status,0,value));}
        @Override public void onCharacteristicWrite(BluetoothGatt g,BluetoothGattCharacteristic c,int status){operation(new Event("write",c.getUuid(),status,0,null));}
        @Override public void onDescriptorWrite(BluetoothGatt g,BluetoothGattDescriptor d,int status){operation(new Event("descriptor",d.getCharacteristic().getUuid(),status,0,null));}
        @Override public void onCharacteristicChanged(BluetoothGatt g,BluetoothGattCharacteristic c){notification(c.getUuid(),c.getValue());}
        @Override public void onCharacteristicChanged(BluetoothGatt g,BluetoothGattCharacteristic c,byte[] value){notification(c.getUuid(),value);}
    };
    private AndroidGattLink(){}
    /** Android15 can wrap a dead Bluetooth Binder in RuntimeException.
     * Only that transport failure is retryable; programming/security errors
     * retain their existing behavior instead of being hidden by a broad catch. */
    static boolean deadBluetoothService(Throwable error){
        for(int depth=0;error!=null&&depth<16;depth++,error=error.getCause())
            if(error instanceof android.os.DeadObjectException)return true;
        return false;
    }
    static RecordingSyncRunner.LinkFailure recoverablePlatformFailure(RuntimeException error){
        if(error instanceof SecurityException||!deadBluetoothService(error))throw error;
        RecordingSyncRunner.LinkFailure failure=new RecordingSyncRunner.LinkFailure("Bluetooth service became unavailable");
        failure.initCause(error);return failure;
    }
    private RecordingSyncRunner.LinkFailure platformFailure(RuntimeException error){
        RecordingSyncRunner.LinkFailure failure=recoverablePlatformFailure(error);
        connectError=failure.getMessage();return failure;
    }

    /** Connect only a device the user has already selected and paired. Call off the main thread. */
    public static AndroidGattLink connect(Context context,BluetoothDevice device) throws IOException {
        return connectWithInitialRetry(context,device,139,true);
    }
    private static AndroidGattLink connectWithInitialRetry(Context context,BluetoothDevice device,int minimumMtu,boolean synchronizeClock)throws IOException {
        return connectWithInitialRetry(context,device,minimumMtu,synchronizeClock,15_000);
    }
    private static AndroidGattLink connectWithInitialRetry(Context context,BluetoothDevice device,int minimumMtu,boolean synchronizeClock,long connectionWaitMs)throws IOException {
        java.util.concurrent.atomic.AtomicReference<BluetoothDevice> rediscovered=new java.util.concurrent.atomic.AtomicReference<>();
        try{return InitialConnectionRetry.open(()->connect(context,rediscovered.get()==null?device:rediscovered.get(),minimumMtu,synchronizeClock,rediscovered.get()!=null,connectionWaitMs),millis->{
            android.util.Log.w("CompanionBle","Initial GATT133 refused before connection; closed client, retrying once");
            rediscovered.set(AndroidDevices.refreshSelected(context,device,millis));
        });}catch(RuntimeException died){throw recoverablePlatformFailure(died);}
    }
    /** Upgrade uses the same bonded GATT owner with no recording negotiation or
     * clock write. Read-back verification must not modify the new application. */
    public static AndroidGattLink connectForUpdate(Context context,BluetoothDevice device)throws IOException{return connectWithInitialRetry(context,device,23,false);}
    public static SystemUpdateClient.Connector updateConnector(Context context,BluetoothDevice device){
        return new SystemUpdateClient.Connector(){
            public RecordingClient.Link connect()throws IOException{return connectForUpdate(context,device);}
            public RecordingClient.Link connectForVerification()throws IOException{
                // Boot installation is deliberately unavailable to GATT. Do
                // not spend another15s blind wait after advertising returns.
                // Every failed attempt still disconnects/closes its exact owner.
                return connectWithInitialRetry(context,device,23,false,2_000);
            }
        };
    }
    private static AndroidGattLink connect(Context context,BluetoothDevice device,int minimumMtu,boolean synchronizeClock,boolean rediscovered,long connectionWaitMs) throws IOException {
        if(context==null||device==null)throw new IllegalArgumentException("context and selected device required");
        if(Build.VERSION.SDK_INT<26)throw new RecordingSyncRunner.ActionRequired("需要 Android 8 或更新的系统才能接收录音");
        AndroidGattLink link=new AndroidGattLink();boolean ready=false;
        link.traceContext=context.getApplicationContext();
        try {
            link.traceStage="wait_previous_owner";
            long ownerStarted=System.nanoTime();
            try{link.connectionOwner=GattConnectionOwner.acquire(device.getAddress());}
            finally{link.ownerWaitNanos=System.nanoTime()-ownerStarted;}
            if(Build.VERSION.SDK_INT>=35)link.inputAddressType=device.getAddressType();
            // The Companion WBA port explicitly uses GAP_STATIC_RANDOM_ADDR
            // in app_ble.c. Rebuild that LE identity after process/radio/OTA
            // recovery instead of losing its type in getRemoteDevice(String).
            // Older Android keeps the original discovered/bonded object.
            if(Build.VERSION.SDK_INT>=33&&!rediscovered){
                android.bluetooth.BluetoothManager manager=(android.bluetooth.BluetoothManager)context.getSystemService(Context.BLUETOOTH_SERVICE);
                BluetoothAdapter adapter=manager==null?null:manager.getAdapter();
                if(adapter!=null){device=adapter.getRemoteLeDevice(device.getAddress(),BluetoothDevice.ADDRESS_TYPE_RANDOM);link.requestedAddressType=BluetoothDevice.ADDRESS_TYPE_RANDOM;}
            }
            if(device.getBondState()!=BluetoothDevice.BOND_BONDED)throw new RecordingSyncRunner.ActionRequired("录音卡已取消配对，请重新配对后继续接收");
            link.traceStage="connect";
            link.gatt=device.connectGatt(context.getApplicationContext(),false,link.callbacks,BluetoothDevice.TRANSPORT_LE);
            if(link.gatt==null)throw new RecordingSyncRunner.LinkFailure("Bluetooth connection could not start");
            link.traceStage="wait_connection";
            Event connection=link.waitOperation("connection",null,connectionWaitMs);if(connection.state!=BluetoothProfile.STATE_CONNECTED)throw new RecordingSyncRunner.LinkFailure("Bluetooth connection not established");
            link.traceStage="mtu";
            if(!link.gatt.requestMtu(517))throw new RecordingSyncRunner.LinkFailure("Bluetooth MTU request refused");link.waitOperation("mtu",null,15_000);
            if(link.mtu<minimumMtu)throw new RecordingSyncRunner.ActionRequired("蓝牙连接容量不足，请重新连接或换用兼容的手机；原录音仍保留");
            link.traceStage="services";
            if(!link.gatt.discoverServices())throw new RecordingSyncRunner.LinkFailure("Bluetooth service discovery refused");link.waitOperation("services",null,15_000);
            BluetoothGattService settings=link.gatt.getService(SETTINGS_SERVICE);
            if(synchronizeClock&&settings!=null&&settings.getCharacteristic(DeviceClock.SETTINGS)!=null){
                link.traceStage="clock";
                byte[] clock=DeviceClock.payload(link.read(DeviceClock.SETTINGS),System.currentTimeMillis()/1000L);
                link.calendarSupported=clock.length==17;
                link.write(DeviceClock.SETTINGS,clock);
                DeviceClock.verify(clock,link.read(DeviceClock.SETTINGS));
            }
            // Share the existing fast radio preference across recording and OTA.
            // Android/controller coexistence policy decides the actual PHY;
            // WOC5 readback records what was negotiated, not this preference.
            link.gatt.setPreferredPhy(BluetoothDevice.PHY_LE_2M_MASK,BluetoothDevice.PHY_LE_2M_MASK,BluetoothDevice.PHY_OPTION_NO_PREFERRED);
            link.traceStage="ready";ready=true;return link;
        } catch(IOException e){link.connectError=e.getMessage()==null?e.getClass().getSimpleName():e.getMessage();throw e;}
        catch(SecurityException e){link.connectError="Bluetooth permission is required";throw new IOException("Bluetooth permission is required",e);}
        catch(RuntimeException e){throw link.platformFailure(e);}
        finally{if(!ready)link.close();}
    }
    private void check() throws IOException {if(closed.get())throw new RecordingSyncRunner.LinkFailure("Bluetooth link closed");if(failure!=null)throw new RecordingSyncRunner.LinkFailure(failure);if(!connected)throw new RecordingSyncRunner.LinkFailure("Bluetooth not connected");}
    private Event waitOperation(String kind,UUID id,long timeout) throws IOException {
        long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(timeout);
        try{while(System.nanoTime()<deadline){if(closed.get())throw new RecordingSyncRunner.LinkFailure("Bluetooth link closed");if(kind.equals("connection")&&initialConnectionStatus>0)throw new InitialConnectionRetry.Refused(initialConnectionStatus);if(failure!=null)throw new RecordingSyncRunner.LinkFailure(failure);Event e=operations.poll(100,TimeUnit.MILLISECONDS);if(e==null)continue;
            if(!e.kind.equals(kind)||(id!=null&&!id.equals(e.id)))continue;
            if(e.status!=BluetoothGatt.GATT_SUCCESS){failure="Bluetooth "+kind+" failed ("+e.status+")";if(kind.equals("connection")&&!connectedOnce)throw new InitialConnectionRetry.Refused(e.status);throw new RecordingSyncRunner.LinkFailure(failure);}return e;}}
        catch(InterruptedException e){Thread.currentThread().interrupt();failure="Bluetooth operation interrupted";throw new IOException(failure,e);}
        failure="Bluetooth "+kind+" timed out";throw new java.net.SocketTimeoutException(failure);
    }
    private BluetoothGattCharacteristic characteristic(UUID id) throws IOException {
        UUID service=(id.equals(SystemUpdateClient.CONTROL)||id.equals(SystemUpdateClient.DATA)||id.equals(SystemUpdateClient.STATUS)||id.equals(SystemUpdateClient.IDENTITY))?SystemUpdateClient.SERVICE:id.equals(SystemUpdateClient.READINESS)?SystemUpdateClient.READINESS_SERVICE:
            (id.equals(DeviceClock.SETTINGS)||id.equals(DeviceMaintenance.CONTROL))?SETTINGS_SERVICE:id.equals(RecordingClient.DEVICE_STATUS)?STATUS_SERVICE:id.equals(RecordingClient.RECORDING_CONSUME)?PRIVACY_SERVICE:
            (id.equals(RecordingClient.MEETING_CONTROL)||id.equals(RecordingClient.MEETING_STATUS)?MEETING_SERVICE:RECORDING_SERVICE);
        BluetoothGattService s=gatt.getService(service);BluetoothGattCharacteristic c=s==null?null:s.getCharacteristic(id);
        if(c==null)throw new IOException("Companion Bluetooth characteristic unavailable: "+id);return c;
    }
    boolean wasDisconnected(){return disconnected;}
    @Override public boolean disconnected(){return disconnected;}
    @Override public boolean isConnected(){return connected&&!closed.get()&&failure==null;}
    @Override public int mtu(){return mtu;}
    @Override public boolean calendarSupported(){return calendarSupported;}
    @Override public String deviceAddress() throws IOException {
        check();try{return gatt.getDevice().getAddress();}catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}catch(RuntimeException e){throw platformFailure(e);}
    }
    @Override public synchronized byte[] read(UUID id) throws IOException {
        check();try{BluetoothGattCharacteristic c=characteristic(id);if((c.getProperties()&BluetoothGattCharacteristic.PROPERTY_READ)==0)throw new IOException("Bluetooth read unavailable");if(!gatt.readCharacteristic(c))throw new RecordingSyncRunner.LinkFailure("Bluetooth read refused");Event e=waitOperation("read",id,15_000);if(e.data==null)throw new RecordingSyncRunner.LinkFailure("Bluetooth read returned no data");return e.data;}
        catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}catch(RuntimeException e){throw platformFailure(e);}
    }
    @Override public synchronized void subscribe(UUID id) throws IOException {
        check();try{BluetoothGattCharacteristic c=characteristic(id);if((c.getProperties()&BluetoothGattCharacteristic.PROPERTY_NOTIFY)==0)throw new IOException("Bluetooth notifications unavailable");
            BluetoothGattDescriptor d=c.getDescriptor(CCCD);if(d==null)throw new IOException("Bluetooth notification descriptor unavailable");
            notifications.put(id,new ArrayBlockingQueue<>(4096));if(!gatt.setCharacteristicNotification(c,true))throw new RecordingSyncRunner.LinkFailure("Bluetooth notification setup refused");
            boolean accepted;if(Build.VERSION.SDK_INT>=33)accepted=gatt.writeDescriptor(d,BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)==BluetoothStatusCodes.SUCCESS;
            else{d.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);accepted=gatt.writeDescriptor(d);}
            if(!accepted)throw new RecordingSyncRunner.LinkFailure("Bluetooth notification subscription refused");waitOperation("descriptor",id,15_000);
        }catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}catch(RuntimeException e){throw platformFailure(e);}
    }
    static int writeTypeFor(UUID id,int properties) {
        return id.equals(RecordingClient.RECORDING_PULL)||(id.equals(SystemUpdateClient.DATA)&&(properties&BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE)!=0)?BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE:BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT;
    }
    @Override public String otaDataWriteMode()throws IOException {
        return writeTypeFor(SystemUpdateClient.DATA,characteristic(SystemUpdateClient.DATA).getProperties())==BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE?"without_response":"with_response";
    }
    @Override public synchronized void write(UUID id,byte[] value) throws IOException {
        check();try{BluetoothGattCharacteristic c=characteristic(id);int type=writeTypeFor(id,c.getProperties());
            int property=type==BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE?BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE:BluetoothGattCharacteristic.PROPERTY_WRITE;
            if((c.getProperties()&property)==0)throw new IOException("Bluetooth write mode unavailable");boolean accepted;
            if(Build.VERSION.SDK_INT>=33)accepted=gatt.writeCharacteristic(c,value,type)==BluetoothStatusCodes.SUCCESS;
            else{c.setWriteType(type);c.setValue(value);accepted=gatt.writeCharacteristic(c);}
            if(!accepted)throw new RecordingSyncRunner.LinkFailure("Bluetooth write refused");waitOperation("write",id,15_000);
        }catch(SecurityException e){throw new IOException("Bluetooth permission is required",e);}catch(RuntimeException e){throw platformFailure(e);}
    }
    @Override public boolean primeBulkTransfer()throws IOException {check();return bulkPriority.prime();}
    @Override public boolean preferBulkTransfer(boolean active)throws IOException {check();return bulkPriority.transfer(active);}
    private boolean requestBulkPriority(boolean active)throws IOException {
        check();
        try{
            boolean accepted=gatt.requestConnectionPriority(active?BluetoothGatt.CONNECTION_PRIORITY_HIGH:BluetoothGatt.CONNECTION_PRIORITY_BALANCED);
            android.util.Log.i("CompanionBle","central priority="+(active?"high":"balanced")+" requestAccepted="+accepted);
            return accepted;
        }catch(SecurityException denied){throw new IOException("Bluetooth permission is required",denied);}
        catch(RuntimeException died){throw platformFailure(died);}
    }
    @Override public byte[] await(UUID id,long timeoutMillis) throws IOException {
        if(timeoutMillis<=0)throw new java.net.SocketTimeoutException("Bluetooth wait timed out");ArrayBlockingQueue<byte[]> q=notifications.get(id);if(q==null)throw new IOException("Bluetooth notifications not subscribed");long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(timeoutMillis);
        try{while(System.nanoTime()<deadline){check();byte[] p=q.poll(100,TimeUnit.MILLISECONDS);if(p!=null)return p;}}
        catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("Bluetooth wait interrupted",e);}throw new java.net.SocketTimeoutException("Bluetooth notification timed out");
    }
    private void saveCloseTrace(){
        // Two overwritten, app-private metadata records; no payload or
        // per-packet logging. Keep the last failure even after cleanup works.
        if(traceContext==null)return;
        try{
            String error=connectError.length()>240?connectError.substring(0,240):connectError;
            org.json.JSONObject trace=new org.json.JSONObject().put("schema",1).put("stage",traceStage)
                .put("startedNanos",traceStartedNanos).put("closedNanos",System.nanoTime())
                .put("connectedOnce",connectedOnce).put("initialConnectionStatus",initialConnectionStatus)
                    .put("callbackStatus",callbackStatus).put("callbackState",callbackState).put("mtu",mtu)
                    .put("inputAddressType",inputAddressType).put("requestedAddressType",requestedAddressType)
                .put("disconnectAcknowledged",disconnectAcknowledged.getCount()==0)
                .put("closeElapsedNanos",closeElapsedNanos).put("connectError",error);
            trace.put("ownerWaitNanos",ownerWaitNanos).put("ownerReleased",connectionOwner==null);
            android.content.SharedPreferences.Editor editor=traceContext.getSharedPreferences("companion_ble_diagnostics",Context.MODE_PRIVATE).edit().putString("last",trace.toString());
            if(!error.isEmpty())editor.putString("lastConnectionFailure",trace.toString());
            editor.apply();
        }catch(Exception diagnosticUnavailable){/* Metadata must not block client release. */}
    }
    @Override public void close() {
        if(!closed.compareAndSet(false,true))return;
        bulkPriority.close();
        final BluetoothGatt g=gatt;long started=System.nanoTime();
        try{
            if(g!=null)GattCloseAwait.close(new GattCloseAwait.Port(){
                public boolean disconnect(){try{g.disconnect();return true;}catch(SecurityException denied){return false;}catch(RuntimeException died){if(!deadBluetoothService(died))throw died;return false;}}
                public void close(){try{g.close();}catch(SecurityException ignored){}catch(RuntimeException died){if(!deadBluetoothService(died))throw died;}}
            },disconnectAcknowledged);
        }finally{
            if(connectionOwner!=null){connectionOwner.close();connectionOwner=null;}
            closeElapsedNanos=System.nanoTime()-started;saveCloseTrace();
        }
    }
}
