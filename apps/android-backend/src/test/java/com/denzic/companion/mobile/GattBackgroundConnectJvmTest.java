package com.denzic.companion.mobile;
import android.bluetooth.BluetoothGattCallback;
import java.lang.reflect.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicBoolean;

/** Actual production callbacks; host harness replaces only Android SDK's
 * throwing callback base constructor. No adapter or physical BLE model. */
public final class GattBackgroundConnectJvmTest {
    static Field field(String name)throws Exception{Field f=AndroidGattLink.class.getDeclaredField(name);f.setAccessible(true);return f;}
    static AndroidGattLink link(boolean background)throws Exception{Constructor<AndroidGattLink> c=AndroidGattLink.class.getDeclaredConstructor();c.setAccessible(true);AndroidGattLink l=c.newInstance();field("backgroundConnect").setBoolean(l,background);return l;}
    static BluetoothGattCallback callback(AndroidGattLink l)throws Exception{return(BluetoothGattCallback)field("callbacks").get(l);}
    static void check(boolean b){if(!b)throw new AssertionError();}
    public static void main(String[] args)throws Exception {
        AndroidGattLink l=link(true);callback(l).onConnectionStateChange(null,0,0);
        check(field("failure").get(l)==null&&!l.disconnected()&&!l.isConnected());
        check(((java.util.Queue<?>)field("operations").get(l)).isEmpty());
        callback(l).onConnectionStateChange(null,0,2);
        Method wait=AndroidGattLink.class.getDeclaredMethod("waitOperation",String.class,java.util.UUID.class,long.class);wait.setAccessible(true);
        Object connected=wait.invoke(l,"connection",null,500L);Field state=connected.getClass().getDeclaredField("state");state.setAccessible(true);check(state.getInt(connected)==2&&l.isConnected());
        callback(l).onConnectionStateChange(null,0,0);check(l.disconnected()&&!l.isConnected()&&field("failure").get(l)!=null);l.close();
        l=link(true);callback(l).onConnectionStateChange(null,133,0);
        try{wait.invoke(l,"connection",null,500L);throw new AssertionError("initial133 hidden");}
        catch(InvocationTargetException e){check(e.getCause()instanceof InitialConnectionRetry.Refused&&((InitialConnectionRetry.Refused)e.getCause()).status==133);}l.close();
        l=link(false);callback(l).onConnectionStateChange(null,0,0);check(l.disconnected()&&field("failure").get(l)!=null);l.close();
        l=link(true);((AtomicBoolean)field("closed").get(l)).set(true);callback(l).onConnectionStateChange(null,0,0);
        check(((CountDownLatch)field("disconnectAcknowledged").get(l)).getCount()==0);
        System.out.println("PASS production background initial-idle wait, actual connected event, later disconnect, initial133 preserved, direct behavior and close acknowledgement unchanged");
    }
}
