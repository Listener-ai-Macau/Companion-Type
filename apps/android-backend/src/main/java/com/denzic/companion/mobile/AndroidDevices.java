package com.denzic.companion.mobile;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanRecord;
import android.bluetooth.le.ScanResult;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelUuid;
import java.io.Closeable;
import java.io.IOException;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

/** Discover Companion candidates without opening a connection or changing pairing. */
@SuppressLint("MissingPermission")
public final class AndroidDevices {
    private AndroidDevices(){}
    private static final ParcelUuid RECORDING_SERVICE=new ParcelUuid(UUID.fromString("8f7a0003-7b7d-4f3d-9d6f-6c2d1b7c0000"));
    public interface Listener {
        void onDevice(BluetoothDevice device,String advertisedName);
        /** Called once after a normal stop or failure; null means no scan error. */
        void onFinished(String error);
    }
    public static final class Scan implements Closeable {
        private final BluetoothLeScanner scanner;private final Listener listener;private final Handler handler=new Handler(Looper.getMainLooper());
        private final Set<String> seen=new HashSet<>();private boolean closed;
        private final ScanCallback callback=new ScanCallback(){
            @Override public void onScanResult(int type,ScanResult result){
                if(result==null||result.getDevice()==null)return;
                try{
                    ScanRecord record=result.getScanRecord();String name=record==null?null:record.getDeviceName();
                    boolean service=record!=null&&record.getServiceUuids()!=null&&record.getServiceUuids().contains(RECORDING_SERVICE);
                    if(!service&&(name==null||!name.toLowerCase(Locale.ROOT).contains("companion")))return;
                    synchronized(Scan.this){if(closed||!seen.add(result.getDevice().getAddress()))return;}
                    listener.onDevice(result.getDevice(),name==null?"Companion":name);
                }catch(SecurityException error){finish("Bluetooth permission is required");}
            }
            @Override public void onScanFailed(int code){finish("Bluetooth scan failed ("+code+")");}
        };
        private Scan(BluetoothLeScanner scanner,Listener listener){this.scanner=scanner;this.listener=listener;}
        private void start() throws IOException {
            try{scanner.startScan(callback);handler.postDelayed(()->finish(null),12_000);}
            catch(SecurityException error){throw new IOException("Bluetooth scan permission is required",error);}
        }
        private void finish(String error){
            synchronized(this){if(closed)return;closed=true;}
            try{scanner.stopScan(callback);}catch(SecurityException ignored){}
            listener.onFinished(error);
        }
        @Override public void close(){finish(null);}
    }
    /** The host app must request the appropriate Android Bluetooth permission first. */
    public static Scan discover(Context context,Listener listener) throws IOException {
        if(context==null||listener==null)throw new IllegalArgumentException("context and listener required");
        try{BluetoothManager manager=(BluetoothManager)context.getApplicationContext().getSystemService(Context.BLUETOOTH_SERVICE);BluetoothAdapter adapter=manager==null?null:manager.getAdapter();
            if(adapter==null||!adapter.isEnabled())throw new IOException("Bluetooth is unavailable or turned off");BluetoothLeScanner scanner=adapter.getBluetoothLeScanner();if(scanner==null)throw new IOException("Bluetooth scanning is unavailable");
            Scan scan=new Scan(scanner,listener);scan.start();return scan;
        }catch(SecurityException error){throw new IOException("Bluetooth permission is required",error);}
    }
}
