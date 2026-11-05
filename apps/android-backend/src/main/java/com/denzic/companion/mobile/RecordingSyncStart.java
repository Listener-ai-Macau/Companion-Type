package com.denzic.companion.mobile;

import java.io.IOException;

/** Persist the exact selection before asking Android to launch the service. */
final class RecordingSyncStart {
    interface Store {
        boolean saveSelection();
        void saveLaunchFailure();
    }
    interface Launcher { void start(); }

    static void begin(Store store, Launcher launcher) throws IOException {
        if (!store.saveSelection()) throw new IOException("无法保存接收任务，请检查手机存储后重试");
        try {
            launcher.start();
        } catch (RuntimeException failure) {
            store.saveLaunchFailure();
            throw failure;
        }
    }
    /** An old Android redelivery must not replace a newer selected task. */
    static boolean matchesSaved(String address,String descriptor,String directory,
                                String savedAddress,String savedDescriptor,String savedDirectory) {
        if(savedAddress==null&&savedDescriptor==null&&savedDirectory==null)return true;
        return address!=null&&descriptor!=null&&directory!=null
            &&address.equals(savedAddress)&&descriptor.equals(savedDescriptor)&&directory.equals(savedDirectory);
    }
    private RecordingSyncStart() {}
}
