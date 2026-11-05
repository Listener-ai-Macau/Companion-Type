package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;

/** Experimental local transcription. Run on a worker thread; no audio is uploaded. */
public final class NativeLocalTranscription {
    private NativeLocalTranscription() {}

    /** Runs on the calling worker. Return false to cancel after the current window. */
    public interface Progress {
        boolean onProgress(long processedMillis, long totalMillis);
    }
    private static native String transcribeFile(String wav, String modelDirectory, String runtimeDirectory, String cacheDirectory) throws IOException;
    private static native String transcribeDetailedFile(String wav, String modelDirectory, String runtimeDirectory, String cacheDirectory) throws IOException;

    private static native String transcribeDetailedFiles(String[] wavs, String modelDirectory, String runtimeDirectory, String cacheDirectory) throws IOException;
    private static native String transcribeDetailedFilesObserved(String[] wavs, String modelDirectory, String runtimeDirectory, String cacheDirectory, Progress progress) throws IOException;

    /** Transcribe a complete saved part set on a worker; timestamps span the original recording. */
    public static String transcribeDetailedParts(RecordingLibrary.Session session, Path directory, Path modelDirectory, Path cacheDirectory) throws IOException {
        return transcribeParts(session, directory, modelDirectory, null, cacheDirectory, null);
    }

    /** As above, using a caller-supplied compatible runtime. */
    public static String transcribeDetailedParts(RecordingLibrary.Session session, Path directory, Path modelDirectory, Path runtimeDirectory, Path cacheDirectory) throws IOException {
        if (runtimeDirectory == null) throw new IllegalArgumentException("runtime directory required");
        return transcribeParts(session, directory, modelDirectory, runtimeDirectory, cacheDirectory, null);
    }

    /** Progress is processed audio duration, not an estimate of time remaining. */
    public static String transcribeDetailedPartsWithProgress(RecordingLibrary.Session session, Path directory, Path modelDirectory, Path cacheDirectory, Progress progress) throws IOException {
        if (progress == null) throw new IllegalArgumentException("progress callback required");
        return transcribeParts(session, directory, modelDirectory, null, cacheDirectory, progress);
    }

    /** As above, using a caller-supplied compatible native runtime directory. */
    public static String transcribeDetailedPartsWithProgress(RecordingLibrary.Session session, Path directory, Path modelDirectory, Path runtimeDirectory, Path cacheDirectory, Progress progress) throws IOException {
        if (runtimeDirectory == null || progress == null) throw new IllegalArgumentException("runtime and progress callback required");
        return transcribeParts(session, directory, modelDirectory, runtimeDirectory, cacheDirectory, progress);
    }

    private static String transcribeParts(RecordingLibrary.Session session, Path directory, Path modelDirectory, Path runtimeDirectory, Path cacheDirectory, Progress progress) throws IOException {
        if (session == null || directory == null || modelDirectory == null || cacheDirectory == null)
            throw new IllegalArgumentException("recording, parts, local model and private cache are required");
        NativeAudio.PartsResult result = NativeAudio.loadParts(session, directory);
        if (result == null) throw new IOException("complete audio parts are unavailable for this recording; original retained");
        String[] paths = new String[result.parts.size()];
        for (int i = 0; i < paths.length; i++) paths[i] = result.parts.get(i).path.toAbsolutePath().toString();
        try {
            if (runtimeDirectory == null) { System.loadLibrary("onnxruntime"); System.loadLibrary("sherpa-onnx-c-api"); }
            System.loadLibrary("companion_mobile_audio");
            String model = modelDirectory.toAbsolutePath().toString();
            String runtime = runtimeDirectory == null ? "" : runtimeDirectory.toAbsolutePath().toString();
            String cache = cacheDirectory.toAbsolutePath().toString();
            return progress == null ? transcribeDetailedFiles(paths, model, runtime, cache)
                : transcribeDetailedFilesObserved(paths, model, runtime, cache, progress);
        } catch (UnsatisfiedLinkError error) {
            throw new IOException("mobile local recognition runtime is not installed for this device", error);
        }
    }

    /** Transcribe a single WAV with the same progress and cancellation behavior. */
    public static String transcribeDetailedWithProgress(Path wav, Path modelDirectory, Path cacheDirectory, Progress progress) throws IOException {
        return transcribeSingleObserved(wav, modelDirectory, null, cacheDirectory, progress);
    }

    /** As above, using a caller-supplied compatible native runtime directory. */
    public static String transcribeDetailedWithProgress(Path wav, Path modelDirectory, Path runtimeDirectory, Path cacheDirectory, Progress progress) throws IOException {
        if (runtimeDirectory == null) throw new IllegalArgumentException("runtime directory required");
        return transcribeSingleObserved(wav, modelDirectory, runtimeDirectory, cacheDirectory, progress);
    }

    private static String transcribeSingleObserved(Path wav, Path modelDirectory, Path runtimeDirectory, Path cacheDirectory, Progress progress) throws IOException {
        if (wav == null || modelDirectory == null || cacheDirectory == null || progress == null)
            throw new IllegalArgumentException("WAV, local model, private cache and progress callback are required");
        try {
            if (runtimeDirectory == null) { System.loadLibrary("onnxruntime"); System.loadLibrary("sherpa-onnx-c-api"); }
            System.loadLibrary("companion_mobile_audio");
            return transcribeDetailedFilesObserved(new String[]{wav.toAbsolutePath().toString()},
                modelDirectory.toAbsolutePath().toString(), runtimeDirectory == null ? "" : runtimeDirectory.toAbsolutePath().toString(),
                cacheDirectory.toAbsolutePath().toString(), progress);
        } catch (UnsatisfiedLinkError error) {
            throw new IOException("mobile local recognition runtime is not installed for this device", error);
        }
    }

    /**
     * Transcribe locally and return JSON with full text and approximate input-window
     * positions in milliseconds. These positions are not word-level timestamps.
     * The supplied WAV and cache remain private; run this on a worker thread.
     */
    public static String transcribeDetailed(Path wav, Path modelDirectory, Path cacheDirectory) throws IOException {
        if (wav == null || modelDirectory == null || cacheDirectory == null)
            throw new IllegalArgumentException("WAV, local model and private cache are required");
        try {
            System.loadLibrary("onnxruntime");
            System.loadLibrary("sherpa-onnx-c-api");
            System.loadLibrary("companion_mobile_audio");
            return transcribeDetailedFile(wav.toAbsolutePath().toString(), modelDirectory.toAbsolutePath().toString(),
                "", cacheDirectory.toAbsolutePath().toString());
        } catch (UnsatisfiedLinkError error) {
            throw new IOException("mobile local recognition runtime is not installed for this device", error);
        }
    }

    /** As above, using a caller-supplied compatible native runtime directory. */
    public static String transcribeDetailed(Path wav, Path modelDirectory, Path runtimeDirectory, Path cacheDirectory) throws IOException {
        if (wav == null || modelDirectory == null || runtimeDirectory == null || cacheDirectory == null)
            throw new IllegalArgumentException("WAV, local model, runtime and private cache are required");
        try {
            System.loadLibrary("companion_mobile_audio");
            return transcribeDetailedFile(wav.toAbsolutePath().toString(), modelDirectory.toAbsolutePath().toString(),
                runtimeDirectory.toAbsolutePath().toString(), cacheDirectory.toAbsolutePath().toString());
        } catch (UnsatisfiedLinkError error) {
            throw new IOException("mobile local recognition library is not installed for this device", error);
        }
    }

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
