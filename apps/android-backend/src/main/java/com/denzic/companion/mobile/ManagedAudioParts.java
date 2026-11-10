package com.denzic.companion.mobile;

import java.io.FileOutputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Recoverable, app-private decoded-audio cache. Run on a worker thread. */
public final class ManagedAudioParts {
    private static final byte[] MAGIC_V1="Companion decoded audio v1\n".getBytes(StandardCharsets.UTF_8);
    private static final byte[] MAGIC_V2="Companion decoded audio v2\n".getBytes(StandardCharsets.UTF_8);
    private static final String MARKER=".companion-decode-owner";
    private ManagedAudioParts() {}
    /** Counts attempts removed or retained when clearing one recording's cache. */
    public static final class ClearResult {
        public final int removedAttempts,retainedAttempts;
        ClearResult(int removed,int retained){removedAttempts=removed;retainedAttempts=retained;}
    }
    private interface Operation<T>{T run()throws IOException;}
    private static <T> T locked(Path root,Operation<T> operation)throws IOException {
        try(RandomAccessFile lockFile=new RandomAccessFile(root.resolve(".companion-decode.lock").toFile(),"rw");FileChannel channel=lockFile.getChannel()) {
            FileLock lock;
            try{lock=channel.tryLock();}catch(OverlappingFileLockException e){throw new IOException("audio preparation is already running; retry",e);}
            if(lock==null)throw new IOException("audio preparation is already running; retry");
            try{return operation.run();}finally{lock.release();}
        }
    }

    /**
     * Reuse a verified decoded set or create one from the original session.
     * cacheRoot is an app-private directory reserved for this cache. A process
     * interruption can leave an incomplete attempt; the next call removes only
     * its known temporary files and retries. Originals are never changed.
     * Use the returned directory for playback and transcription.
     */
    public static NativeAudio.PartsResult prepare(RecordingLibrary.Session session,Path cacheRoot)throws IOException {
        if(session==null||cacheRoot==null)throw new IllegalArgumentException("recording and private cache required");
        if(session.imported!=null)return session.imported.verifiedParts();
        byte[] fingerprint=DeviceBookmarkCache.fingerprint(session);
        byte[] identity=sessionIdentity(session);
        Path root=cacheRoot.toAbsolutePath();Files.createDirectories(root);
        if(!Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS))throw new IOException("audio cache directory unavailable");
        return locked(root,()->{
                List<Path> owned=new ArrayList<>();
                try(DirectoryStream<Path> entries=Files.newDirectoryStream(root,"attempt-*")) {
                    for(Path entry:entries)try{if(owned(entry,fingerprint,identity,false))owned.add(entry);}
                    catch(IOException ignored){ /* leave unreadable entries untouched */ }
                }
                for(Path entry:owned) {
                    if(!Files.exists(entry.resolve("parts").resolve(".companion-parts"),LinkOption.NOFOLLOW_LINKS)) {
                        try{cleanupIncomplete(entry);}catch(IOException ignored){ /* keep the remnant and allow retry */ }
                    }
                }
                for(Path entry:owned) {
                    Path parts=entry.resolve("parts");
                    if(Files.exists(parts.resolve(".companion-parts"),LinkOption.NOFOLLOW_LINKS)) {
                        try {
                            NativeAudio.PartsResult saved=NativeAudio.loadParts(session,parts);
                            if(saved!=null)return saved;
                        } catch(IOException damaged) { /* retain this copy and rebuild from originals */ }
                    }
                }
                Path attempt=Files.createDirectory(root.resolve("attempt-"+UUID.randomUUID()));
                Path marker=attempt.resolve(MARKER);
                try(FileOutputStream file=new FileOutputStream(marker.toFile())) {
                    file.write(MAGIC_V2);file.write(identity);file.write(fingerprint);file.getFD().sync();
                }
                try{return NativeAudio.decodeParts(session,attempt.resolve("parts"));}
                catch(IOException|RuntimeException error) {
                    try{cleanupIncomplete(attempt);}catch(IOException cleanup){error.addSuppressed(cleanup);}
                    throw error;
                }
        });
    }

    /**
     * Explicitly clear decoded cache copies for this recording, e.g. when the
     * user chooses to free space. This does not remove the original recording,
     * device data, transcript, minutes or other recordings. Stop playback and
     * transcription first. Retained attempts contain unknown files or could not
     * be removed; report them and allow the caller to retry.
     */
    public static ClearResult clear(RecordingLibrary.Session session,Path cacheRoot)throws IOException {
        if(session==null||cacheRoot==null)throw new IllegalArgumentException("recording and private cache required");
        if(session.segments.isEmpty())throw new IllegalArgumentException("recording session required");
        byte[] fingerprint=descriptorFingerprint(session),identity=sessionIdentity(session);
        return clearMatching(cacheRoot,fingerprint,identity);
    }
    /**
     * Clear v2 cache copies using the stable key saved for the recording even if
     * its original metadata is no longer available. Earlier v1 cache markers do
     * not contain that identity and cannot be matched by this method.
     */
    public static ClearResult clearBySessionKey(String sessionKey,Path cacheRoot)throws IOException {
        if(sessionKey==null||sessionKey.isEmpty()||cacheRoot==null)throw new IllegalArgumentException("recording key and private cache required");
        return clearMatching(cacheRoot,null,identityHash(sessionKey));
    }
    private static ClearResult clearMatching(Path cacheRoot,byte[] fingerprint,byte[] identity)throws IOException {
        Path root=cacheRoot.toAbsolutePath();
        if(!Files.exists(root,LinkOption.NOFOLLOW_LINKS))return new ClearResult(0,0);
        if(!Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS))throw new IOException("audio cache directory unavailable");
        return locked(root,()->{
            int removed=0,retained=0;
            try(DirectoryStream<Path> entries=Files.newDirectoryStream(root,"attempt-*")) {
                for(Path entry:entries) {
                    boolean matches;
                    try{matches=owned(entry,fingerprint,identity,true);}catch(IOException unreadable){continue;}
                    if(!matches)continue;
                    try{if(removeAttempt(entry,true))removed++;else retained++;}catch(IOException failure){retained++;}
                }
            }
            return new ClearResult(removed,retained);
        });
    }

    private static byte[] sessionIdentity(RecordingLibrary.Session session) {
        return identityHash(MeetingStore.sessionKey(session.segments.get(0).descriptor));
    }
    private static byte[] identityHash(String key) {
        try{return MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8));}
        catch(java.security.NoSuchAlgorithmException unavailable){throw new AssertionError(unavailable);}
    }
    // Cache ownership can be checked from descriptors even when an original
    // file became damaged; cleanup must not require a healthy recording.
    private static byte[] descriptorFingerprint(RecordingLibrary.Session session) {
        try {
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            for(RecordingLibrary.Entry entry:session.segments) {
                byte[] wire=entry.descriptor.wireBytes();wire[95]=0;java.util.Arrays.fill(wire,108,112,(byte)0);digest.update(wire);
            }
            return digest.digest();
        } catch(java.security.NoSuchAlgorithmException unavailable){throw new AssertionError(unavailable);}
    }
    private static boolean owned(Path attempt,byte[] fingerprint,byte[] identity,boolean allVersions)throws IOException {
        String name=attempt.getFileName().toString();
        try{UUID.fromString(name.substring("attempt-".length()));}catch(IllegalArgumentException|IndexOutOfBoundsException e){return false;}
        if(!Files.isDirectory(attempt,LinkOption.NOFOLLOW_LINKS))return false;
        Path marker=attempt.resolve(MARKER);
        if(!Files.isRegularFile(marker,LinkOption.NOFOLLOW_LINKS))return false;
        long size=Files.size(marker);
        if(size!=MAGIC_V1.length+32&&size!=MAGIC_V2.length+identity.length+32)return false;
        byte[] actual=Files.readAllBytes(marker);
        if(actual.length==MAGIC_V1.length+32) {
            if(fingerprint==null)return false;
            byte[] expected=new byte[MAGIC_V1.length+fingerprint.length];
            System.arraycopy(MAGIC_V1,0,expected,0,MAGIC_V1.length);System.arraycopy(fingerprint,0,expected,MAGIC_V1.length,fingerprint.length);
            return MessageDigest.isEqual(actual,expected);
        }
        byte[] prefix=new byte[MAGIC_V2.length+identity.length];
        System.arraycopy(MAGIC_V2,0,prefix,0,MAGIC_V2.length);System.arraycopy(identity,0,prefix,MAGIC_V2.length,identity.length);
        if(!MessageDigest.isEqual(prefix,java.util.Arrays.copyOf(actual,prefix.length)))return false;
        return allVersions||MessageDigest.isEqual(fingerprint,java.util.Arrays.copyOfRange(actual,prefix.length,actual.length));
    }

    private static void cleanupIncomplete(Path attempt)throws IOException {
        removeAttempt(attempt,false);
    }
    private static boolean removeAttempt(Path attempt,boolean allowCompleted)throws IOException {
        Path parts=attempt.resolve("parts");
        if(!allowCompleted&&Files.exists(parts.resolve(".companion-parts"),LinkOption.NOFOLLOW_LINKS))return false;
        List<Path> files=new ArrayList<>();
        try(DirectoryStream<Path> entries=Files.newDirectoryStream(attempt)) {
            for(Path entry:entries)if(!entry.getFileName().toString().equals(MARKER)&&!entry.equals(parts))return false;
        }
        if(Files.exists(parts,LinkOption.NOFOLLOW_LINKS)) {
            if(!Files.isDirectory(parts,LinkOption.NOFOLLOW_LINKS))return false;
            try(DirectoryStream<Path> entries=Files.newDirectoryStream(parts)) {
                for(Path entry:entries) {
                    String name=entry.getFileName().toString();
                    if(!Files.isRegularFile(entry,LinkOption.NOFOLLOW_LINKS)||
                        !(name.matches("part-[0-9]{8}\\.wav")||(name.startsWith(".parts-receipt-")&&name.endsWith(".tmp"))||
                          (allowCompleted&&name.equals(".companion-parts"))))return false;
                    files.add(entry);
                }
            }
            for(Path file:files)Files.delete(file);
            Files.delete(parts);
        }
        Files.delete(attempt.resolve(MARKER));Files.delete(attempt);
        return true;
    }
}
