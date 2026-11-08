package com.denzic.companion.mobile;

import java.io.IOException;

public final class InitialConnectionRetryTest {
    public static void main(String[] args)throws Exception {
        int[] attempts={0},closed={0},delay={0},commands={0};
        String ready=InitialConnectionRetry.open(budget->{
            attempts[0]++;
            try{if(attempts[0]==1)throw new InitialConnectionRetry.Refused(133);return "ready";}
            finally{if(attempts[0]==1)closed[0]++;}
        },ms->{if(ms!=1000||closed[0]!=1)throw new AssertionError("retry before close or wrong cooldown");delay[0]++;});
        commands[0]++; // The caller runs its product command only after open succeeds.
        if(!ready.equals("ready")||attempts[0]!=2||closed[0]!=1||delay[0]!=1||commands[0]!=1)throw new AssertionError("initial133 recovery repeated product command");
        attempts[0]=0;delay[0]=0;
        try{InitialConnectionRetry.open(budget->{attempts[0]++;throw new InitialConnectionRetry.Refused(133);},ms->delay[0]++);throw new AssertionError("repeated133 succeeded");}
        catch(InitialConnectionRetry.Refused expected){}
        if(attempts[0]!=3||delay[0]!=2)throw new AssertionError("unbounded connection retry");
        long[] tick={0};attempts[0]=closed[0]=delay[0]=commands[0]=0;
        ready=InitialConnectionRetry.open(budget->{
            attempts[0]++;if(budget.remainingMillis()<=0)throw new AssertionError("expired attempt started");
            if(attempts[0]==3&&budget.remainingMillis()!=1658)throw new AssertionError("budget restarted between attempts");
            tick[0]+=171;
            if(attempts[0]<3){closed[0]++;throw new InitialConnectionRetry.Refused(133);}
            tick[0]+=500;return "ready";
        },ms->{if(closed[0]!=attempts[0]||ms!=1000)throw new AssertionError("owner not closed before rediscovery");delay[0]++;tick[0]+=ms;},()->tick[0]);
        commands[0]++;
        if(!ready.equals("ready")||attempts[0]!=3||closed[0]!=2||delay[0]!=2||commands[0]!=1||tick[0]>4000)throw new AssertionError("two real-length refusals not recovered within budget");
        attempts[0]=delay[0]=0;tick[0]=0;InitialConnectionRetry.Refused late=new InitialConnectionRetry.Refused(133);
        try{InitialConnectionRetry.open(budget->{attempts[0]++;tick[0]+=3500;throw late;},ms->delay[0]++,()->tick[0]);throw new AssertionError("late failure succeeded");}
        catch(InitialConnectionRetry.Refused expected){if(expected!=late)throw new AssertionError("original refusal lost");}
        if(attempts[0]!=1||delay[0]!=0)throw new AssertionError("rediscovery exceeded remaining budget");
        attempts[0]=0;tick[0]=0;
        try{InitialConnectionRetry.open(budget->{attempts[0]++;throw late;},ms->tick[0]=4001,()->tick[0]);throw new AssertionError("expired scan retried");}
        catch(InitialConnectionRetry.Refused expected){if(expected!=late||attempts[0]!=1)throw new AssertionError("expired budget opened another client");}
        for(int status:new int[]{5,8,19,22,257}){
            attempts[0]=0;delay[0]=0;
            try{InitialConnectionRetry.open(budget->{attempts[0]++;throw new InitialConnectionRetry.Refused(status);},ms->delay[0]++);throw new AssertionError("refusal succeeded");}
            catch(InitialConnectionRetry.Refused expected){if(expected.status!=status)throw new AssertionError("status lost");}
            if(attempts[0]!=1||delay[0]!=0)throw new AssertionError("other refusal retried");
        }
        IOException original=new IOException("protocol or file failure");attempts[0]=0;
        try{InitialConnectionRetry.open(budget->{attempts[0]++;throw original;},ms->{throw new AssertionError("noninitial failure retried");});throw new AssertionError("failed operation succeeded");}
        catch(IOException expected){if(expected!=original||attempts[0]!=1)throw new AssertionError("original error replaced");}
        try{InitialConnectionRetry.open(budget->{throw new SecurityException("permission");},ms->{throw new AssertionError("permission retried");});throw new AssertionError("permission accepted");}
        catch(SecurityException expected){}
        attempts[0]=0;
        try{InitialConnectionRetry.open(budget->{attempts[0]++;throw new InitialConnectionRetry.Refused(133);},ms->{throw new InterruptedException();});throw new AssertionError("interrupted retry accepted");}
        catch(IOException expected){if(!Thread.currentThread().isInterrupted()||attempts[0]!=1)throw new AssertionError("interruption lost");}
        Thread.interrupted();
        System.out.println("PASS initial133 closed-client recovery: two171ms refusals then ready within4s, three attempts maximum, single command, expired budget/other refusal/permission/protocol/interruption preserved");
    }
}
