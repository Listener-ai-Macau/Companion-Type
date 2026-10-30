package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;

/** User-initiated service-backed minutes; call on a worker thread. */
public final class NativeMinutes {
    private NativeMinutes() {}
    private static native String generateJson(String request,String apiKey,String privateCacheDirectory) throws IOException;
    /** Sends the selected transcript to the configured service; see README for consent and result handling. */
    public static String generate(String request,String apiKey,Path privateCacheDirectory) throws IOException {
        if(request==null||apiKey==null||privateCacheDirectory==null)throw new IllegalArgumentException("request, service key and private cache required");
        try {System.loadLibrary("companion_mobile_audio");return generateJson(request,apiKey,privateCacheDirectory.toAbsolutePath().toString());}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile minutes library is not installed for this device",error);}
    }
}
