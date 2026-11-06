package com.denzic.companion.mobile;
import java.io.IOException;
import java.nio.file.*;
/** QA fixture assembly through the production inventory key. Never a device write. */
public final class FixtureRecording056 {
    public static String create(Path out,Path recordings)throws IOException{
        RecorderWire.Descriptor d=RecorderWire.Descriptor.decode(Files.readAllBytes(out.resolve("descriptor.bin")));String stem=SegmentReceiver.key(d);
        Files.write(recordings.resolve(stem+".meta"),d.metadataBytes());Files.write(recordings.resolve(stem+".cop1"),Files.readAllBytes(out.resolve("payload.bin")));
        if(RecordingLibrary.inspect(recordings).sessions.get(0).state!=RecordingLibrary.SessionState.COMPLETE)throw new IOException("Synthetic fixture inventory incomplete");return MeetingStore.sessionKey(d);
    }
}
