package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;

/** User-initiated service-backed minutes; call on a worker thread. */
public final class NativeMinutes {
    private NativeMinutes() {}
    /** Runs on the calling worker. Values are UTF-8 source bytes, not time. */
    public interface Progress { boolean onProgress(long processedBytes,long totalBytes); }
    /** UNKNOWN includes older or malformed results with no recorded supplement source. */
    public enum SupplementStatus { CURRENT, CHANGED, UNKNOWN }
    private static native String generateJson(String request,String apiKey,String privateCacheDirectory) throws IOException;
    private static native String generateJsonObserved(String request,String apiKey,String privateCacheDirectory,Progress progress) throws IOException;
    private static native int compareSupplementSourcesJson(String result,String[] current) throws IOException;
    /** Compare the result with the exact supplements selected for the current version; no network call. */
    public static SupplementStatus supplementStatus(String result,List<String> currentSupplements) throws IOException {
        if(result==null||currentSupplements==null)throw new IllegalArgumentException("result and current supplements required");
        for(String value:currentSupplements)if(value==null)throw new IllegalArgumentException("supplement must not be null");
        try {
            System.loadLibrary("companion_mobile_audio");
            int status=compareSupplementSourcesJson(result,currentSupplements.toArray(new String[0]));
            return status==1?SupplementStatus.CURRENT:status==2?SupplementStatus.CHANGED:SupplementStatus.UNKNOWN;
        } catch(UnsatisfiedLinkError error){throw new IOException("mobile minutes library is not installed for this device",error);}
    }
    /** Stop after the current service request; successfully saved chapters are reused on retry. */
    public static String generateWithProgress(String request,String apiKey,Path privateCacheDirectory,Progress progress) throws IOException {
        if(request==null||apiKey==null||privateCacheDirectory==null||progress==null)
            throw new IllegalArgumentException("request, service key, private cache and progress callback required");
        try {System.loadLibrary("companion_mobile_audio");return generateJsonObserved(request,apiKey,privateCacheDirectory.toAbsolutePath().toString(),progress);}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile minutes library is not installed for this device",error);}
    }
    /** Sends the selected transcript to the configured service; see README for consent and result handling. */
    public static String generate(String request,String apiKey,Path privateCacheDirectory) throws IOException {
        if(request==null||apiKey==null||privateCacheDirectory==null)throw new IllegalArgumentException("request, service key and private cache required");
        try {System.loadLibrary("companion_mobile_audio");return generateJson(request,apiKey,privateCacheDirectory.toAbsolutePath().toString());}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile minutes library is not installed for this device",error);}
    }
}
