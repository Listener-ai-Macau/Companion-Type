package com.denzic.companion.mobile;

import java.io.IOException;

/** Recover one Android 133 refusal before a link or product command exists. */
final class InitialConnectionRetry {
    static final class Refused extends RecordingSyncRunner.LinkFailure {
        final int status;
        Refused(int status){super("Bluetooth connection failed ("+status+")");this.status=status;}
    }
    interface Attempt<T> {T open(boolean background) throws IOException;}
    interface Delay {void waitMillis(long millis) throws InterruptedException;}
    static <T> T open(Attempt<T> attempt,Delay delay) throws IOException {
        try{return attempt.open(false);}
        catch(Refused first){
            if(first.status!=133)throw first;
            try{delay.waitMillis(1000);}
            catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new IOException("Bluetooth connection interrupted",interrupted);}
            return attempt.open(true);
        }
    }
    private InitialConnectionRetry(){}
}
