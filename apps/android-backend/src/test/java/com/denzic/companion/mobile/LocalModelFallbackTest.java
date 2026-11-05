package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;

/** Real verified fallback assets and a process-local unavailable proxy. */
public final class LocalModelFallbackTest {
    public static void main(String[] args)throws Exception {
        Path available=Paths.get(args[0]);Path missing=Paths.get(args[1]);
        if(!LocalModelPreparation.isPrepared(available))throw new AssertionError("verified fallback must report ready");
        LocalModelPreparation.prepare(available,null);
        if(!LocalModelPreparation.isPrepared(available))throw new AssertionError("failed download lost fallback readiness");
        if(LocalModelPreparation.isPrepared(missing))throw new AssertionError("missing model reported ready");
        try{LocalModelPreparation.prepare(missing,null);throw new AssertionError("missing models unexpectedly prepared");}
        catch(IOException expected){}
        Thread.currentThread().interrupt();
        try{
            try{LocalModelPreparation.prepare(available,null);throw new AssertionError("interrupted preparation reported success");}
            catch(IOException expected){}
        } finally {Thread.interrupted();}
        System.out.println("PASS verified fallback readiness, offline preparation, missing models and cancellation");
    }
}
