package com.denzic.companion.mobile;

import java.io.IOException;

/** User-initiated, source-backed questions over selected transcript text. */
public final class NativeMeetingQa {
    private NativeMeetingQa() {}
    private static native String askJson(String request, String apiKey) throws IOException;
    private static native boolean cancelJson(String jobId);
    /** Sends selected transcript text to the configured service. Call on a worker thread. */
    public static String ask(String request, String apiKey) throws IOException {
        if (request == null || apiKey == null) throw new IllegalArgumentException("request and service key required");
        try { System.loadLibrary("companion_mobile_audio"); return askJson(request, apiKey); }
        catch (UnsatisfiedLinkError error) { throw new IOException("mobile meeting question library is not installed for this device", error); }
    }
    /** Stop before the next segment; the current network request may finish first. */
    public static boolean cancel(String jobId) throws IOException {
        if (jobId == null || jobId.isEmpty()) throw new IllegalArgumentException("jobId required");
        try { System.loadLibrary("companion_mobile_audio"); return cancelJson(jobId); }
        catch (UnsatisfiedLinkError error) { throw new IOException("mobile meeting question library is not installed for this device", error); }
    }
}
