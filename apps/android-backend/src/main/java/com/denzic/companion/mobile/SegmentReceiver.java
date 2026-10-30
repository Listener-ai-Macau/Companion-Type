package com.denzic.companion.mobile;

import java.io.Closeable;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.UUID;
import java.util.zip.CRC32;

/** Receives one sealed segment to private storage. It never deletes device audio. */
public final class SegmentReceiver implements Closeable {
    /** The damaged partial was retained separately, so one fresh transfer can be attempted. */
    static final class IntegrityMismatch extends IOException {
        IntegrityMismatch() {super("recording integrity mismatch; damaged partial retained");}
    }
    private final RecorderWire.Descriptor descriptor;
    private final Path part,complete;
    private final RandomAccessFile file,lockFile;
    private final FileChannel lockChannel;
    private final FileLock lock;
    private final MessageDigest sha;
    private final CRC32 crc=new CRC32();
    private long offset,sequence;
    private boolean closed;

    private static String hex(byte[] data) {StringBuilder b=new StringBuilder(data.length*2);for(byte x:data)b.append(String.format(java.util.Locale.ROOT,"%02x",x&255));return b.toString();}
    static String key(RecorderWire.Descriptor d) {return hex(d.uid())+"-"+Long.toUnsignedString(d.epoch,16)+"-"+Long.toUnsignedString(d.sessionId,16)+"-"+d.segmentIndex+"-"+d.recordingId+"-"+hex(d.sha256());}
    private static MessageDigest digest() {try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}}

    /**
     * Open or resume the exact descriptor's partial file. Existing data is
     * rehashed; a conflict is reported without overwriting either copy.
     * Call from a worker thread, not the UI thread.
     */
    public SegmentReceiver(Path privateDirectory,RecorderWire.Descriptor descriptor) throws IOException {
        if(privateDirectory==null||descriptor==null)throw new IllegalArgumentException("directory and descriptor required");
        this.descriptor=descriptor;Files.createDirectories(privateDirectory);
        String key=key(descriptor);
        part=privateDirectory.resolve(key+".part");complete=privateDirectory.resolve(key+".cop1");
        RandomAccessFile lf=new RandomAccessFile(privateDirectory.resolve(key+".lock").toFile(),"rw");FileChannel lc=lf.getChannel();FileLock held;
        try {held=lc.tryLock();} catch(OverlappingFileLockException e){lc.close();lf.close();throw new IOException("recording is already being received",e);} catch(IOException e){lc.close();lf.close();throw e;}
        if(held==null){lc.close();lf.close();throw new IOException("recording is already being received");}
        RandomAccessFile f=null;
        try {
            Path metadata=privateDirectory.resolve(key+".meta");
            if(Files.exists(metadata)) {
                RecorderWire.Descriptor previous=RecorderWire.Descriptor.decode(Files.readAllBytes(metadata));
                if(!descriptor.sameContent(previous))throw new IOException("recording metadata conflict; existing copy preserved");
            } else {
                Path temporary=privateDirectory.resolve(key+"."+UUID.randomUUID()+".meta-tmp");
                try(RandomAccessFile m=new RandomAccessFile(temporary.toFile(),"rw")){m.write(descriptor.wireBytes());m.getFD().sync();}
                try{Files.move(temporary,metadata,StandardCopyOption.ATOMIC_MOVE);}finally{Files.deleteIfExists(temporary);}
            }
            if(Files.exists(complete))throw new IOException("recording already exists; verify or open the existing copy");
            f=new RandomAccessFile(part.toFile(),"rw");long size=f.length();if(size>descriptor.encodedLength)throw new IOException("partial recording is longer than its descriptor; retained");
            MessageDigest h=digest();byte[] buffer=new byte[32768];long read=0;while(read<size){int n=f.read(buffer,0,(int)Math.min(buffer.length,size-read));if(n<0)throw new IOException("partial recording changed while reading");h.update(buffer,0,n);crc.update(buffer,0,n);read+=n;}f.seek(size);this.offset=size;this.sha=h;
        } catch(IOException|RuntimeException e){if(f!=null)f.close();held.release();lc.close();lf.close();throw e;}
        this.file=f;this.lockFile=lf;this.lockChannel=lc;this.lock=held;
    }
    public long resumeOffset() {return offset;}
    public long nextSequence() {return sequence;}
    public boolean completeBytesReceived() {return offset==descriptor.encodedLength;}

    public void accept(byte[] notification) throws IOException {
        if(closed||completeBytesReceived())throw new IOException("receiver is not accepting chunks");
        byte[] payload=RecorderWire.packet(descriptor,notification,sequence,offset);
        file.write(payload);sha.update(payload);crc.update(payload);offset+=payload.length;sequence++;
    }

    /** Verify full encoded bytes and publish a local copy; this does not prove playback or clear the device. */
    public Path finish() throws IOException {
        if(closed||!completeBytesReceived())throw new IOException("recording is incomplete; partial file retained");
        if(crc.getValue()!=descriptor.contentCrc||!Arrays.equals(sha.digest(),descriptor.sha256())) {
            file.getFD().sync();file.close();
            Path retained=part.resolveSibling("damaged-"+Long.toUnsignedString(descriptor.sessionId,16)+"-"+descriptor.recordingId+"-"+UUID.randomUUID()+".part");
            try {Files.move(part,retained,StandardCopyOption.ATOMIC_MOVE);throw new IntegrityMismatch();}
            finally {close();}
        }
        file.getFD().sync();file.close();
        try {
            if(Files.exists(complete))throw new IOException("existing recording preserved");
            Files.move(part,complete,StandardCopyOption.ATOMIC_MOVE);
            return complete;
        } finally {close();}
    }
    @Override public void close() throws IOException {
        if(closed)return;closed=true;IOException problem=null;
        try{file.close();}catch(IOException e){problem=e;}
        try{lock.release();}catch(IOException e){if(problem==null)problem=e;}
        try{lockChannel.close();}catch(IOException e){if(problem==null)problem=e;}
        try{lockFile.close();}catch(IOException e){if(problem==null)problem=e;}
        if(problem!=null)throw problem;
    }
}
