package com.denzic.companion.mobile;

import java.io.IOException;

/** Prepare calendar data locally; importing it remains an explicit user action. */
public final class NativeCalendar {
    private NativeCalendar() {}
    private static native String exportJson(String request) throws IOException;
    /** JSON request and response are documented in the backend README. Call on a worker thread. */
    public static String export(String request) throws IOException {
        if(request==null)throw new IllegalArgumentException("calendar request required");
        try{System.loadLibrary("companion_mobile_audio");return exportJson(request);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile calendar library is not installed for this device",error);}
    }
}
