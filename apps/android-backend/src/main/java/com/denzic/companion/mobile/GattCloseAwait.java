package com.denzic.companion.mobile;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Worker-only, bounded disconnect acknowledgement before unregistering GATT.
 * A stopped worker retains its interrupt flag after releasing its own client.
 * An absent callback never prevents close; no connection/data command retries. */
final class GattCloseAwait {
    static final long MAX_MILLIS=750;
    interface Port { boolean disconnect(); void close(); }
    private GattCloseAwait(){}
    static void close(Port port,CountDownLatch disconnected){
        boolean interrupted=Thread.interrupted();
        long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(MAX_MILLIS);
        try{
            if(port.disconnect())while(disconnected.getCount()!=0){
                long remaining=deadline-System.nanoTime();if(remaining<=0)break;
                try{if(disconnected.await(remaining,TimeUnit.NANOSECONDS))break;}
                catch(InterruptedException stop){interrupted=true;}
            }
        }finally{
            try{port.close();}finally{if(interrupted)Thread.currentThread().interrupt();}
        }
    }
}
