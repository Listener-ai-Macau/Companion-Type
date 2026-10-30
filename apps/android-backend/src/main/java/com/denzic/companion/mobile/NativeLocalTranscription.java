package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;

/** Experimental local transcription. Run on a worker thread; no audio is uploaded. */
public final class NativeLocalTranscription {
    private NativeLocalTranscription() {}
    private static native String transcribeFile(String wav, String modelDirectory, String runtimeDirectory, String cacheDirectory) throws IOException;

    /** Use the pinned native runtime packaged with this library, including unextracted APK libraries. */
    public static String transcribe(Path wav, Path modelDirectory, Path cacheDirectory) throws IOException {
        if (wav == null || modelDirectory == null || cacheDirectory == null)
            throw new IllegalArgumentException("WAV, local model and private cache are required");
        try {
            System.loadLibrary("onnxruntime");
            System.loadLibrary("sherpa-onnx-c-api");
            System.loadLibrary("companion_mobile_audio");
            return transcribeFile(wav.toAbsolutePath().toString(), modelDirectory.toAbsolutePath().toString(),
                "", cacheDirectory.toAbsolutePath().toString());
        } catch (UnsatisfiedLinkError error) {
            throw new IOException("mobile local recognition runtime is not installed for this device", error);
        }
    }

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
