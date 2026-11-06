package com.denzic.companion.app;

import android.app.*;
import android.bluetooth.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;
import com.denzic.companion.mobile.*;
import org.json.*;
import java.io.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Explicit user-started normal full-file update. Process restart never replays
 * BEGIN/DATA/FINISH. A stored intent is not evidence that Boot installed it. */
public final class DeviceUpdateService extends Service {
    private static final String PREFS="companion_device_update",CHANNEL="companion_device_update";
    private static final int NOTIFICATION=0x435550;
    private static boolean running;
    private static final AtomicBoolean cancel=new AtomicBoolean();
    private static volatile String livePhase="idle";
    private Thread task;
    private static SharedPreferences prefs(Context c){return c.getSharedPreferences(PREFS,MODE_PRIVATE);}
    public static synchronized boolean isRunning(){return running;}
    static File directory(Context c)throws IOException{File d=new File(c.getFilesDir(),"device-updates");if(!d.isDirectory()&&!d.mkdirs())throw new IOException("无法保存升级包。");return d;}
    private static File archive(Context c,String id)throws IOException{if(id==null||!id.matches("[0-9a-f]{64}"))throw new IOException("请重新选择完整升级包。");return new File(directory(c),id+".zip");}
    static SystemUpdatePackage load(Context c,String id)throws IOException{try(InputStream in=new FileInputStream(archive(c,id))){SystemUpdatePackage p=SystemUpdatePackage.open(in);if(!id.equals(p.id))throw new IOException("已选升级包发生变化，请重新选择。");return p;}}
    static synchronized JSONObject prepare(Context c,InputStream source)throws Exception{
        if(running||RecordingSyncService.isRunning())throw new IOException("正在接收录音或升级，请等待完成。");
        File stage=File.createTempFile("incoming-",".zip",directory(c));
        try{
            try(FileOutputStream out=new FileOutputStream(stage)){byte[] b=new byte[32768];int n,total=0;while((n=source.read(b))!=-1){total+=n;if(total>SystemUpdatePackage.ARCHIVE_LIMIT)throw new IOException("升级包超过支持的大小。");out.write(b,0,n);}out.getFD().sync();}
            SystemUpdatePackage p;try(InputStream in=new FileInputStream(stage)){p=SystemUpdatePackage.open(in);}
            File target=archive(c,p.id);
            if(target.exists()){load(c,p.id);}else if(!stage.renameTo(target))throw new IOException("升级包保存失败，请重新选择。");
            if(!prefs(c).edit().putString("preparedId",p.id).putString("preparedInfo",p.info().toString()).commit())throw new IOException("升级包选择未保存，请重试。");return p.info();
        }finally{stage.delete();}
    }
    public static synchronized JSONObject status(Context c)throws Exception{
        SharedPreferences p=prefs(c);String phase=p.getString("phase","idle");
        if(!running&&("checking".equals(phase)||"transferring".equals(phase)||"installing".equals(phase)||"verifying".equals(phase)))phase="interrupted";
        JSONObject out=new JSONObject().put("running",running).put("phase",phase).put("address",p.getString("address","")).put("name",p.getString("name","录音卡"))
            .put("accepted",p.getLong("accepted",0)).put("total",p.getLong("total",0)).put("message",phase.equals("interrupted")?"上次操作已中断，尚未确认结果。请连接原录音卡核对实际版本。":p.getString("message",""))
            .put("canCancel",running&&(livePhase.equals("checking")||livePhase.equals("transferring"))).put("canVerify",!running&&!p.getString("uid","").isEmpty()&&!phase.equals("complete"));
        String id=p.getString("preparedId","");if(!id.isEmpty())try{if(!archive(c,id).isFile())throw new IOException();out.put("prepared",new JSONObject(p.getString("preparedInfo","{}")));}catch(Exception unavailable){out.put("packageError","已选升级包暂不可读，请重新选择。");}
        return out;
    }
    static synchronized JSONObject start(Context c,BluetoothDevice device,String name,String id,boolean verify)throws Exception{
        if(running||RecordingSyncService.isRunning())throw new IOException("正在接收录音或升级，请等待完成。");
        SharedPreferences p=prefs(c);if(device==null)throw new IOException("请先连接原录音卡。");
        String address=device.getAddress();
        if(verify){if(!address.equals(p.getString("address","")))throw new IOException("请选择上次升级的原录音卡。");id=p.getString("transactionId","");if(p.getString("uid","").isEmpty())throw new IOException("尚无原设备身份，无法确认上次结果；请重新选择升级包。");}
        else if(!id.equals(p.getString("preparedId","")))throw new IOException("所选升级包已变化，请重新读取。");
        SystemUpdatePackage pack=load(c,id);
        if(device.getBondState()!=BluetoothDevice.BOND_BONDED)throw new IOException("请先完成系统蓝牙配对。");
        SharedPreferences.Editor save=p.edit().putString("phase",verify?"verifying":"checking").putString("address",address).putString("name",name).putString("transactionId",id).putString("message","正在连接并核对设备");
        if(!verify)save.putString("uid","").putLong("accepted",0).putLong("total",pack.info().getLong("bytes"));
        if(!save.commit())throw new IOException("升级任务未保存，未连接设备。");
        running=true;cancel.set(false);livePhase=verify?"verifying":"checking";
        try{c.startForegroundService(new Intent(c,DeviceUpdateService.class).putExtra("verify",verify));}
        catch(RuntimeException e){running=false;p.edit().putString("phase","error").putString("message","后台任务未启动，请回到应用重试。").commit();throw e;}
        return status(c);
    }
    public static synchronized JSONObject cancel(Context c)throws Exception{
        if(running&&(livePhase.equals("installing")||livePhase.equals("verifying")))throw new IOException("设备正在安装或核对结果，请保持供电并等待。");
        cancel.set(true);return status(c);
    }
    private static String message(String phase){switch(phase){case "checking":return "正在核对设备和升级条件";case "transferring":return "正在传入完整升级包";case "installing":return "设备正在验证并安装，请保持供电";case "verifying":return "正在重新连接并核对实际运行版本";case "complete":return "升级完成，已核对实际程序、资源和完整校验";default:return "升级结果待确认";}}
    private void record(String phase,long accepted,long total)throws IOException{
        synchronized(DeviceUpdateService.class){
            if(phase.equals("installing")&&cancel.get())throw new IOException("已停止传入，未要求设备安装；下一次从头传入。");
            if(!prefs(this).edit().putString("phase",phase).putLong("accepted",accepted).putLong("total",total).putString("message",message(phase)).commit())throw new IOException("升级进度无法保存，已停止继续发送。");livePhase=phase;
        }
        NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);n.notify(NOTIFICATION,notification(message(phase),accepted,total));
    }
    private Notification notification(String text,long accepted,long total){
        Intent open=getPackageManager().getLaunchIntentForPackage(getPackageName());PendingIntent launch=open==null?null:PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b=new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.stat_sys_upload).setContentTitle("Companion · 录音卡升级").setContentText(text).setOngoing(true).setOnlyAlertOnce(true).setContentIntent(launch);
        if(livePhase.equals("transferring")&&total>0)b.setProgress(100,(int)Math.min(100,accepted*100/total),false);return b.build();
    }
    @Override public void onCreate(){super.onCreate();NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);n.createNotificationChannel(new NotificationChannel(CHANNEL,"录音卡升级",NotificationManager.IMPORTANCE_LOW));}
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(task!=null)return START_NOT_STICKY;
        if(intent==null){synchronized(DeviceUpdateService.class){running=false;}stopSelf();return START_NOT_STICKY;}
        Notification n=notification("正在准备升级",0,0);if(Build.VERSION.SDK_INT>=29)startForeground(NOTIFICATION,n,ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);else startForeground(NOTIFICATION,n);
        final boolean verify=intent.getBooleanExtra("verify",false);
        task=new Thread(()->{
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
            try{
                SharedPreferences p=prefs(this);SystemUpdatePackage pack=load(this,p.getString("transactionId",""));
                BluetoothManager m=(BluetoothManager)getSystemService(BLUETOOTH_SERVICE);BluetoothAdapter adapter=m==null?null:m.getAdapter();if(adapter==null)throw new IOException("手机蓝牙暂不可用。");
                BluetoothDevice device=adapter.getRemoteDevice(p.getString("address",""));SystemUpdateClient.Connector connector=()->AndroidGattLink.connectForUpdate(this,device);
                if(verify){if(!SystemUpdateClient.verify(connector,pack,p.getString("uid","")))throw new IOException("尚未看到匹配的新运行版本，请保持供电，稍后再核对；不要重复发送完成请求。");record("complete",pack.info().getLong("bytes"),pack.info().getLong("bytes"));}
                else SystemUpdateClient.transfer(connector,pack,cancel,new SystemUpdateClient.Progress(){
                    public void update(String phase,long accepted,long total)throws IOException{record(phase,accepted,total);}
                    public void identity(String uid)throws IOException{if(!p.edit().putString("uid",uid).commit())throw new IOException("设备身份无法保存，未开始传入。");}
                });
            }catch(Exception error){String detail=error.getMessage()==null?"升级结果待确认，请重新连接原设备核对。":error.getMessage();String phase=livePhase.equals("installing")||livePhase.equals("verifying")?"unconfirmed":cancel.get()?"cancelled":"error";prefs(this).edit().putString("phase",phase).putString("message",detail).commit();}
            finally{new Handler(getMainLooper()).post(()->{synchronized(DeviceUpdateService.class){task=null;stopForeground(STOP_FOREGROUND_REMOVE);stopSelf(startId);running=false;}});}
        },"Companion-device-update");task.start();return START_NOT_STICKY;
    }
    @Override public void onDestroy(){if(task!=null&&task.isAlive()){cancel.set(true);task.interrupt();}super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
