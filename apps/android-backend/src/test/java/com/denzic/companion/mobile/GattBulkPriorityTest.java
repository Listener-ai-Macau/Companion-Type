package com.denzic.companion.mobile;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class GattBulkPriorityTest {
    static void check(boolean value){if(!value)throw new AssertionError();}
    static final class Timer implements GattBulkPriority.Scheduler {
        final List<Runnable> callbacks=new ArrayList<>();int cancelled;
        public GattBulkPriority.Cancel after(long millis,Runnable callback){check(millis==5000);callbacks.add(callback);return ()->cancelled++;}
    }
    static final class Port implements GattBulkPriority.Port {
        final List<Boolean> calls=new ArrayList<>();boolean accepted=true,fail;
        public boolean request(boolean high)throws IOException {calls.add(high);if(fail)throw new IOException("optional preference unavailable");return accepted;}
    }
    public static void main(String[] args)throws Exception {
        Port p=new Port();Timer t=new Timer();GattBulkPriority a=new GattBulkPriority(p,t);
        check(a.prime());check(a.transfer(true));t.callbacks.get(0).run();
        check(p.calls.equals(Arrays.asList(true)));check(a.transfer(false));check(p.calls.equals(Arrays.asList(true,false)));
        p=new Port();t=new Timer();a=new GattBulkPriority(p,t);check(a.prime());t.callbacks.get(0).run();check(p.calls.equals(Arrays.asList(true,false)));
        p=new Port();t=new Timer();a=new GattBulkPriority(p,t);check(a.prime());check(a.prime());t.callbacks.get(0).run();check(p.calls.equals(Arrays.asList(true)));t.callbacks.get(1).run();check(p.calls.equals(Arrays.asList(true,false)));
        p=new Port();p.accepted=false;t=new Timer();a=new GattBulkPriority(p,t);check(!a.prime()&&t.callbacks.isEmpty());p.accepted=true;check(a.transfer(true));check(p.calls.equals(Arrays.asList(true,true)));a.transfer(false);
        p=new Port();t=new Timer();a=new GattBulkPriority(p,t);a.prime();a.close();t.callbacks.get(0).run();check(!a.transfer(true));check(!a.prime());check(p.calls.equals(Arrays.asList(true))&&t.cancelled==1);
        p=new Port();p.fail=true;t=new Timer();a=new GattBulkPriority(p,t);try{a.prime();throw new AssertionError();}catch(IOException expected){}check(t.callbacks.isEmpty());p.fail=false;a.transfer(true);a.transfer(false);check(p.calls.equals(Arrays.asList(true,true,false)));
        p=new Port();t=new Timer();a=new GattBulkPriority(p,t);a.transfer(true);check(a.prime()&&t.callbacks.isEmpty());check(p.calls.equals(Arrays.asList(true)));a.transfer(false);
        System.out.println("PASS_STOP_PRIME_BORROW_NO_DUPLICATE_HIGH_EXPIRY_LATE_TIMER_CLOSE_REFUSAL_AND_ACTIVE_TRANSFER");
    }
}
