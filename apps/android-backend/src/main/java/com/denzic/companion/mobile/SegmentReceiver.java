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
    private final boolean existingComplete;
    private long offset,sequence;
    private long boundaryBytes;
    private byte[] boundarySha;
    private boolean closed,published;

    private static final char[] HEX="0123456789abcdef".toCharArray();
    private static String hex(byte[] data) {
        char[] out=new char[data.length*2];for(int i=0;i<data.length;i++){int value=data[i]&255;out[i*2]=HEX[value>>>4];out[i*2+1]=HEX[value&15];}return new String(out);
    }
    static String sessionPrefix(RecorderWire.Descriptor d) {return hex(d.uid())+"-"+Long.toUnsignedString(d.epoch,16)+"-"+Long.toUnsignedString(d.sessionId,16)+"-";}
    static String key(RecorderWire.Descriptor d) {return sessionPrefix(d)+d.segmentIndex+"-"+d.recordingId+"-"+hex(d.sha256());}
    private static MessageDigest digest() {try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}}
    private Path damagedPath(String extension) {return part.resolveSibling("damaged-"+Long.toUnsignedString(descriptor.sessionId,16)+"-"+descriptor.recordingId+"-"+UUID.randomUUID()+extension);}

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
        RandomAccessFile f=null;MessageDigest h=digest();boolean alreadyComplete=false;
        try {
            RangeCheckpoint.verifySavedPrefix(privateDirectory,descriptor);
            Path metadata=privateDirectory.resolve(key+".meta");
            boolean saveMetadata=!Files.exists(metadata);
            if(!saveMetadata) {
                RecorderWire.Descriptor previous=RecorderWire.Descriptor.decode(Files.readAllBytes(metadata));
                if(!descriptor.sameContent(previous))throw new IOException("recording metadata conflict; existing copy preserved");
                if(previous.startedUnixSeconds!=0 && descriptor.startedUnixSeconds!=0 &&
                    previous.startedUnixSeconds!=descriptor.startedUnixSeconds)throw new IOException("recording date changed");
                saveMetadata=previous.startedUnixSeconds==0 && descriptor.startedUnixSeconds!=0;
            }
            if(saveMetadata) {
                Path temporary=privateDirectory.resolve(key+"."+UUID.randomUUID()+".meta-tmp");
                try(RandomAccessFile m=new RandomAccessFile(temporary.toFile(),"rw")){m.write(descriptor.metadataBytes());m.getFD().sync();}
                try{Files.move(temporary,metadata,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}finally{Files.deleteIfExists(temporary);}
            }
            if(Files.exists(complete)) {
                if(RecordingLibrary.verified(complete,descriptor)){alreadyComplete=true;this.offset=descriptor.encodedLength;}
                else {
                    Files.move(complete,damagedPath(".cop1"),StandardCopyOption.ATOMIC_MOVE);
                }
            }
            if(!alreadyComplete) {
                f=new RandomAccessFile(part.toFile(),"rw");long size=f.length();
                if(size>descriptor.encodedLength) {f.close();f=null;Files.move(part,damagedPath(".part"),StandardCopyOption.ATOMIC_MOVE);f=new RandomAccessFile(part.toFile(),"rw");size=0;}
                byte[] buffer=new byte[32768];long read=0;while(read<size){int n=f.read(buffer,0,(int)Math.min(buffer.length,size-read));if(n<0)throw new IOException("partial recording changed while reading");rememberBoundary(h,buffer,n,read);h.update(buffer,0,n);crc.update(buffer,0,n);read+=n;}f.seek(size);this.offset=size;
            }
        } catch(IOException|RuntimeException e){if(f!=null)f.close();held.release();lc.close();lf.close();throw e;}
        this.file=f;this.lockFile=lf;this.lockChannel=lc;this.lock=held;this.sha=h;this.existingComplete=alreadyComplete;
    }
    public long resumeOffset() {return offset;}
    public long nextSequence() {return sequence;}
    public boolean completeBytesReceived() {return offset==descriptor.encodedLength;}
    void verifyOriginal()throws IOException {
        if(closed||!completeBytesReceived())throw new IOException("recording is incomplete; saved source retained");
        if(existingComplete)return;
        byte[] actual;
        try{actual=((MessageDigest)sha.clone()).digest();}
        catch(CloneNotSupportedException unsupported){
            if(!RecordingLibrary.verified(part,descriptor))throw new IOException("recording integrity mismatch; saved source retained");
            return;
        }
        if(crc.getValue()!=descriptor.contentCrc||!Arrays.equals(actual,descriptor.sha256()))
            throw new IOException("recording integrity mismatch; saved source retained");
    }

    /** Future negotiated range consumer only; ordinary download never calls
     * this. The existing receiver lock stays held until physical confirmation. */
    RangeCheckpoint checkpointRange(Path directory,int firstSector,int endSector,long nonce,
            RangeCheckpoint.DirectorySync sync)throws IOException {
        return prepareRangeCheckpoint(directory,firstSector,endSector,nonce,sync).persist();
    }
    /** Capture immutable accepted bounds/hash on the receiver thread. The
     * caller retains this receiver's lock and joins the persistence worker
     * before publishing/renaming/closing the source. Later appends do not
     * mutate the captured prefix and need not wait for filesystem sync. */
    RangeCheckpoint.Save prepareRangeCheckpoint(Path directory,int firstSector,int endSector,long nonce,
            RangeCheckpoint.DirectorySync sync)throws IOException {
        return prepareRangeCheckpoint(directory,firstSector,endSector,nonce,sync,null,false);
    }
    RangeCheckpoint.Save prepareQueuedRangeCheckpoint(Path directory,int firstSector,int endSector,long nonce,
            RangeCheckpoint.DirectorySync sync,java.util.function.Supplier<RangeCheckpoint> previous)throws IOException {
        return prepareRangeCheckpoint(directory,firstSector,endSector,nonce,sync,previous,true);
    }
    private RangeCheckpoint.Save prepareRangeCheckpoint(Path directory,int firstSector,int endSector,long nonce,
            RangeCheckpoint.DirectorySync sync,java.util.function.Supplier<RangeCheckpoint> previous,boolean queue)throws IOException {
        if(closed||published)throw new IOException("receiver is closed");
        long end=Math.min(descriptor.encodedLength,((long)endSector*16-1)*248);
        if(end>offset)throw new IOException("recording range is not fully received");
        if(!part.getParent().toAbsolutePath().normalize().equals(directory.toAbsolutePath().normalize()))
            throw new IOException("recording range belongs to a different directory");
        byte[] prefix=null;
        if(existingComplete&&end==descriptor.encodedLength)prefix=descriptor.sha256();
        else if(end==boundaryBytes)prefix=boundarySha;
        else if(end==offset)try{prefix=((MessageDigest)sha.clone()).digest();}catch(CloneNotSupportedException unsupported){/* full readback fallback retains correctness */}
        final byte[] acceptedSha=prefix==null?null:prefix.clone();
        return queue?()->RangeCheckpoint.saveQueuedOwned(directory,descriptor,firstSector,endSector,nonce,sync,end,acceptedSha,previous.get()):
            ()->RangeCheckpoint.saveOwned(directory,descriptor,firstSector,endSector,nonce,sync,end,acceptedSha);
    }
    private void rememberBoundary(MessageDigest digest,byte[] payload,int length,long start){
        long sector=((start+length)/248+1)/16;
        long end=sector==0?0:(sector*16-1)*248;
        if(end<=start)return;
        boundaryBytes=end;boundarySha=null;
        try{MessageDigest copy=(MessageDigest)digest.clone();copy.update(payload,0,(int)(end-start));boundarySha=copy.digest();}
        catch(CloneNotSupportedException unsupported){/* checkpoint uses exact readback */}
    }

    public void accept(byte[] notification) throws IOException {
        if(closed||published||completeBytesReceived())throw new IOException("receiver is not accepting chunks");
        byte[] payload=RecorderWire.packet(descriptor,notification,sequence,offset);
        file.write(payload);rememberBoundary(sha,payload,payload.length,offset);sha.update(payload);crc.update(payload);offset+=payload.length;sequence++;
    }

    /** Verify full encoded bytes and publish a local copy; this does not prove playback or clear the device. */
    public Path finish() throws IOException {
        return finish(true);
    }
    /** Publish the same fully synced original while retaining the descriptor
     * lock until queued range receipts and the terminal handoff have settled. */
    Path finishRetainingLock()throws IOException{return finish(false);}
    private Path finish(boolean release)throws IOException {
        if(closed||published||!completeBytesReceived())throw new IOException("recording is incomplete; partial file retained");
        if(existingComplete){if(release)close();else published=true;return complete;}
        if(crc.getValue()!=descriptor.contentCrc||!Arrays.equals(sha.digest(),descriptor.sha256())) {
            if(RangeCheckpoint.exists(part.getParent(),descriptor))
                throw new IOException("recording integrity mismatch after partial reclamation; saved source retained, automatic restart disabled");
            file.getFD().sync();file.close();
            try {Files.move(part,damagedPath(".part"),StandardCopyOption.ATOMIC_MOVE);throw new IntegrityMismatch();}
            finally {close();}
        }
        file.getFD().sync();file.close();
        try {
            if(Files.exists(complete))throw new IOException("existing recording preserved");
            Files.move(part,complete,StandardCopyOption.ATOMIC_MOVE);
            published=true;
            return complete;
        } finally {if(release||!published)close();}
    }
    @Override public void close() throws IOException {
        if(closed)return;closed=true;IOException problem=null;
        try{if(file!=null)file.close();}catch(IOException e){problem=e;}
        try{lock.release();}catch(IOException e){if(problem==null)problem=e;}
        try{lockChannel.close();}catch(IOException e){if(problem==null)problem=e;}
        try{lockFile.close();}catch(IOException e){if(problem==null)problem=e;}
        if(problem!=null)throw problem;
    }
}
