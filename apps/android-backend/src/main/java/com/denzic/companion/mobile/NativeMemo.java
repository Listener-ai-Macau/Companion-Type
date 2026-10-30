package com.denzic.companion.mobile;

import java.io.IOException;

/** Locally identify literal task candidates from a short voice memo. */
public final class NativeMemo {
    private NativeMemo() {}
    private static native String extractJson(String transcript,long durationMillis) throws IOException;
    /** Returns a draft JSON result; review candidates and retain the complete transcript. */
    public static String extract(String transcript,long durationMillis) throws IOException {
        if(transcript==null||durationMillis<=0)throw new IllegalArgumentException("transcript and recording duration required");
        try{System.loadLibrary("companion_mobile_audio");return extractJson(transcript,durationMillis);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile memo library is not installed for this device",error);}
    }
}
