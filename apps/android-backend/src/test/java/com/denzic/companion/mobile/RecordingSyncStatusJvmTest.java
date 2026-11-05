package com.denzic.companion.mobile;

public final class RecordingSyncStatusJvmTest {
    public static void main(String[] args) {
        for(String active:new String[]{"starting","connecting","syncing","following","reconnecting","waiting_bluetooth"}) {
            RecordingSyncStatus interrupted=RecordingSyncStatus.fromSaved(active,"old detail",false,true);
            if(!"interrupted".equals(interrupted.state)||interrupted.running||!interrupted.hasSavedTask
                    ||!interrupted.detail.contains("继续原任务"))throw new AssertionError(active);
            RecordingSyncStatus running=RecordingSyncStatus.fromSaved(active,"live",true,true);
            if(!active.equals(running.state)||!running.running||!"live".equals(running.detail))throw new AssertionError(active);
        }
        RecordingSyncStatus noTask=RecordingSyncStatus.fromSaved("syncing","old",false,false);
        if(!"interrupted".equals(noTask.state)||noTask.hasSavedTask||!noTask.detail.contains("重新选择"))throw new AssertionError("missing task");
        for(String finalState:new String[]{"idle","complete","incomplete","stopped","error"}) {
            RecordingSyncStatus finalStatus=RecordingSyncStatus.fromSaved(finalState,"saved",false,true);
            if(!finalState.equals(finalStatus.state)||!"saved".equals(finalStatus.detail))throw new AssertionError(finalState);
        }
        System.out.println("RecordingSyncStatusJvmTest passed");
    }
}
