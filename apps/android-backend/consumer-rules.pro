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
