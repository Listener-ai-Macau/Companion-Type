package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;

/** Decode an ordered local session to 16 kHz mono WAV on a worker thread. */
public final class NativeAudio {
    private NativeAudio() {}
    public static final class Result {
        public final Path path;
        public final long samples;
        public final boolean captureComplete;
        private Result(Path path,long samples,boolean captureComplete) {this.path=path;this.samples=samples;this.captureComplete=captureComplete;}
    }
    private static native long decodeFiles(String[] paths,byte[][] descriptors,String output) throws IOException;

    /** The host must package the matching companion_mobile_audio native library for its ABI. */
    public static Result decode(RecordingLibrary.Session session,Path output) throws IOException {
        if(session==null||output==null)throw new IllegalArgumentException("session and output required");
        if(session.state==RecordingLibrary.SessionState.DAMAGED)throw new IOException("recording is damaged; originals retained");
        int count=session.segments.size();String[] paths=new String[count];byte[][] descriptors=new byte[count][];boolean complete=true;
        for(int i=0;i<count;i++) {
            RecordingLibrary.Entry entry=session.segments.get(i);
            if(entry.state!=RecordingLibrary.State.VERIFIED)throw new IOException("recording has segments that have not been fully received");
            paths[i]=entry.file.toAbsolutePath().toString();descriptors[i]=entry.descriptor.wireBytes();
            if((entry.descriptor.flags&4)!=0)complete=false;
        }
        try {System.loadLibrary("companion_mobile_audio");}
        catch(UnsatisfiedLinkError error){throw new IOException("mobile audio decoder is not installed for this device",error);}
        long samples=decodeFiles(paths,descriptors,output.toAbsolutePath().toString());
        return new Result(output,samples,complete);
    }
}
