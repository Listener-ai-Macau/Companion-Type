package com.denzic.companion.mobile;
import java.util.Locale;

/** Advertisement names are discovery hints only; the connected protocol authenticates identity. */
public final class DeviceNames {
    private DeviceNames(){}
    public static boolean candidate(String name,boolean publishedRecordingService){
        if(publishedRecordingService)return true;
        String normalized=name==null?"":name.trim().toLowerCase(Locale.ROOT);
        return normalized.contains("companion")||normalized.contains("capture");
    }
}
