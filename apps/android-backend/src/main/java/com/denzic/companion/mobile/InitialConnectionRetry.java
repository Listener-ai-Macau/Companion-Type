package com.denzic.companion.mobile;

import java.io.IOException;

/** Recover fast Android133 refusals before a link or product command exists.
 * The observed failure was two successive~171ms establishments, so one retry
 * still exposed an error. Keep at most three closed-owner attempts within one
 * monotonic4s initial-link budget; never retry a protocol/security/data failure. */
final class InitialConnectionRetry {
    static final class Refused extends RecordingSyncRunner.LinkFailure {
        final int status;
        Refused(int status){super("Bluetooth connection failed ("+status+")");this.status=status;}
    }
    interface Clock {long millis();}
    static final class Budget {
        private final Clock clock;private final long started;
        Budget(Clock clock){this.clock=clock;started=clock.millis();}
        long remainingMillis(){return 4000L-(clock.millis()-started);}
    }
    interface Attempt<T> {T open(Budget budget) throws IOException;}
    interface Delay {void waitMillis(long millis) throws InterruptedException;}
    static <T> T open(Attempt<T> attempt,Delay delay) throws IOException {
        return open(attempt,delay,()->System.nanoTime()/1_000_000L);
    }
    static <T> T open(Attempt<T> attempt,Delay delay,Clock clock) throws IOException {
        Budget budget=new Budget(clock);Refused last=null;
        for(int count=0;count<3;count++) {
            if(budget.remainingMillis()<=0) {
                if(last!=null)throw last;
                throw new java.net.SocketTimeoutException("Bluetooth initial connection budget exhausted");
            }
            try{return attempt.open(budget);}
            catch(Refused refused){
                last=refused;
                if(refused.status!=133||count==2||budget.remainingMillis()<=1000L)throw refused;
                try{delay.waitMillis(1000);}
                catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new IOException("Bluetooth connection interrupted",interrupted);}
            }
        }
        throw last;
    }
    private InitialConnectionRetry(){}
}
