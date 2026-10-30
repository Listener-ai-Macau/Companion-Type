package com.denzic.companion.mobile;

import java.nio.file.Paths;

/** Exercises the native bridge's configuration failure without contacting a service. */
public final class NativeTranscriptionJvmTest {
    public static void main(String[] args)throws Exception {
        try {
            NativeTranscription.transcribe(Paths.get("synthetic-unused.wav"),"","","test-resource");
            throw new AssertionError("missing credentials unexpectedly accepted");
        } catch(java.io.IOException expected) {
            if(!expected.getMessage().contains("configuration is incomplete"))throw expected;
        }
        System.out.println("PASS Java-to-native ASR bridge rejects missing configuration without a network call");
    }
}
