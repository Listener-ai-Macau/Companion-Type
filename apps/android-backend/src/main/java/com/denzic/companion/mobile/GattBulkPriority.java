package com.denzic.companion.mobile;

import java.io.Closeable;
import java.io.IOException;

/** Start optional radio negotiation during STOP, without delaying that command.
 * A real transfer borrows the accepted preference; an unused prime expires. */
final class GattBulkPriority implements Closeable {
    interface Port {boolean request(boolean high)throws IOException;}
    interface Cancel {void cancel();}
    interface Scheduler {Cancel after(long millis,Runnable task);}
    private final Port port;
    private final Scheduler scheduler;
    private Cancel expiry;
    private Object token;
    private boolean primed,active,closed;
    GattBulkPriority(Port port,Scheduler scheduler){this.port=port;this.scheduler=scheduler;}
    private void cancelExpiry(){token=null;if(expiry!=null){expiry.cancel();expiry=null;}}
    synchronized boolean prime()throws IOException {
        if(closed)return false;
        if(active)return true;
        if(!primed&&!port.request(true))return false;
        primed=true;cancelExpiry();final Object expected=new Object();token=expected;
        expiry=scheduler.after(5000,()->expire(expected));return true;
    }
    private synchronized void expire(Object expected){
        if(closed||token!=expected)return;
        expiry=null;token=null;primed=false;
        if(!active)try{port.request(false);}catch(IOException unavailable){/* Closing/lost link needs no radio preference. */}
    }
    synchronized boolean transfer(boolean value)throws IOException {
        if(closed)return false;
        boolean borrowed=value&&primed;cancelExpiry();primed=false;active=value;
        return borrowed||port.request(value);
    }
    @Override public synchronized void close(){closed=true;active=false;primed=false;cancelExpiry();}
}
