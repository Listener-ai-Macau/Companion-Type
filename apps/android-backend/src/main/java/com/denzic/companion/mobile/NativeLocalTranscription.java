package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;

/** Experimental local transcription. Run on a worker thread; no audio is uploaded. */
public final class NativeLocalTranscription {
    private NativeLocalTranscription() {}
    private static native String transcribeFile(String wav, String modelDirectory, String runtimeDirectory, String cacheDirectory) throws IOException;

    /** The host supplies the pinned model, compatible runtime and an app-private cache. */
    public static String transcribe(Path wav, Path modelDirectory, Path runtimeDirectory, Path cacheDirectory) throws IOException {
        if (wav == null || modelDirectory == null || runtimeDirectory == null || cacheDirectory == null)
            throw new IllegalArgumentException("WAV, local model, runtime and private cache are required");
        try {
            System.loadLibrary("companion_mobile_audio");
            return transcribeFile(wav.toAbsolutePath().toString(), modelDirectory.toAbsolutePath().toString(),
                runtimeDirectory.toAbsolutePath().toString(), cacheDirectory.toAbsolutePath().toString());
        } catch (UnsatisfiedLinkError error) {
            throw new IOException("mobile local recognition library is not installed for this device", error);
        }
    }
}
