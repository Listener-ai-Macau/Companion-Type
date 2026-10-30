package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;

/** Explicit one-shot cloud recognition. Runs on a worker thread. */
public final class NativeTranscription {
    private NativeTranscription() {}
    private static native String transcribeFile(String wav,String appId,String accessToken,String resourceId) throws IOException;

    /**
     * Sends this WAV to the user's configured Volcengine service, which may charge for usage.
     * The host app must make this action and provider clear to the user before calling it.
     * This method neither stores credentials nor starts recognition automatically.
     */
    public static String transcribe(Path wav,String appId,String accessToken,String resourceId) throws IOException {
        if(wav==null||appId==null||accessToken==null||resourceId==null)throw new IllegalArgumentException("WAV and service configuration are required");
        try {
            System.loadLibrary("companion_mobile_audio");
            return transcribeFile(wav.toAbsolutePath().toString(),appId,accessToken,resourceId);
        } catch(UnsatisfiedLinkError error) {throw new IOException("mobile recognition library is not installed for this device",error);}
    }
}
