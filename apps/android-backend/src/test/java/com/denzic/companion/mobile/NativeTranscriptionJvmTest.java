package com.denzic.companion.mobile;

import java.nio.file.Paths;
import java.nio.file.Files;
import java.nio.file.Path;

/** Exercises the native bridge's configuration failure without contacting a service. */
public final class NativeTranscriptionJvmTest {
    public static void main(String[] args)throws Exception {
        try {
            NativeTranscription.transcribe(Paths.get("synthetic-unused.wav"),"","","test-resource");
            throw new AssertionError("missing credentials unexpectedly accepted");
        } catch(java.io.IOException expected) {
            if(!expected.getMessage().contains("configuration is incomplete"))throw expected;
        }
        if(args.length>0) {
            Path cache=Paths.get(args[0]).resolve("must-not-create-cache");
            try {NativeTranscription.transcribe(Paths.get("synthetic-unused.wav"),"","","test-resource",cache);throw new AssertionError("missing credentials unexpectedly accepted");}
            catch(java.io.IOException expected){if(!expected.getMessage().contains("configuration is incomplete"))throw expected;}
            if(Files.exists(cache))throw new AssertionError("invalid configuration created a cache");
        }
        System.out.println("PASS Java-to-native ASR bridge rejects missing configuration without a network call");
    }
}
