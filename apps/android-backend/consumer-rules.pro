# Preserve JNI entry points when a consuming app enables shrinking.
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeAudio {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeTranscription {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeCalendar {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeMemo {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeMinutes {
    native <methods>;
}
-keepclasseswithmembernames,includedescriptorclasses class com.denzic.companion.mobile.NativeRecordingControl {
    native <methods>;
}
-keepclassmembers class com.denzic.companion.mobile.NativeRecordingControl$Callbacks {
    public byte[] identity();
    public byte[] status();
    public void writeControl(byte[]);
    public byte[] capacitySlots(byte[]);
}
