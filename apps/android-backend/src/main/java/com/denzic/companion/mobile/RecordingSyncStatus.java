package com.denzic.companion.mobile;

/** A moment-in-time view of the saved reception task and the current process. */
public final class RecordingSyncStatus {
    public final String state;
    public final String detail;
    public final boolean running;
    /** A task identity is saved; permissions and device availability are checked when resuming. */
    public final boolean hasSavedTask;

    private RecordingSyncStatus(String state, String detail, boolean running, boolean hasSavedTask) {
        this.state=state;this.detail=detail;this.running=running;this.hasSavedTask=hasSavedTask;
    }

    static RecordingSyncStatus fromSaved(String state,String detail,boolean running,boolean hasSavedTask) {
        boolean wasActive="starting".equals(state)||"connecting".equals(state)||"syncing".equals(state)||"following".equals(state)
            ||"reconnecting".equals(state)||"waiting_bluetooth".equals(state);
        if(wasActive&&!running) {
            String message=hasSavedTask
                ? "手机后台接收已中断，已保存的录音保留；可在应用中继续原任务。"
                : "手机后台接收已中断，已保存的录音保留；请重新选择录音。";
            return new RecordingSyncStatus("interrupted",message,false,hasSavedTask);
        }
        return new RecordingSyncStatus(state,detail,running,hasSavedTask);
    }
}
