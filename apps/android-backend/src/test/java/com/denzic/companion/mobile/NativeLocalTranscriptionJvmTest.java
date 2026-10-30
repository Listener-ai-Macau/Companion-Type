package com.denzic.companion.mobile;

import java.nio.file.Path;
import java.nio.file.Paths;

/** Host JNI smoke test with synthetic audio and a locally installed pinned runtime. */
public final class NativeLocalTranscriptionJvmTest {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("fixture, model root and cache required");
        Path wav = Paths.get(args[0]);
        Path model = Paths.get(args[1]);
        Path cache = Paths.get(args[2]);
        String first = NativeLocalTranscription.transcribe(wav, model, model, cache);
        String resumed = NativeLocalTranscription.transcribe(wav, model, model, cache);
        if (!first.contains("蓝色文件夹") || !first.equals(resumed))
            throw new AssertionError("Synthetic speech or cached retry failed: " + first);
        System.out.println("local JNI synthetic transcription and retry passed");
    }
}
