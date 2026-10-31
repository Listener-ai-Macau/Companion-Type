package com.denzic.companion.mobile;

import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;
import java.util.UUID;

/** Exact, retryable consumption only after the original local prefix is durable. */
final class DurableConsume {
    interface DirectorySync { void sync(Path directory) throws IOException; }
    interface PrefixCheck { void verify(RecordingLibrary.Session prefix) throws IOException; }
    private final RecorderWire.Peer peer;
    private final RecordingClient.Link link;
    private final DirectorySync syncDirectory;
    private final PrefixCheck checkPrefix;
    private boolean subscribed;

    DurableConsume(RecorderWire.Peer peer,RecordingClient.Link link) {
        this(peer,link,directory->{
            try(FileChannel f=FileChannel.open(directory,StandardOpenOption.READ)){f.force(true);}
            catch(UnsupportedOperationException|SecurityException e){throw new IOException("cannot safely save recording directory",e);}
        },
            prefix->NativeAudio.inspectPrefix(prefix));
    }
    DurableConsume(RecorderWire.Peer peer,RecordingClient.Link link,DirectorySync sync,PrefixCheck check) {
        this.peer=peer;this.link=link;this.syncDirectory=sync;this.checkPrefix=check;
    }
    private static Path pending(Path directory){return directory.resolve(".consume-pending");}
    private static Path confirmed(Path directory,RecorderWire.Descriptor d){return directory.resolve(SegmentReceiver.key(d)+".receipt");}
    private static boolean regular(Path path){return Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS);}
    private static void forceFile(Path path)throws IOException {
        if(!regular(path))throw new IOException("saved recording file is unavailable; device copy retained");
        try(FileChannel channel=FileChannel.open(path,StandardOpenOption.WRITE)){channel.force(true);}
    }
    private void ready(Path directory,RecorderWire.Descriptor d)throws IOException {
        peer.validate(d);
        RecordingLibrary.Session prefix=RecordingLibrary.verifiedPrefix(directory,d);
        checkPrefix.verify(prefix);
        for(RecordingLibrary.Entry entry:prefix.segments){
            forceFile(entry.file);
            forceFile(directory.resolve(SegmentReceiver.key(entry.descriptor)+".meta"));
        }
        syncDirectory.sync(directory);
        Path parent=directory.toAbsolutePath().getParent();
        if(parent==null)throw new IOException("recording directory has no durable parent");
        syncDirectory.sync(parent);
    }
    private void writeNew(Path directory,Path target,byte[] data)throws IOException {
        Path temp=directory.resolve(".consume-"+UUID.randomUUID()+".tmp");
        Files.createFile(temp);
        try {
            try(RandomAccessFile f=new RandomAccessFile(temp.toFile(),"rw")){f.write(data);f.getFD().sync();}
            if(Files.exists(target,LinkOption.NOFOLLOW_LINKS))throw new IOException("recording receipt already exists");
            Files.move(temp,target,StandardCopyOption.ATOMIC_MOVE);
            syncDirectory.sync(directory);
        } finally {Files.deleteIfExists(temp);}
    }
    private FileLock lock(FileChannel channel)throws IOException {
        try {FileLock lock=channel.tryLock();if(lock==null)throw new IOException("another recording sync is in progress");return lock;}
        catch(OverlappingFileLockException e){throw new IOException("another recording sync is in progress",e);}
    }
    private boolean hasConfirmation(Path directory,RecorderWire.Descriptor d)throws IOException {
        Path file=confirmed(directory,d);if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))return false;
        if(!regular(file)||Files.size(file)!=84||!peer.receiptMatches(d,Files.readAllBytes(file)))throw new IOException("saved recording confirmation is invalid; originals retained");
        return true;
    }
    static long receiptTimeoutMillis(long length) {
        long sectors=(length+4095)/4096+2;
        return Math.min(240_000,Math.max(15_000,5_000+sectors*50));
    }
    private void send(Path directory,RecorderWire.Descriptor d)throws IOException {
        byte[] request=peer.consumeReceipt(d);
        if(!subscribed){link.subscribe(RecordingClient.RECORDING_CONSUME);subscribed=true;}
        link.write(RecordingClient.RECORDING_CONSUME,request);
        long deadline=System.nanoTime()+receiptTimeoutMillis(d.encodedLength)*1_000_000L;
        while(true){
            long remaining=(deadline-System.nanoTime())/1_000_000L;
            if(remaining<=0)throw new IOException("device confirmation pending; local recording retained");
            byte[] reply=link.await(RecordingClient.RECORDING_CONSUME,remaining);
            if(peer.receiptMatches(d,reply))break;
            if(reply!=null&&reply.length==16&&Arrays.equals(Arrays.copyOf(reply,8),new byte[]{'C','A','E','2',2,0,16,0})) {
                long id=(reply[8]&255L)|((reply[9]&255L)<<8)|((reply[10]&255L)<<16)|((reply[11]&255L)<<24);
                if(id==d.recordingId)throw new IOException("device did not confirm recording consumption; local recording retained");
            }
        }
        writeNew(directory,confirmed(directory,d),request);
    }
    private boolean reconcile(Path directory)throws IOException {
        Path file=pending(directory);if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))return false;
        if(!regular(file)||Files.size(file)!=112)throw new IOException("pending recording confirmation is invalid; originals retained");
        RecorderWire.Descriptor d=RecorderWire.Descriptor.decode(Files.readAllBytes(file));
        ready(directory,d);
        if(!hasConfirmation(directory,d))send(directory,d);
        Files.delete(file);syncDirectory.sync(directory);return true;
    }
    /** Resolve a lost reply before any later segment can be consumed. */
    boolean reconcilePending(Path directory)throws IOException {
        Files.createDirectories(directory);
        try(RandomAccessFile f=new RandomAccessFile(directory.resolve(".consume-lock").toFile(),"rw");
            FileChannel channel=f.getChannel();FileLock ignored=lock(channel)) {return reconcile(directory);}
    }
    /** True only when a new exact device receipt was confirmed in this call. */
    boolean consume(Path directory,RecorderWire.Descriptor d)throws IOException {
        Files.createDirectories(directory);
        try(RandomAccessFile f=new RandomAccessFile(directory.resolve(".consume-lock").toFile(),"rw");
            FileChannel channel=f.getChannel();FileLock ignored=lock(channel)) {
            boolean hadPending=Files.exists(pending(directory),LinkOption.NOFOLLOW_LINKS);
            if(hadPending&&(!regular(pending(directory))||Files.size(pending(directory))!=112))
                throw new IOException("pending recording confirmation is invalid; originals retained");
            RecorderWire.Descriptor prior=hadPending?RecorderWire.Descriptor.decode(Files.readAllBytes(pending(directory))):null;
            reconcile(directory);
            if(hadPending&&prior.sameContent(d))return true;
            ready(directory,d);
            if(hasConfirmation(directory,d))return false;
            writeNew(directory,pending(directory),d.wireBytes());
            send(directory,d);
            Files.delete(pending(directory));syncDirectory.sync(directory);return true;
        }
    }
}
