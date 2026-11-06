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
        this(peer,link,AndroidDirectorySync::sync,
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
    private static FileLock lock(FileChannel channel)throws IOException {
        try {FileLock lock=channel.tryLock();if(lock==null)throw new IOException("another recording sync is in progress");return lock;}
        catch(OverlappingFileLockException e){throw new IOException("another recording sync is in progress",e);}
    }
    /** Save an unresolved receipt aside only by explicit host action; no device command is sent. */
    static String defer(Path directory,RecorderWire.Descriptor expected,DirectorySync sync)throws IOException {
        if(directory==null||expected==null)throw new IllegalArgumentException("directory and pending recording required");
        Files.createDirectories(directory);
        try(RandomAccessFile f=new RandomAccessFile(directory.resolve(".consume-lock").toFile(),"rw");
            FileChannel channel=f.getChannel();FileLock ignored=lock(channel)) {
            Path source=pending(directory);
            if(!regular(source)||Files.size(source)!=112)throw new IOException("没有可暂缓的设备确认，已保存的录音保留");
            RecorderWire.Descriptor actual=RecorderWire.Descriptor.decode(Files.readAllBytes(source));
            if(!actual.sameContent(expected))throw new IOException("待确认录音已变化，请刷新后重试");
            // Deferral only moves the saved descriptor; it never acknowledges
            // or deletes device data. Even a damaged/missing local recording
            // must not prevent reception of unrelated sessions. Validation is
            // still mandatory before restoring and sending this receipt.
            return movePendingAside(directory,source,".consume-deferred-",sync);
        }
    }
    /** Preserve an unreadable pending record without claiming an identity or touching the device. */
    static String deferUnreadable(Path directory,DirectorySync sync)throws IOException {
        if(directory==null)throw new IllegalArgumentException("directory required");
        Files.createDirectories(directory);
        try(RandomAccessFile f=new RandomAccessFile(directory.resolve(".consume-lock").toFile(),"rw");
            FileChannel channel=f.getChannel();FileLock ignored=lock(channel)) {
            Path source=pending(directory);
            if(!regular(source))throw new IOException("没有可暂缓的损坏确认记录");
            boolean valid=false;
            if(Files.size(source)==112) {
                byte[] content=Files.readAllBytes(source);
                try {RecorderWire.Descriptor.decode(content);valid=true;}
                catch(IOException damaged) { /* Preserve the original bytes for diagnosis. */ }
            }
            if(valid)throw new IOException("该确认记录可读取，请使用普通暂缓操作");
            return movePendingAside(directory,source,".consume-unreadable-",sync);
        }
    }
    private static String movePendingAside(Path directory,Path source,String prefix,DirectorySync sync)throws IOException {
        String token;Path destination;
        do {token=prefix+UUID.randomUUID()+".pending";destination=directory.resolve(token);}
        while(Files.exists(destination,LinkOption.NOFOLLOW_LINKS));
        Files.move(source,destination,StandardCopyOption.ATOMIC_MOVE);
        sync.sync(directory);
        return token;
    }
    /** Restore one explicitly chosen deferred receipt before reconnecting to its original device. */
    static void restore(Path directory,String token,RecorderWire.Descriptor expected,DirectorySync sync)throws IOException {
        if(directory==null||expected==null||token==null||!token.matches("\\.consume-deferred-[0-9a-f-]{36}\\.pending"))
            throw new IllegalArgumentException("invalid deferred recording confirmation");
        Files.createDirectories(directory);
        try(RandomAccessFile f=new RandomAccessFile(directory.resolve(".consume-lock").toFile(),"rw");
            FileChannel channel=f.getChannel();FileLock ignored=lock(channel)) {
            Path source=directory.resolve(token),target=pending(directory);
            if(Files.exists(target,LinkOption.NOFOLLOW_LINKS))throw new IOException("已有另一项设备确认待处理，请先完成或暂缓");
            if(!regular(source)||Files.size(source)!=112)throw new IOException("暂缓的设备确认不可用，已保存的录音保留");
            RecorderWire.Descriptor actual=RecorderWire.Descriptor.decode(Files.readAllBytes(source));
            if(!actual.sameContent(expected))throw new IOException("暂缓的录音已变化，请刷新后重试");
            RecordingLibrary.verifiedPrefix(directory,actual);
            Files.move(source,target,StandardCopyOption.ATOMIC_MOVE);
            sync.sync(directory);
        }
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
    private byte[] request(RecorderWire.Descriptor d)throws IOException {
        byte[] request=peer.consumeReceipt(d);
        if(!subscribed){link.subscribe(RecordingClient.RECORDING_CONSUME);subscribed=true;}
        link.write(RecordingClient.RECORDING_CONSUME,request);
        return request;
    }
    private void awaitReceipt(Path directory,RecorderWire.Descriptor d,byte[] request)throws IOException {
        // A later sealed file may have been copied while this notification
        // queued. Bound the actual wait, including stale replies; never resend
        // or remove the durable pending proof merely because copying took time.
        long deadline=System.nanoTime()+receiptTimeoutMillis(d.encodedLength)*1_000_000L;
        while(true){
            long remaining=(deadline-System.nanoTime())/1_000_000L;
            if(remaining<=0)throw new java.net.SocketTimeoutException("device confirmation pending; local recording retained");
            byte[] reply=link.await(RecordingClient.RECORDING_CONSUME,remaining);
            if(peer.receiptMatches(d,reply))break;
            if(reply!=null&&reply.length==16&&Arrays.equals(Arrays.copyOf(reply,8),new byte[]{'C','A','E','2',2,0,16,0})) {
                long id=(reply[8]&255L)|((reply[9]&255L)<<8)|((reply[10]&255L)<<16)|((reply[11]&255L)<<24);
                if(id==d.recordingId)throw new IOException("device did not confirm recording consumption; local recording retained");
            }
        }
        writeNew(directory,confirmed(directory,d),request);
    }
    private void send(Path directory,RecorderWire.Descriptor d)throws IOException {
        awaitReceipt(directory,d,request(d));
    }
    private boolean reconcile(Path directory,RecorderWire.Descriptor selected)throws IOException {
        Path file=pending(directory);if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))return false;
        if(!regular(file)||Files.size(file)!=112)throw new IOException("pending recording confirmation is invalid; originals retained");
        RecorderWire.Descriptor d=RecorderWire.Descriptor.decode(Files.readAllBytes(file));
        if(!RecordingLibrary.sameSession(d,selected))
            throw new IOException("另一场录音的设备确认尚未完成，请先继续接收那场录音；已保存的录音均保留");
        ready(directory,d);
        if(!hasConfirmation(directory,d))send(directory,d);
        Files.delete(file);syncDirectory.sync(directory);return true;
    }
    /** Resolve a lost reply before any later segment can be consumed. */
    boolean reconcilePending(Path directory,RecorderWire.Descriptor selected)throws IOException {
        peer.validate(selected);
        Files.createDirectories(directory);
        try(RandomAccessFile f=new RandomAccessFile(directory.resolve(".consume-lock").toFile(),"rw");
            FileChannel channel=f.getChannel();FileLock ignored=lock(channel)) {return reconcile(directory,selected);}
    }
    /** Holds the same directory lock and durable pending proof across one
     * unrelated sealed download. Close on any error leaves that proof intact. */
    final class Pending implements java.io.Closeable {
        private final Path directory;private final RecorderWire.Descriptor descriptor;
        private final RandomAccessFile file;private final FileLock held;
        private byte[] wire;private boolean finished,closed;
        final boolean changed;
        Pending(Path directory,RecorderWire.Descriptor descriptor,RandomAccessFile file,FileLock held,boolean finished,boolean changed){
            this.directory=directory;this.descriptor=descriptor;this.file=file;this.held=held;this.finished=finished;this.changed=changed;
        }
        void finish()throws IOException {
            if(closed)throw new IOException("recording confirmation is closed");
            if(finished)return;
            awaitReceipt(directory,descriptor,wire);
            Files.delete(pending(directory));syncDirectory.sync(directory);finished=true;
        }
        @Override public void close()throws IOException {
            if(closed)return;closed=true;
            IOException problem=null;
            try{held.release();}catch(IOException e){problem=e;}
            try{file.close();}catch(IOException e){if(problem==null)problem=e;else problem.addSuppressed(e);}
            if(problem!=null)throw problem;
        }
    }
    Pending begin(Path directory,RecorderWire.Descriptor d)throws IOException {
        Files.createDirectories(directory);
        RandomAccessFile f=new RandomAccessFile(directory.resolve(".consume-lock").toFile(),"rw");
        try {
            FileLock held=lock(f.getChannel());
            boolean hadPending=Files.exists(pending(directory),LinkOption.NOFOLLOW_LINKS);
            if(hadPending&&(!regular(pending(directory))||Files.size(pending(directory))!=112))
                throw new IOException("pending recording confirmation is invalid; originals retained");
            RecorderWire.Descriptor prior=hadPending?RecorderWire.Descriptor.decode(Files.readAllBytes(pending(directory))):null;
            reconcile(directory,d);
            if(hadPending&&prior.sameContent(d))return new Pending(directory,d,f,held,true,true);
            ready(directory,d);
            if(hasConfirmation(directory,d))return new Pending(directory,d,f,held,true,false);
            writeNew(directory,pending(directory),d.wireBytes());
            Pending result=new Pending(directory,d,f,held,false,true);result.wire=request(d);return result;
        }catch(IOException|RuntimeException failure){try{f.close();}catch(IOException close){failure.addSuppressed(close);}throw failure;}
    }
    /** True only when a new exact device receipt was confirmed in this call. */
    boolean consume(Path directory,RecorderWire.Descriptor d)throws IOException {
        try(Pending result=begin(directory,d)){result.finish();return result.changed;}
    }
}
