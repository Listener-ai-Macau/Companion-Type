package com.denzic.companion.mobile;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/** Rebuildable positions of device marks, bound to the verified recording segments. */
public final class DeviceBookmarkCache {
    private static final int MAGIC=0x43424d31, FIXED_BYTES=81, MAX_BYTES=16*1024*1024;
    private final Path directory;
    public DeviceBookmarkCache(Path appPrivateDirectory) {
        if(appPrivateDirectory==null)throw new IllegalArgumentException("private directory required");
        directory=appPrivateDirectory;
    }
    public static final class Saved {
        public final long samples;
        public final boolean captureComplete;
        public final List<NativeAudio.Bookmark> bookmarks;
        private Saved(long samples,boolean complete,List<NativeAudio.Bookmark> marks) {
            this.samples=samples;captureComplete=complete;bookmarks=Collections.unmodifiableList(marks);
        }
    }
    private static MessageDigest digest() {
        try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}
    }
    private static String hex(byte[] value) {
        StringBuilder result=new StringBuilder();for(byte b:value)result.append(String.format(Locale.ROOT,"%02x",b&255));return result.toString();
    }
    private Path path(RecordingLibrary.Session session) {
        String key=session.key();
        return directory.resolve(hex(digest().digest(key.getBytes(java.nio.charset.StandardCharsets.UTF_8)))+".device-marks");
    }
    /* syncState can change after a receipt; it does not change the recording. */
    static byte[] fingerprint(RecordingLibrary.Session session)throws IOException {
        if(session!=null&&session.imported!=null)return session.imported.fingerprint();
        if(session==null||session.segments.isEmpty())throw new IllegalArgumentException("recording session required");
        if(session.state==RecordingLibrary.SessionState.DAMAGED)throw new IOException("recording is damaged; originals retained");
        MessageDigest hash=digest();
        for(RecordingLibrary.Entry entry:session.segments) {
            if(entry.state!=RecordingLibrary.State.VERIFIED)throw new IOException("recording has segments that have not been fully received");
            byte[] wire=entry.descriptor.wireBytes();wire[95]=0;Arrays.fill(wire,108,112,(byte)0);hash.update(wire);
        }
        return hash.digest();
    }
    /** Save the marks returned by decoding this exact session; no audio is modified. */
    public void save(RecordingLibrary.Session session,NativeAudio.Result result)throws IOException {
        if(result==null)throw new IllegalArgumentException("decoded recording required");
        byte[] source=fingerprint(session);
        if(!MessageDigest.isEqual(source,result.sourceFingerprint))throw new IOException("decoded audio belongs to a different recording; decode again");
        if(result.bookmarks.size()>(MAX_BYTES-FIXED_BYTES)/32)throw new IOException("too many device marks to index; original recording retained");
        ByteArrayOutputStream buffer=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(buffer);
        out.writeInt(MAGIC);out.write(source);out.writeLong(result.samples);out.writeBoolean(result.captureComplete);out.writeInt(result.bookmarks.size());
        for(NativeAudio.Bookmark mark:result.bookmarks) {out.writeLong(mark.sequence);out.writeLong(mark.sourceSamples);out.writeLong(mark.playbackSamples);out.writeLong(mark.elapsedMillis);}
        out.flush();byte[] body=buffer.toByteArray();buffer.write(digest().digest(body));
        Files.createDirectories(directory);Path temporary=Files.createTempFile(directory,".device-marks-",".tmp");
        try {
            try(FileOutputStream file=new FileOutputStream(temporary.toFile())) {file.write(buffer.toByteArray());file.getFD().sync();}
            Files.move(temporary,path(session),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        } finally {Files.deleteIfExists(temporary);}
    }
    /** Null means no valid matching index: the caller can decode the original again. */
    public Saved load(RecordingLibrary.Session session)throws IOException {
        byte[] expected=fingerprint(session);Path file=path(session);
        if(!Files.exists(file))return null;
        long size=Files.size(file);if(size<FIXED_BYTES||size>MAX_BYTES)return null;
        byte[] bytes=Files.readAllBytes(file);if(bytes.length!=size)return null;
        int length=bytes.length-32;MessageDigest hash=digest();hash.update(bytes,0,length);
        if(!MessageDigest.isEqual(hash.digest(),Arrays.copyOfRange(bytes,length,bytes.length)))return null;
        DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes,0,length));
        if(in.readInt()!=MAGIC)return null;byte[] actual=new byte[32];in.readFully(actual);
        long samples=in.readLong();boolean complete=in.readBoolean();int count=in.readInt();
        if(!MessageDigest.isEqual(expected,actual)||samples<0||count<0||count!=(length-(FIXED_BYTES-32))/32||(length-(FIXED_BYTES-32))%32!=0)return null;
        List<NativeAudio.Bookmark> marks=new ArrayList<>(count);
        for(int i=0;i<count;i++) {
            long sequence=in.readLong(),source=in.readLong(),playback=in.readLong(),elapsed=in.readLong();
            if(sequence<0||source<0||playback<0||playback>samples||elapsed<0)return null;
            marks.add(new NativeAudio.Bookmark(sequence,source,playback,elapsed));
        }
        return new Saved(samples,complete,marks);
    }
}
