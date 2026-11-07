package com.denzic.companion.mobile;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.util.Base64;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;

/** User-started transfer of one selected recording session, including while the app is backgrounded. */
public final class RecordingSyncService extends Service {
    private static final String START="com.denzic.companion.sync.START", STOP="com.denzic.companion.sync.STOP";
    private static final String PREFS="companion_recording_sync", CHANNEL="companion_recording_sync", ADDRESS="address", DESCRIPTOR="descriptor", DIRECTORY="directory";
    private static final int NOTIFICATION=0x434f4d;
    private static boolean startingOrRunning;
    private static volatile RecordingClient activeClient;
    private static RecordingClient pendingClient;
    private static String pendingAddress;
    private static byte[] pendingDescriptor;
    private static synchronized RecordingClient takePending(String address,byte[] descriptor)throws IOException {
        if(pendingClient==null)return null;
        if(!address.equals(pendingAddress)||!java.util.Arrays.equals(descriptor,pendingDescriptor)){
            closePending();throw new IOException("selected connection handoff changed");
        }
        RecordingClient client=pendingClient;pendingClient=null;pendingAddress=null;pendingDescriptor=null;return client;
    }
    private static synchronized void closePending(){
        RecordingClient client=pendingClient;pendingClient=null;pendingAddress=null;pendingDescriptor=null;
        if(client!=null)try{client.close();}catch(IOException ignored){}
    }
    private RecordingSyncRunner runner;
    private volatile RecordingTransferMetrics transferMetrics;
    private volatile int runningStartId;
    private boolean workerDone;
    private volatile boolean destroyed;

    /** Start while the host activity is visible and Bluetooth permission has been granted. */
    public static void start(Context context, BluetoothDevice device, RecorderWire.Descriptor selected, File recordingDirectory) throws IOException {
        start(context,device,selected,recordingDirectory,null);
    }
    /** Consumes ownership of an optional already verified activity connection.
     * Saved selection still permits a fresh connection after process death. */
    public static void start(Context context,BluetoothDevice device,RecorderWire.Descriptor selected,File recordingDirectory,RecordingClient connection)throws IOException {
        try{startOwned(context,device,selected,recordingDirectory,connection);}
        catch(IOException|RuntimeException error){if(connection!=null)try{connection.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private static void startOwned(Context context,BluetoothDevice device,RecorderWire.Descriptor selected,File recordingDirectory,RecordingClient connection)throws IOException {
        if(context==null||device==null||selected==null||recordingDirectory==null)throw new IllegalArgumentException("device, recording and directory required");
        File parent=context.getFilesDir().getCanonicalFile();File directory=recordingDirectory.getCanonicalFile();
        if(!parent.equals(directory.getParentFile())||!directory.isDirectory())throw new IOException("录音目录必须是应用私有目录中已存在的直接子目录");
        RecorderWire.Descriptor pending=RecordingLibrary.pendingConfirmation(directory.toPath());
        if(pending!=null&&!RecordingLibrary.sameSession(pending,selected))
            throw new IOException("另一场录音的设备确认尚未完成，请先继续接收那场录音；已保存的录音均保留");
        final String address;
        try {address=device.getAddress();}catch(SecurityException e){throw new IOException("请允许蓝牙连接",e);}
        final byte[] wire=selected.wireBytes();
        Intent intent=new Intent(context,RecordingSyncService.class).setAction(START).putExtra(ADDRESS,address)
                .putExtra(DESCRIPTOR,wire).putExtra(DIRECTORY,directory.getName());
        if(connection!=null)connection.validateHandoff(address,selected);
        synchronized(RecordingSyncService.class){if(startingOrRunning)throw new IOException("已有录音正在接收，请先停止或等待完成");startingOrRunning=true;pendingClient=connection;pendingAddress=address;pendingDescriptor=wire.clone();}
        try {
            SharedPreferences prefs=context.getSharedPreferences(PREFS,MODE_PRIVATE);
            RecordingSyncStart.begin(new RecordingSyncStart.Store(){
                public boolean saveSelection(){return prefs.edit().putString(ADDRESS,address)
                    .putString(DESCRIPTOR,Base64.encodeToString(wire,Base64.NO_WRAP))
                    .putString(DIRECTORY,directory.getName()).putString("state","starting")
                    .putBoolean("consumePullOverlapNegotiated",false).remove("nativeTransferMetrics")
                    .putString("detail","正在准备接收").commit();}
                public void saveLaunchFailure(){prefs.edit().putString("state","error")
                    .putString("detail","无法启动后台接收，请检查蓝牙权限并在应用中重试").commit();}
            },()->context.startForegroundService(intent));
        } catch(IOException|RuntimeException e){closePending();synchronized(RecordingSyncService.class){startingOrRunning=false;}throw e;}
    }
    /** Ask the same selected session to continue after process death or a user stop. */
    public static void resume(Context context) throws IOException {
        SharedPreferences p=context.getSharedPreferences(PREFS,MODE_PRIVATE);
        String address=p.getString(ADDRESS,null),encoded=p.getString(DESCRIPTOR,null),name=p.getString(DIRECTORY,null);
        if(address==null||encoded==null||name==null)throw new IOException("没有可继续的录音接收任务");
        try {
            BluetoothManager manager=(BluetoothManager)context.getSystemService(Context.BLUETOOTH_SERVICE);
            BluetoothAdapter adapter=manager==null?null:manager.getAdapter();if(adapter==null)throw new IOException("蓝牙不可用");
            RecorderWire.Descriptor selected=RecorderWire.Descriptor.decode(Base64.decode(encoded,Base64.NO_WRAP));
            start(context,adapter.getRemoteDevice(address),selected,new File(context.getFilesDir(),name));
        } catch(IllegalArgumentException|SecurityException e){throw new IOException("无法继续原来的录音接收",e);}
    }
    /** Continue the exact outstanding confirmation, even if its segment is no longer on the card. */
    public static void resumePending(Context context,BluetoothDevice device,File recordingDirectory) throws IOException {
        if(context==null||device==null||recordingDirectory==null)throw new IllegalArgumentException("device and directory required");
        RecorderWire.Descriptor pending=RecordingLibrary.pendingConfirmation(recordingDirectory.toPath());
        if(pending==null)throw new IOException("没有待确认的录音接收任务");
        start(context,device,pending,recordingDirectory);
    }
    /** Stops only reception, not the recording on the card. */
    public static void stop(Context context) {context.stopService(new Intent(context,RecordingSyncService.class));}
    /** Control the existing recording on the same connection while reception continues; call on a worker. */
    public static String control(Path controlDirectory,String hostSession,NativeRecordingControl.Action action,int maxSeconds) throws IOException {
        RecordingClient client=activeClient;if(client==null)throw new IOException("录音卡尚未连接，请稍后重试");
        return client.controlDuringSync(controlDirectory,hostSession,action,maxSeconds);
    }
    public static String controlSessions(Path controlDirectory) throws IOException {
        RecordingClient client=activeClient;if(client==null)throw new IOException("录音卡尚未连接，请稍后重试");
        return client.controlSessionsDuringSync(controlDirectory);
    }
    public static synchronized boolean isRunning(){return startingOrRunning;}
    public static String state(Context context){return context.getSharedPreferences(PREFS,MODE_PRIVATE).getString("state","idle");}
    public static String detail(Context context){return context.getSharedPreferences(PREFS,MODE_PRIVATE).getString("detail","");}

    /** Prefer this combined view after reopening the host app. It does not start a task. */
    public static RecordingSyncStatus status(Context context) {
        SharedPreferences p=context.getSharedPreferences(PREFS,MODE_PRIVATE);
        boolean saved=p.getString(ADDRESS,null)!=null&&p.getString(DESCRIPTOR,null)!=null&&p.getString(DIRECTORY,null)!=null;
        return RecordingSyncStatus.fromSaved(p.getString("state","idle"),p.getString("detail",""),isRunning(),saved);
    }

    @Override public void onCreate(){super.onCreate();synchronized(RecordingSyncService.class){startingOrRunning=true;}NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        n.createNotificationChannel(new NotificationChannel(CHANNEL,"录音同步",NotificationManager.IMPORTANCE_LOW));}
    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        if(intent!=null&&STOP.equals(intent.getAction())){if(runner!=null){runningStartId=startId;runner.stop();}else stopSelf(startId);return START_NOT_STICKY;}
        if(intent==null||!START.equals(intent.getAction())){stopSelf(startId);return START_NOT_STICKY;}
        String requestedAddress=intent.getStringExtra(ADDRESS),requestedDirectory=intent.getStringExtra(DIRECTORY);
        byte[] requestedWire=intent.getByteArrayExtra(DESCRIPTOR);
        SharedPreferences saved=getSharedPreferences(PREFS,MODE_PRIVATE);
        if(!RecordingSyncStart.matchesSaved(requestedAddress,requestedWire==null?null:Base64.encodeToString(requestedWire,Base64.NO_WRAP),requestedDirectory,
                saved.getString(ADDRESS,null),saved.getString(DESCRIPTOR,null),saved.getString(DIRECTORY,null))){
            if(runner==null)stopSelf(startId);else runningStartId=startId;
            return START_NOT_STICKY;
        }
        if(runner!=null){runningStartId=startId;return START_REDELIVER_INTENT;}
        // Android requires promotion promptly; all Bluetooth and storage work stays off the main thread.
        try {
            if(Build.VERSION.SDK_INT>=29)startForeground(NOTIFICATION,notification("正在准备接收"),ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
            else startForeground(NOTIFICATION,notification("正在准备接收"));
        } catch(SecurityException | IllegalStateException e) {
            getSharedPreferences(PREFS,MODE_PRIVATE).edit().putString("state","error").putString("detail","无法启动后台接收，请检查蓝牙权限并在应用中重试").commit();
            stopSelf(startId);return START_NOT_STICKY;
        }
        String address=intent.getStringExtra(ADDRESS),name=intent.getStringExtra(DIRECTORY);byte[] wire=intent.getByteArrayExtra(DESCRIPTOR);
        try {
            if(address==null||name==null||wire==null||!name.equals(new File(name).getName()))throw new IOException("录音接收任务信息无效");
            final RecorderWire.Descriptor selected=RecorderWire.Descriptor.decode(wire);
            File directory=new File(getFilesDir(),name).getCanonicalFile();
            if(!getFilesDir().getCanonicalFile().equals(directory.getParentFile())||!directory.isDirectory())throw new IOException("录音保存目录不可用");
            BluetoothManager manager=(BluetoothManager)getSystemService(BLUETOOTH_SERVICE);
            BluetoothAdapter adapter=manager==null?null:manager.getAdapter();if(adapter==null)throw new IOException("蓝牙不可用");
            final BluetoothDevice device=adapter.getRemoteDevice(address);final Path path=directory.toPath();
            if(!getSharedPreferences(PREFS,MODE_PRIVATE).edit().putString(ADDRESS,address).putString(DESCRIPTOR,Base64.encodeToString(wire,Base64.NO_WRAP)).putString(DIRECTORY,name).commit())throw new IOException("无法保存接收任务");
            runningStartId=startId;
            transferMetrics=new RecordingTransferMetrics();
            final RecordingTransferMetrics measured=transferMetrics;
            runner=new RecordingSyncRunner(()->{
                try {
                    if(!adapter.isEnabled())throw new RecordingSyncRunner.BluetoothOff();
                    if(device.getBondState()!=BluetoothDevice.BOND_BONDED)
                        throw new RecordingSyncRunner.ActionRequired("录音卡已取消配对，请重新配对后继续接收");
                } catch(SecurityException denied) {
                    throw new RecordingSyncRunner.ActionRequired("请允许蓝牙连接后继续接收",denied);
                }
                measured.connecting();
                RecordingClient transferred=takePending(address,wire);
                final RecordingClient client;
                if(transferred!=null){
                    try{transferred.validateHandoff(address,selected);transferred.attachTransferMetrics(measured);}
                    catch(IOException|RuntimeException error){try{transferred.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
                    client=transferred;measured.reusedConnection();
                }else client=new RecordingClient(AndroidGattLink.connect(getApplicationContext(),device),measured);
                activeClient=client;
                measured.connected();
                getSharedPreferences(PREFS,MODE_PRIVATE).edit().putBoolean("consumePullOverlapNegotiated",client.consumePullOverlapNegotiated()).commit();
                return new RecordingSyncRunner.Connection(){
                    private boolean retired;
                    public RecordingLibrary.Session sync() throws IOException {return client.syncAvailableAndReclaim(selected,path,null);}
                    public boolean disconnected(){return client.disconnected();}
                    public synchronized void close() throws IOException {if(retired)return;retired=true;if(activeClient==client)activeClient=null;measured.connectionClosed(client.disconnected());client.close();}
                };
            },new RecordingSyncRunner.Listener(){
                public void status(String state,String detail){update(state,detail);}
                public void finished(RecordingLibrary.Session session){
                    boolean complete=session.state==RecordingLibrary.SessionState.COMPLETE;
                    update(complete?"complete":"incomplete",complete?"录音已保存到手机":"已保存可恢复的录音，请检查录音是否完整");
                }
            });
            new Thread(()->{try{runner.run();}finally{stopSelf(runningStartId);synchronized(RecordingSyncService.class){workerDone=true;if(destroyed)startingOrRunning=false;}}},"companion-recording-sync").start();
            return START_REDELIVER_INTENT;
        } catch(IOException|IllegalArgumentException|SecurityException e){update("error",e.getMessage()==null?"无法开始接收录音":e.getMessage());stopSelf(startId);return START_NOT_STICKY;}
    }
    private void update(String state,String text){
        SharedPreferences.Editor edit=getSharedPreferences(PREFS,MODE_PRIVATE).edit().putString("state",state).putString("detail",text);
        RecordingTransferMetrics observed=transferMetrics;
        if(observed!=null){if(state.equals("reconnecting"))observed.reconnecting();edit.putString("nativeTransferMetrics",observed.json());}
        edit.commit();
        if(!destroyed){NotificationManager manager=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);manager.notify(NOTIFICATION,notification(text));}}
    private Notification notification(String text){
        Intent stop=new Intent(this,RecordingSyncService.class).setAction(STOP);
        PendingIntent action=PendingIntent.getService(this,1,stop,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b=new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("Companion 录音同步").setContentText(text).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause,"停止接收",action).build());
        Intent launch=getPackageManager().getLaunchIntentForPackage(getPackageName());
        if(launch!=null)b.setContentIntent(PendingIntent.getActivity(this,0,launch,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));
        return b.build();
    }
    @Override public void onDestroy(){destroyed=true;if(runner!=null)runner.stop();closePending();synchronized(RecordingSyncService.class){if(runner==null||workerDone)startingOrRunning=false;}super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
