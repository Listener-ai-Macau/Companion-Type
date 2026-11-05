package com.denzic.companion.mobile;

import java.io.IOException;

/** Tests selection identity and the launch failure/interruption boundary. */
public final class RecordingSyncStartJvmTest {
    private static final class Store implements RecordingSyncStart.Store {
        String selected="old-task", state="complete";
        boolean canSave=true;
        public boolean saveSelection(){if(!canSave)return false;selected="new-task";state="starting";return true;}
        public void saveLaunchFailure(){state="error";}
    }
    public static void main(String[] args) throws Exception {
        Store failed=new Store();
        try {
            RecordingSyncStart.begin(failed,()->{if(!"new-task".equals(failed.selected))throw new AssertionError("wrong task at launch");throw new IllegalStateException("Android rejected launch");});
            throw new AssertionError("launch failure swallowed");
        } catch(IllegalStateException expected) {}
        if(!"new-task".equals(failed.selected)||!"error".equals(failed.state))throw new AssertionError("resume would select the wrong task");
        Store interrupted=new Store();
        RecordingSyncStart.begin(interrupted,()->{});
        RecordingSyncStatus afterDeath=RecordingSyncStatus.fromSaved(interrupted.state,"",false,true);
        if(!"new-task".equals(interrupted.selected)||!"interrupted".equals(afterDeath.state))throw new AssertionError("launch interrupted before service started");
        Store noDisk=new Store();noDisk.canSave=false;final boolean[] launched={false};
        try {RecordingSyncStart.begin(noDisk,()->launched[0]=true);throw new AssertionError("uncommitted task launched");}catch(IOException expected){}
        if(launched[0]||!"old-task".equals(noDisk.selected))throw new AssertionError("save failure started reception");
        if(RecordingSyncStart.matchesSaved("old-device","old-session","old-dir","new-device","new-session","new-dir"))throw new AssertionError("old redelivery replaced new task");
        if(!RecordingSyncStart.matchesSaved("new-device","new-session","new-dir","new-device","new-session","new-dir"))throw new AssertionError("same task was rejected");
        if(!RecordingSyncStart.matchesSaved("legacy-device","legacy-session","legacy-dir",null,null,null))throw new AssertionError("legacy first redelivery was rejected");
        System.out.println("RecordingSyncStartJvmTest passed");
    }
}
