package com.denzic.companion.app;

import java.io.Closeable;
import java.io.IOException;
import java.util.function.Predicate;

/** One visible activity owns a selected connection until handoff or release.
 * A failed operation is never replayed. All callers use the activity worker. */
final class DeviceConnectionOwner<C extends Closeable> implements Closeable {
    interface Open<C>{C open()throws Exception;}
    interface Operation<C,T>{T run(C connection)throws Exception;}
    private final Predicate<C> usable;
    private C connection;
    private String address;
    DeviceConnectionOwner(Predicate<C> usable){this.usable=usable;}
    synchronized <T>T use(String selected,Open<C> open,Operation<C,T> operation)throws Exception {
        if(selected==null||selected.isEmpty())throw new IllegalArgumentException("selected device required");
        if(connection!=null&&(!selected.equals(address)||!usable.test(connection)))close();
        if(connection==null){connection=open.open();address=selected;}
        try{return operation.run(connection);}
        catch(Exception|Error error){try{close();}catch(Exception close){error.addSuppressed(close);}throw error;}
    }
    synchronized C take(String selected)throws IOException {
        if(connection==null)return null;
        if(!selected.equals(address)||!usable.test(connection)){close();return null;}
        C owned=connection;connection=null;address=null;return owned;
    }
    @Override public synchronized void close()throws IOException {
        C owned=connection;connection=null;address=null;if(owned!=null)owned.close();
    }
}
