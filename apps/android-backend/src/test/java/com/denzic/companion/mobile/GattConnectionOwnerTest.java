package com.denzic.companion.mobile;

import java.io.IOException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/** Real lease implementation under concurrent worker handoff and cleanup. */
public final class GattConnectionOwnerTest {
    private static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception {
        String address="C8:ED:45:EB:95:B4";
        GattConnectionOwner old=GattConnectionOwner.acquire(address);
        CountDownLatch waiting=new CountDownLatch(1),opened=new CountDownLatch(1),finish=new CountDownLatch(1);
        AtomicReference<Throwable> error=new AtomicReference<>();
        Thread next=new Thread(()->{
            waiting.countDown();
            try(GattConnectionOwner lease=GattConnectionOwner.acquire(address.toLowerCase(java.util.Locale.ROOT))){opened.countDown();finish.await();}
            catch(Throwable failed){error.set(failed);}
        });next.start();check(waiting.await(2,TimeUnit.SECONDS),"next worker not started");
        check(!opened.await(40,TimeUnit.MILLISECONDS),"new GATT opened while old owner still held");
        try(GattConnectionOwner unrelated=GattConnectionOwner.acquire("C8:ED:45:EB:95:B5",10)){}
        // The callback/service thread may release an Activity-created GATT.
        Thread cleanup=new Thread(old::close);cleanup.start();cleanup.join(2000);
        check(opened.await(2,TimeUnit.SECONDS),"cleanup did not wake next selected-device worker");
        old.close(); // cannot release the NEXT worker's ownership
        try{GattConnectionOwner.acquire(address,20);throw new AssertionError("double close released a new owner");}catch(IOException expected){}
        finish.countDown();next.join(2000);check(!next.isAlive()&&error.get()==null,"handoff failed: "+error.get());
        try(GattConnectionOwner held=GattConnectionOwner.acquire(address)){
            AtomicBoolean interrupted=new AtomicBoolean();
            Thread cancelled=new Thread(()->{
                Thread.currentThread().interrupt();
                try{GattConnectionOwner.acquire(address);error.set(new AssertionError("cancelled owner acquired"));}
                catch(IOException expected){interrupted.set(Thread.currentThread().isInterrupted());}
            });cancelled.start();cancelled.join(2000);check(interrupted.get()&&error.get()==null,"owner cancellation lost interrupt or leaked");
        }
        try(GattConnectionOwner afterTimeoutAndCancel=GattConnectionOwner.acquire(address,20)){}
        System.out.println("PASS same-address workers serialized through old close; cross-thread handoff, independent address, timeout/cancel cleanup and double-close ownership preserved");
    }
}
