package com.denzic.companion.mobile;

import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.DigestInputStream;
import java.security.DigestOutputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/** Private complete-set receipt. It never deletes the original recording. */
final class DecodedAudioParts {
    private static final int MAGIC=0x43415031;
    private static final String RECEIPT=".companion-parts";
    private DecodedAudioParts(){}
    private static MessageDigest digest(){try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}}
    private static Path path(Path directory,int index){return directory.resolve(String.format(Locale.ROOT,"part-%08d.wav",index));}
    static byte[] expectedHeader(long samples)throws IOException {
        if(samples<=0||samples>57_600_000L)throw new IOException("invalid audio part duration");
        int size=(int)(samples*2);ByteBuffer b=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);
        b.put(new byte[]{'R','I','F','F'}).putInt(size+36).put(new byte[]{'W','A','V','E','f','m','t',' '});
        b.putInt(16).putShort((short)1).putShort((short)1).putInt(16000).putInt(32000).putShort((short)2).putShort((short)16);
        b.put(new byte[]{'d','a','t','a'}).putInt(size);return b.array();
    }
    private static byte[] partHash(Path file,long samples)throws IOException {
        if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)||Files.size(file)!=44+samples*2)throw new IOException("audio part missing or changed; original retained");
        MessageDigest hash=digest();byte[] header=new byte[44],buffer=new byte[64*1024];
        try(InputStream stream=new BufferedInputStream(Files.newInputStream(file));DataInputStream in=new DataInputStream(stream)) {
            in.readFully(header);if(!Arrays.equals(header,expectedHeader(samples)))throw new IOException("audio part format changed; original retained");
            hash.update(header);for(int n;(n=in.read(buffer))!=-1;)hash.update(buffer,0,n);
        }
        return hash.digest();
    }
    static void save(NativeAudio.PartsResult result)throws IOException {
        if(result.sourceFingerprint.length!=32||result.parts.isEmpty())throw new IOException("invalid audio parts");
        List<byte[]> hashes=new ArrayList<>();long total=0;
        for(int i=0;i<result.parts.size();i++) {
            NativeAudio.Part part=result.parts.get(i);
            if(!path(result.directory,i).equals(part.path)||part.firstSample!=total||total>Long.MAX_VALUE-part.samples)throw new IOException("invalid audio part order");
            hashes.add(partHash(part.path,part.samples));total+=part.samples;
        }
        if(total!=result.samples)throw new IOException("audio parts do not cover recording");
        Path temp=Files.createTempFile(result.directory,".parts-receipt-",".tmp");
        try {
            MessageDigest hash=digest();
            try(FileOutputStream file=new FileOutputStream(temp.toFile());DigestOutputStream checked=new DigestOutputStream(file,hash);DataOutputStream out=new DataOutputStream(checked)) {
                out.writeInt(MAGIC);out.write(result.sourceFingerprint);out.writeLong(result.samples);out.writeBoolean(result.captureComplete);out.writeInt(result.parts.size());
                for(int i=0;i<result.parts.size();i++){out.writeLong(result.parts.get(i).samples);out.write(hashes.get(i));}
                out.writeInt(result.bookmarks.size());
                for(NativeAudio.Bookmark mark:result.bookmarks){out.writeLong(mark.sequence);out.writeLong(mark.sourceSamples);out.writeLong(mark.playbackSamples);out.writeLong(mark.elapsedMillis);}
                out.flush();byte[] checksum=hash.digest();checked.on(false);out.write(checksum);out.flush();file.getFD().sync();
            }
            Files.move(temp,result.directory.resolve(RECEIPT),StandardCopyOption.ATOMIC_MOVE);
        } finally {Files.deleteIfExists(temp);}
    }
    static NativeAudio.PartsResult load(Path directory,byte[] fingerprint)throws IOException {
        Path receipt=directory.resolve(RECEIPT);if(!Files.exists(receipt))return null;
        if(!Files.isRegularFile(receipt,LinkOption.NOFOLLOW_LINKS))throw new IOException("audio parts receipt unavailable");
        long size=Files.size(receipt);if(size<85)throw new IOException("audio parts receipt damaged");
        MessageDigest hash=digest();List<Long> sizes=new ArrayList<>();List<byte[]> hashes=new ArrayList<>();List<NativeAudio.Bookmark> marks=new ArrayList<>();long total;boolean complete;
        try(DigestInputStream checked=new DigestInputStream(new BufferedInputStream(Files.newInputStream(receipt)),hash);DataInputStream in=new DataInputStream(checked)) {
            if(in.readInt()!=MAGIC)throw new IOException("unsupported audio parts receipt");
            byte[] saved=new byte[32];in.readFully(saved);if(!MessageDigest.isEqual(saved,fingerprint))return null;
            total=in.readLong();complete=in.readBoolean();int count=in.readInt();
            if(total<=0||count<=0||count>(size-85)/40)throw new IOException("audio parts receipt damaged");
            long sum=0;
            for(int i=0;i<count;i++) {
                long samples=in.readLong();if(samples<=0||samples>57_600_000L||sum>Long.MAX_VALUE-samples)throw new IOException("invalid audio part duration");
                byte[] partHash=new byte[32];in.readFully(partHash);sizes.add(samples);hashes.add(partHash);sum+=samples;
            }
            if(sum!=total)throw new IOException("audio parts do not cover recording");
            int markCount=in.readInt();
            if(markCount<0||markCount>(size-85-40L*count)/32||size!=85+40L*count+32L*markCount)throw new IOException("audio parts receipt damaged");
            for(int i=0;i<markCount;i++) {
                long sequence=in.readLong(),source=in.readLong(),playback=in.readLong(),elapsed=in.readLong();
                if(sequence<=0||source<0||playback<0||playback>total||elapsed<0)throw new IOException("invalid audio bookmark");
                marks.add(new NativeAudio.Bookmark(sequence,source,playback,elapsed));
            }
            byte[] actual=hash.digest();checked.on(false);byte[] expected=new byte[32];in.readFully(expected);
            if(!MessageDigest.isEqual(actual,expected)||in.read()!=-1)throw new IOException("audio parts receipt damaged");
        }
        List<NativeAudio.Part> parts=new ArrayList<>();long offset=0;
        for(int i=0;i<sizes.size();i++) {
            long samples=sizes.get(i);Path file=path(directory,i);
            if(!MessageDigest.isEqual(partHash(file,samples),hashes.get(i)))throw new IOException("audio part changed; original retained");
            parts.add(new NativeAudio.Part(file,offset,samples));offset+=samples;
        }
        return new NativeAudio.PartsResult(directory,total,complete,parts,marks,fingerprint);
    }
}
