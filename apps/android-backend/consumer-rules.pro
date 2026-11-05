# Preserve JNI entry points when a consuming app enables shrinking.
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeAudio {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeTranscription {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeLocalTranscription {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeCalendar {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeMemo {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeMeetingDocuments {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeMinutes {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeMeetingQa {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeRecordingControl {
    native <methods>;
}
-keepclassmembers class com.denzic.companion.mobile.NativeRecordingControl$Callbacks {
    public byte[] identity();
    public byte[] status();
    public byte[][] catalogue();
    public java.lang.String[] localFiles();
    public void writeControl(byte[]);
    public byte[] capacitySlots(byte[]);
}

# The native worker calls this interface by name after each audio window.
-keepclassmembers interface com.denzic.companion.mobile.NativeLocalTranscription$Progress {
    public boolean onProgress(long, long);
}
-keepclassmembers interface com.denzic.companion.mobile.NativeTranscription$Progress {
    public boolean onProgress(long, long);
}
-keepclassmembers interface com.denzic.companion.mobile.NativeMinutes$Progress {
    public boolean onProgress(long, long);
}
