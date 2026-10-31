package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Decode an ordered local session to 16 kHz mono WAV on a worker thread. */
public final class NativeAudio {
    private NativeAudio() {}
    /** Device-authored mark on the same recording, with captured and playback positions. */
    public static final class Bookmark {
        public final long sequence,sourceSamples,playbackSamples,elapsedMillis;
        private Bookmark(long sequence,long source,long playback,long elapsed) {
            this.sequence=sequence;sourceSamples=source;playbackSamples=playback;elapsedMillis=elapsed;
        }
    }
    public static final class Result {
        public final Path path;
        public final long samples;
        public final boolean captureComplete;
        public final List<Bookmark> bookmarks;
        private Result(Path path,long samples,boolean captureComplete,List<Bookmark> bookmarks) {
            this.path=path;this.samples=samples;this.captureComplete=captureComplete;
            this.bookmarks=Collections.unmodifiableList(bookmarks);
        }
    }
    private static native long decodeFiles(String[] paths,byte[][] descriptors,String output) throws IOException;
    private static native long[] decodeFilesDetailed(String[] paths,byte[][] descriptors,String output) throws IOException;

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
        try {
            long[] values=decodeFilesDetailed(paths,descriptors,output.toAbsolutePath().toString());
            if(values==null||values.length<1||(values.length-1)%4!=0)throw new IOException("invalid audio metadata; originals retained");
            List<Bookmark> marks=new ArrayList<>();
            for(int i=1;i<values.length;i+=4)marks.add(new Bookmark(values[i],values[i+1],values[i+2],values[i+3]));
            return new Result(output,values[0],complete,marks);
        } catch(UnsatisfiedLinkError error){throw new IOException("mobile audio decoder needs the matching backend version",error);}
    }
}
