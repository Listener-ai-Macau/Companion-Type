package com.denzic.companion.mobile;
import android.annotation.SuppressLint;
import android.bluetooth.BluetoothDevice;
import android.content.*;
import android.os.Build;
import java.io.IOException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** Explicit user-selected system pairing. Never accepts a PIN or removes another bond. */
@SuppressLint("MissingPermission")
public final class AndroidPairing {
    private AndroidPairing(){}
    public static void pair(Context context,BluetoothDevice selected)throws IOException{
        if(context==null||selected==null)throw new IllegalArgumentException("selected device required");
        if(selected.getBondState()==BluetoothDevice.BOND_BONDED)return;
        Context app=context.getApplicationContext();CountDownLatch done=new CountDownLatch(1);AtomicInteger state=new AtomicInteger(-1);
        BroadcastReceiver receiver=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent intent){
            if(!BluetoothDevice.ACTION_BOND_STATE_CHANGED.equals(intent.getAction()))return;
            BluetoothDevice observed=intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
            if(observed==null||!selected.getAddress().equals(observed.getAddress()))return;
            int next=intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE,BluetoothDevice.ERROR);
            if(next==BluetoothDevice.BOND_BONDED||next==BluetoothDevice.BOND_NONE){state.set(next);done.countDown();}
        }};
        boolean registered=false;
        try{
            IntentFilter filter=new IntentFilter(BluetoothDevice.ACTION_BOND_STATE_CHANGED);
            if(Build.VERSION.SDK_INT>=33)app.registerReceiver(receiver,filter,Context.RECEIVER_EXPORTED);else app.registerReceiver(receiver,filter);
            registered=true;
            int current=selected.getBondState();if(current==BluetoothDevice.BOND_BONDED)return;
            if(current!=BluetoothDevice.BOND_BONDING&&!selected.createBond())throw new IOException("手机暂时无法开始配对，请检查录音卡是否处于可连接状态。");
            if(selected.getBondState()==BluetoothDevice.BOND_BONDED)return;
            if(!done.await(60,TimeUnit.SECONDS))throw new IOException("尚未确认配对完成，请检查系统提示后重新读取设备；录音仍保留。");
            if(state.get()!=BluetoothDevice.BOND_BONDED||selected.getBondState()!=BluetoothDevice.BOND_BONDED)throw new IOException("配对未完成或已取消，请让录音卡进入可连接状态后重试。");
        }catch(SecurityException e){throw new IOException("请先允许附近设备权限，再进行配对。",e);}
        catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("配对等待已中断，请重新读取设备状态。",e);}
        finally{if(registered)try{app.unregisterReceiver(receiver);}catch(IllegalArgumentException ignored){}}
    }
}
