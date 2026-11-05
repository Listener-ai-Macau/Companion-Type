package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;

/** Explicit one-shot cloud recognition. Runs on a worker thread. */
public final class NativeTranscription {
    private NativeTranscription() {}
    /** Runs on the caller's worker; return false to stop after the current request. */
    public interface Progress { boolean onProgress(long processedMillis, long totalMillis); }
    private static native String transcribeFileWithCache(String wav,String appId,String accessToken,String resourceId,String privateCacheDirectory) throws IOException;

    private static native String transcribeFilesWithCache(String[] wavs,String appId,String accessToken,String resourceId,String privateCacheDirectory) throws IOException;
    private static native String transcribeFilesObserved(String[] wavs,String appId,String accessToken,String resourceId,String privateCacheDirectory,Progress progress) throws IOException;

    /** Cloud transcription with processed-audio progress and cancellation. */
    public static String transcribeWithProgress(Path wav,String appId,String accessToken,String resourceId,Path privateCacheDirectory,Progress progress) throws IOException {
        if(wav==null||appId==null||accessToken==null||resourceId==null||progress==null)
            throw new IllegalArgumentException("recording, service configuration and progress callback are required");
        return observed(new String[]{wav.toAbsolutePath().toString()},appId,accessToken,resourceId,privateCacheDirectory,progress);
    }

    /** Transcribe every verified part with one continuous progress timeline. */
    public static String transcribePartsWithProgress(RecordingLibrary.Session session,Path directory,String appId,String accessToken,String resourceId,Path privateCacheDirectory,Progress progress) throws IOException {
        if(session==null||directory==null||appId==null||accessToken==null||resourceId==null||progress==null)
            throw new IllegalArgumentException("recording, parts, service configuration and progress callback are required");
        NativeAudio.PartsResult result=NativeAudio.loadParts(session,directory);
        if(result==null)throw new IOException("complete audio parts are unavailable for this recording; original retained");
        String[] paths=new String[result.parts.size()];
        for(int i=0;i<paths.length;i++)paths[i]=result.parts.get(i).path.toAbsolutePath().toString();
        return observed(paths,appId,accessToken,resourceId,privateCacheDirectory,progress);
    }

    private static String observed(String[] paths,String appId,String accessToken,String resourceId,Path cache,Progress progress) throws IOException {
        try {
            System.loadLibrary("companion_mobile_audio");
            return transcribeFilesObserved(paths,appId,accessToken,resourceId,cache==null?"":cache.toAbsolutePath().toString(),progress);
        } catch(UnsatisfiedLinkError error){throw new IOException("mobile recognition library is not installed for this device",error);}
    }

    /** Send every verified part to the configured cloud service, in order, on a worker thread. */
    public static String transcribeParts(RecordingLibrary.Session session,Path directory,String appId,String accessToken,String resourceId,Path privateCacheDirectory) throws IOException {
        if(session==null||directory==null||appId==null||accessToken==null||resourceId==null)
            throw new IllegalArgumentException("recording, parts and service configuration are required");
        NativeAudio.PartsResult result=NativeAudio.loadParts(session,directory);
        if(result==null)throw new IOException("complete audio parts are unavailable for this recording; original retained");
        String[] paths=new String[result.parts.size()];
        for(int i=0;i<paths.length;i++)paths[i]=result.parts.get(i).path.toAbsolutePath().toString();
        try {
            System.loadLibrary("companion_mobile_audio");
            return transcribeFilesWithCache(paths,appId,accessToken,resourceId,privateCacheDirectory==null?"":privateCacheDirectory.toAbsolutePath().toString());
        } catch(UnsatisfiedLinkError error){throw new IOException("mobile recognition library is not installed for this device",error);}
    }

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
