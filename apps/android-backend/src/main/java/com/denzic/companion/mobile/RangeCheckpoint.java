package com.denzic.companion.mobile;

import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.UUID;
import java.util.zip.CRC32;

/** Durable partial-source handoff for the range-reclaim refactor.
 * Kept behind the future negotiated range protocol: this class sends no BLE
 * command and cannot make an ordinary download destructive. The receiver's
 * existing exact-descriptor file lock must remain held during save/confirm. */
final class RangeCheckpoint {
    interface DirectorySync {void sync(Path directory)throws IOException;}
    private static final int BYTES=216;
    final RecorderWire.Descriptor descriptor;
    final long nonce,prefixBytes;
    final int firstSector,endSector;
    final boolean confirmed;
    private final byte[] prefixSha,rangeSha;

    private RangeCheckpoint(RecorderWire.Descriptor d,long nonce,int first,int end,
            long prefixBytes,byte[] prefixSha,byte[] rangeSha,boolean confirmed)throws IOException {
        if(d==null||nonce<=0||nonce>0xffffffffL||first<0||end<=first||end>65535)
            throw invalid();
        long usedSectors=(((d.encodedLength+247)/248+1)*256+4095)/4096;
        long expectedEnd=Math.min(d.encodedLength,((long)end*16-1)*248);
        if(end>usedSectors||Math.max(0,((long)first*16-1)*248)>=d.encodedLength||prefixBytes!=expectedEnd||
                prefixSha.length!=32||rangeSha.length!=32)throw invalid();
        descriptor=d;this.nonce=nonce;firstSector=first;endSector=end;this.prefixBytes=prefixBytes;
        this.prefixSha=prefixSha.clone();this.rangeSha=rangeSha.clone();this.confirmed=confirmed;
    }
    byte[] rangeSha(){return rangeSha.clone();}
    private static IOException invalid(){return new IOException("recording range checkpoint is invalid; saved source retained");}
    private static Path path(Path dir,RecorderWire.Descriptor d){return dir.resolve(SegmentReceiver.key(d)+".range");}
    private static boolean exists(Path p){return Files.exists(p,LinkOption.NOFOLLOW_LINKS);}
    static boolean exists(Path dir,RecorderWire.Descriptor d){return exists(path(dir,d));}
    private static long get(byte[] p,int at,int n){long v=0;for(int i=0;i<n;i++)v|=(p[at+i]&255L)<<(i*8);return v;}
    private static void put(byte[] p,int at,long v,int n){for(int i=0;i<n;i++)p[at+i]=(byte)(v>>>(i*8));}
    private static long crc(byte[] p,int n){CRC32 c=new CRC32();c.update(p,0,n);return c.getValue();}
    private static MessageDigest sha(){try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}}
    private byte[] encode(){
        byte[] p=new byte[BYTES];System.arraycopy(new byte[]{'C','R','H','1',1,0,(byte)BYTES,0},0,p,0,8);
        p[5]=(byte)(confirmed?1:0);put(p,8,nonce,4);put(p,12,firstSector,2);put(p,14,endSector,2);
        put(p,16,prefixBytes,8);System.arraycopy(prefixSha,0,p,24,32);System.arraycopy(rangeSha,0,p,56,32);
        System.arraycopy(descriptor.wireBytes(),0,p,88,112);put(p,200,descriptor.startedUnixSeconds,4);
        put(p,208,crc(p,208),4);System.arraycopy(new byte[]{'C','R','G','E'},0,p,212,4);return p;
    }
    static RangeCheckpoint read(Path dir,RecorderWire.Descriptor expected)throws IOException {
        Path file=path(dir,expected);
        if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)||Files.size(file)!=BYTES)throw invalid();
        byte[] p=Files.readAllBytes(file);
        if(!Arrays.equals(Arrays.copyOf(p,5),new byte[]{'C','R','H','1',1})||p[5]<0||p[5]>1||
                get(p,6,2)!=BYTES||get(p,204,4)!=0||get(p,208,4)!=crc(p,208)||
                !Arrays.equals(Arrays.copyOfRange(p,212,216),new byte[]{'C','R','G','E'}))throw invalid();
        byte[] meta=Arrays.copyOfRange(p,88,200);
        long date=get(p,200,4);
        if(date!=0){meta=Arrays.copyOf(meta,120);put(meta,112,date,4);put(meta,116,crc(meta,116),4);}
        RecorderWire.Descriptor actual=RecorderWire.Descriptor.decode(meta);
        if(!actual.sameContent(expected)||(actual.startedUnixSeconds!=0&&expected.startedUnixSeconds!=0&&
                actual.startedUnixSeconds!=expected.startedUnixSeconds))throw invalid();
        return new RangeCheckpoint(actual,get(p,8,4),(int)get(p,12,2),(int)get(p,14,2),get(p,16,8),
                Arrays.copyOfRange(p,24,56),Arrays.copyOfRange(p,56,88),p[5]==1);
    }
    private static Path source(Path dir,RecorderWire.Descriptor d)throws IOException {
        Path complete=dir.resolve(SegmentReceiver.key(d)+".cop1"),part=dir.resolve(SegmentReceiver.key(d)+".part");
        if(exists(complete)&&exists(part))throw new IOException("recording range has conflicting local sources; both retained");
        Path file=exists(complete)?complete:part;
        if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS))throw new IOException("saved recording prefix is missing; range recovery cannot restart from zero");
        return file;
    }
    /** Revalidate the exact saved prefix before allowing a resumed PULL. A
     * damaged prefix must never trigger the legacy discard-and-start-over path:
     * some of its device sectors may already have been physically reclaimed. */
    static void verifySavedPrefix(Path dir,RecorderWire.Descriptor d)throws IOException {
        if(!exists(dir,d))return;
        RangeCheckpoint c=read(dir,d);byte[][] hashes=hashes(source(dir,d),d,c.firstSector,
            Math.min(d.encodedLength,((long)c.endSector*16-1)*248),c.prefixBytes);
        if(!MessageDigest.isEqual(c.prefixSha,hashes[0])||!MessageDigest.isEqual(c.rangeSha,hashes[1]))
            throw new IOException("saved recording prefix is damaged; range recovery cannot restart from zero");
    }
    private static byte[][] hashes(Path file,RecorderWire.Descriptor d,int first,long rangeEnd,long end)throws IOException {
        long begin=Math.max(0,((long)first*16-1)*248);
        MessageDigest prefix=sha(),range=sha();byte[] buffer=new byte[32768];
        try(RandomAccessFile f=new RandomAccessFile(file.toFile(),"r")){
            if(f.length()<end||f.length()>d.encodedLength)throw new IOException("saved recording prefix length changed; source retained");
            long at=0;
            while(at<end){
                int n=f.read(buffer,0,(int)Math.min(buffer.length,end-at));if(n<0)throw invalid();
                prefix.update(buffer,0,n);
                int start=(int)Math.max(0,Math.min(n,begin-at));
                int stop=(int)Math.max(start,Math.min(n,rangeEnd-at));
                if(start<stop)range.update(buffer,start,stop-start);
                at+=n;
            }
        }
        return new byte[][]{prefix.digest(),range.digest()};
    }
    private static void force(Path file)throws IOException {
        if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS))throw invalid();
        try(FileChannel c=FileChannel.open(file,StandardOpenOption.WRITE)){c.force(true);}
    }
    private void publish(Path dir,DirectorySync sync)throws IOException {
        Path temp=dir.resolve(".range-"+UUID.randomUUID()+".tmp");
        Files.createFile(temp);
        try {
            try(RandomAccessFile f=new RandomAccessFile(temp.toFile(),"rw")){f.write(encode());f.getFD().sync();}
            Files.move(temp,path(dir,descriptor),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            sync.sync(dir);
        }finally{Files.deleteIfExists(temp);}
    }
    static RangeCheckpoint save(Path dir,RecorderWire.Descriptor d,int first,int end,long nonce,DirectorySync sync)throws IOException {
        return save(dir,d,first,end,nonce,sync,0,null,false);
    }
    static RangeCheckpoint saveOwned(Path dir,RecorderWire.Descriptor d,int first,int end,long nonce,
            DirectorySync sync,long acceptedBytes,byte[] acceptedSha)throws IOException {
        return save(dir,d,first,end,nonce,sync,acceptedBytes,acceptedSha,true);
    }
    private static RangeCheckpoint save(Path dir,RecorderWire.Descriptor d,int first,int end,long nonce,
            DirectorySync sync,long acceptedBytes,byte[] acceptedSha,boolean owned)throws IOException {
        if(sync==null)throw new IllegalArgumentException("directory sync required");
        long limit=Math.min(d.encodedLength,((long)end*16-1)*248);
        // Validate the proposed bounds before opening source or replacing proof.
        new RangeCheckpoint(d,nonce,first,end,limit,new byte[32],new byte[32],false);
        if(exists(dir,d)){
            RangeCheckpoint previous=read(dir,d);
            if(!owned)verifySavedPrefix(dir,d);
            if(!previous.confirmed){
                if(previous.nonce==nonce&&previous.firstSector==first&&previous.endSector==end){
                    // The prior atomic rename may have succeeded immediately
                    // before directory sync failed. A retry must establish
                    // durability again before returning a sendable proof.
                    force(source(dir,d));force(dir.resolve(SegmentReceiver.key(d)+".meta"));
                    force(path(dir,d));sync.sync(dir);
                    Path parent=dir.toAbsolutePath().getParent();if(parent==null)throw invalid();sync.sync(parent);
                    return previous;
                }
                throw new IOException("a recording range confirmation is still pending; saved proof retained");
            }
            if(first!=previous.endSector||nonce==previous.nonce)throw new IOException("recording range frontier is not contiguous");
        }else if(first!=0)throw new IOException("recording range frontier must start at the first sector");
        Path file=source(dir,d),meta=dir.resolve(SegmentReceiver.key(d)+".meta");
        RecorderWire.Descriptor saved=RecorderWire.Descriptor.decode(Files.readAllBytes(meta));
        if(!saved.sameContent(d)||(saved.startedUnixSeconds!=0&&d.startedUnixSeconds!=0&&
                saved.startedUnixSeconds!=d.startedUnixSeconds))throw invalid();
        long prefix=owned?acceptedBytes:limit;
        byte[][] hashes;
        if(acceptedSha!=null){
            // The live receiver's incremental SHA already covers every byte
            // under this same file lock. Read only the newly handed-off range,
            // rather than rehashing the entire growing prefix for every4K.
            MessageDigest range=sha();byte[] buffer=new byte[32768];
            try(RandomAccessFile f=new RandomAccessFile(file.toFile(),"r")){
                long begin=Math.max(0,((long)first*16-1)*248);
                if(prefix<limit||prefix>f.length()||f.length()>d.encodedLength)throw invalid();
                f.seek(begin);long left=limit-begin;
                while(left>0){int n=f.read(buffer,0,(int)Math.min(buffer.length,left));if(n<0)throw invalid();range.update(buffer,0,n);left-=n;}
            }
            hashes=new byte[][]{acceptedSha,range.digest()};
        }else hashes=hashes(file,d,first,limit,prefix);
        force(file);force(meta);sync.sync(dir);
        Path parent=dir.toAbsolutePath().getParent();if(parent==null)throw invalid();sync.sync(parent);
        RangeCheckpoint result=new RangeCheckpoint(saved,nonce,first,end,prefix,hashes[0],hashes[1],false);
        result.publish(dir,sync);return result;
    }
    /** Caller invokes this ONLY for an exact device physical-DONE receipt. */
    void confirm(Path dir,DirectorySync sync)throws IOException {
        confirm(dir,sync,false);
    }
    void confirmOwned(Path dir,DirectorySync sync)throws IOException {confirm(dir,sync,true);}
    private void confirm(Path dir,DirectorySync sync,boolean owned)throws IOException {
        RangeCheckpoint current=read(dir,descriptor);
        if(current.nonce!=nonce||current.firstSector!=firstSector||current.endSector!=endSector||
                !MessageDigest.isEqual(current.rangeSha,rangeSha)||!MessageDigest.isEqual(current.prefixSha,prefixSha))throw invalid();
        if(!owned)verifySavedPrefix(dir,descriptor);
        if(!current.confirmed)new RangeCheckpoint(descriptor,nonce,firstSector,endSector,prefixBytes,prefixSha,rangeSha,true).publish(dir,sync);
    }
}
