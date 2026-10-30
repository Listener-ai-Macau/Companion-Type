package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;

/** Explicit one-shot cloud recognition. Runs on a worker thread. */
public final class NativeTranscription {
    private NativeTranscription() {}
    private static native String transcribeFileWithCache(String wav,String appId,String accessToken,String resourceId,String privateCacheDirectory) throws IOException;

    /**
     * Sends this WAV to the user's configured Volcengine service, which may charge for usage.
     * The host app must make this action and provider clear to the user before calling it.
     * This method neither stores credentials nor starts recognition automatically.
     */
    public static String transcribe(Path wav,String appId,String accessToken,String resourceId) throws IOException {
        return transcribe(wav,appId,accessToken,resourceId,null);
    }

    /** Use app-private persistent storage to reuse successfully recognized chunks after a failure. */
    public static String transcribe(Path wav,String appId,String accessToken,String resourceId,Path privateCacheDirectory) throws IOException {
        if(wav==null||appId==null||accessToken==null||resourceId==null)throw new IllegalArgumentException("WAV and service configuration are required");
        try {
            System.loadLibrary("companion_mobile_audio");
            return transcribeFileWithCache(wav.toAbsolutePath().toString(),appId,accessToken,resourceId,privateCacheDirectory==null?"":privateCacheDirectory.toAbsolutePath().toString());
        } catch(UnsatisfiedLinkError error) {throw new IOException("mobile recognition library is not installed for this device",error);}
    }
}
