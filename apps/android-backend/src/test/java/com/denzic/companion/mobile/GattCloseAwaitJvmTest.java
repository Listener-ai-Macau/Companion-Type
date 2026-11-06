package com.denzic.companion.mobile;
import java.util.concurrent.CountDownLatch;
public final class GattCloseAwaitJvmTest {
    static void check(boolean value){if(!value)throw new AssertionError();}
    public static void main(String[] args)throws Exception{
        CountDownLatch signal=new CountDownLatch(1);int[] calls={0,0};
        GattCloseAwait.close(new GattCloseAwait.Port(){
            public boolean disconnect(){calls[0]++;new Thread(()->{try{Thread.sleep(15);}catch(InterruptedException ignored){}signal.countDown();}).start();return true;}
            public void close(){check(signal.getCount()==0);calls[1]++;}
        },signal);check(calls[0]==1&&calls[1]==1);
        Thread.currentThread().interrupt();CountDownLatch stopped=new CountDownLatch(0);
        GattCloseAwait.close(new GattCloseAwait.Port(){public boolean disconnect(){return true;}public void close(){calls[1]++;}},stopped);
        check(Thread.interrupted()&&calls[1]==2);
        long start=System.nanoTime();
        GattCloseAwait.close(new GattCloseAwait.Port(){public boolean disconnect(){return true;}public void close(){calls[1]++;}},new CountDownLatch(1));
        long millis=(System.nanoTime()-start)/1000000;check(millis>=700&&millis<2000&&calls[1]==3);
        start=System.nanoTime();GattCloseAwait.close(new GattCloseAwait.Port(){public boolean disconnect(){return false;}public void close(){calls[1]++;}},new CountDownLatch(1));
        check((System.nanoTime()-start)/1000000<100&&calls[1]==4);
        try{GattCloseAwait.close(new GattCloseAwait.Port(){public boolean disconnect(){throw new IllegalStateException("fixture");}public void close(){calls[1]++;}},new CountDownLatch(1));throw new AssertionError();}
        catch(IllegalStateException expected){check(calls[1]==5);}
        System.out.println("PASS actual GATT close helper: disconnect acknowledgement precedes unregister, timeout still closes, denied/failed disconnect still releases, cancellation interrupt retained; no data/command retry. SOFTWARE ONLY");
    }
}
