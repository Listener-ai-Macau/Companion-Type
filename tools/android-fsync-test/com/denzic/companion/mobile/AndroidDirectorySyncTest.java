package com.denzic.companion.mobile;
import android.system.Os;
import android.system.OsConstants;
import java.io.IOException;
import java.nio.file.Paths;
import java.util.Arrays;
public final class AndroidDirectorySyncTest {
    private static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    private static void reset(String failure,int mode){Os.calls.clear();Os.fail=failure;Os.mode=mode;}
    private static void fails()throws Exception {
        try{AndroidDirectorySync.sync(Paths.get("private-recordings"));throw new AssertionError("expected failure");}
        catch(IOException expected){}
    }
    public static void main(String[] args)throws Exception {
        reset("",040000);AndroidDirectorySync.sync(Paths.get("private-recordings"));
        check(Os.calls.equals(Arrays.asList("open","fstat","fsync","close")),"directory was not explicitly synced and closed");
        check((Os.flags&OsConstants.O_NOFOLLOW)!=0&&(Os.flags&OsConstants.O_CLOEXEC)!=0,"safe directory open flags missing");
        reset("open",040000);fails();check(Os.calls.equals(Arrays.asList("open")),"open failure must stop");
        reset("fstat",040000);fails();check(Os.calls.equals(Arrays.asList("open","fstat","close")),"fstat failure must close");
        reset("fsync",040000);fails();check(Os.calls.equals(Arrays.asList("open","fstat","fsync","close")),"fsync failure must close and report failure");
        reset("close",040000);fails();check(Os.calls.contains("fsync"),"close failure must propagate after syncing");
        reset("",0100000);fails();check(Os.calls.equals(Arrays.asList("open","fstat","close")),"non-directory must not be synced");
        System.out.println("PASS Android directory fsync invocation and failure propagation (mock OS)");
    }
}
