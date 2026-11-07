package com.denzic.companion.mobile;

import java.io.IOException;

public final class InitialConnectionRetryTest {
    public static void main(String[] args)throws Exception {
        int[] attempts={0},closed={0},delay={0},commands={0};
        java.util.ArrayList<Boolean> modes=new java.util.ArrayList<>();
        String ready=InitialConnectionRetry.open(background->{
            modes.add(background);
            attempts[0]++;
            try{if(attempts[0]==1)throw new InitialConnectionRetry.Refused(133);return "ready";}
            finally{if(attempts[0]==1)closed[0]++;}
        },ms->{if(ms!=1000||closed[0]!=1)throw new AssertionError("retry before close or wrong cooldown");delay[0]++;});
        commands[0]++; // The caller runs its product command only after open succeeds.
        if(!ready.equals("ready")||attempts[0]!=2||closed[0]!=1||delay[0]!=1||commands[0]!=1)throw new AssertionError("initial133 recovery repeated product command");
        if(!modes.equals(java.util.Arrays.asList(false,true)))throw new AssertionError("retry must change direct to background scheduling exactly once");
        attempts[0]=0;delay[0]=0;
        try{InitialConnectionRetry.open(background->{attempts[0]++;throw new InitialConnectionRetry.Refused(133);},ms->delay[0]++);throw new AssertionError("repeated133 succeeded");}
        catch(InitialConnectionRetry.Refused expected){}
        if(attempts[0]!=2||delay[0]!=1)throw new AssertionError("unbounded connection retry");
        for(int status:new int[]{5,8,19,22,257}){
            attempts[0]=0;delay[0]=0;
            try{InitialConnectionRetry.open(background->{attempts[0]++;throw new InitialConnectionRetry.Refused(status);},ms->delay[0]++);throw new AssertionError("refusal succeeded");}
            catch(InitialConnectionRetry.Refused expected){if(expected.status!=status)throw new AssertionError("status lost");}
            if(attempts[0]!=1||delay[0]!=0)throw new AssertionError("other refusal retried");
        }
        IOException original=new IOException("protocol or file failure");attempts[0]=0;
        try{InitialConnectionRetry.open(background->{attempts[0]++;throw original;},ms->{throw new AssertionError("noninitial failure retried");});throw new AssertionError("failed operation succeeded");}
        catch(IOException expected){if(expected!=original||attempts[0]!=1)throw new AssertionError("original error replaced");}
        try{InitialConnectionRetry.open(background->{throw new SecurityException("permission");},ms->{throw new AssertionError("permission retried");});throw new AssertionError("permission accepted");}
        catch(SecurityException expected){}
        attempts[0]=0;
        try{InitialConnectionRetry.open(background->{attempts[0]++;throw new InitialConnectionRetry.Refused(133);},ms->{throw new InterruptedException();});throw new AssertionError("interrupted retry accepted");}
        catch(IOException expected){if(!Thread.currentThread().isInterrupted()||attempts[0]!=1)throw new AssertionError("interruption lost");}
        Thread.interrupted();
        System.out.println("PASS initial133 closed-client recovery, one retry, single subsequent command, other refusal/permission/protocol errors and interruption preserved");
    }
}
