package com.denzic.companion.mobile;

import java.io.Closeable;
import java.io.IOException;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Serial ownership of one selected recorder across activity/sync/OTA workers.
 * Ownership follows the GATT object across thread handoff, through unregister.
 * Different device addresses do not block each other. No command retry. */
final class GattConnectionOwner implements Closeable {
    private static final Map<String,Entry> ENTRIES=new HashMap<>();
    private static final class Entry {final Semaphore available=new Semaphore(1,true);int users;}
    private final String address;
    private final Entry entry;
    private final AtomicBoolean released=new AtomicBoolean();
    private GattConnectionOwner(String address,Entry entry){this.address=address;this.entry=entry;}
    static GattConnectionOwner acquire(String address)throws IOException{return acquire(address,1500);}
    static GattConnectionOwner acquire(String address,long timeoutMillis)throws IOException {
        if(address==null||address.isEmpty())throw new IllegalArgumentException("selected address required");
        String key=address.toUpperCase(Locale.ROOT);Entry entry;
        synchronized(ENTRIES){entry=ENTRIES.get(key);if(entry==null){entry=new Entry();ENTRIES.put(key,entry);}entry.users++;}
        boolean acquired=false;
        try {
            acquired=entry.available.tryAcquire(timeoutMillis,TimeUnit.MILLISECONDS);
            if(!acquired)throw new IOException("录音卡的上一项连接尚未释放，请稍后重试；没有发送新命令。");
            return new GattConnectionOwner(key,entry);
        }catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new IOException("Bluetooth connection interrupted",interrupted);}
        finally{if(!acquired)retire(key,entry);}
    }
    private static void retire(String address,Entry entry){
        synchronized(ENTRIES){if(--entry.users==0)ENTRIES.remove(address);}
    }
    @Override public void close(){
        if(!released.compareAndSet(false,true))return;
        entry.available.release();retire(address,entry);
    }
}
