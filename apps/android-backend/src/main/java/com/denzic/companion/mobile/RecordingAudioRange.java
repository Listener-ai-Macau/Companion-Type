package com.denzic.companion.mobile;

import java.io.IOException;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.Arrays;

/**
 * An explicitly selected range of a verified recording, for use with either
 * local transcription or the host's chosen cloud provider. Run on a worker.
 */
public final class RecordingAudioRange {
    private RecordingAudioRange() {}
    public interface Processor<T> { T process(Path temporaryWav) throws IOException; }
    public static final class Result<T> {
        public final T value;
        /** Non-null only if the app must retry deletion of this private temporary file. */
        public final Path retainedTemporary;
        Result(T value,Path retainedTemporary) { this.value=value;this.retainedTemporary=retainedTemporary; }
    }

    /**
     * The host must use an app-private temporary directory and call only after
     * the user selects the range and provider. Local processing stays offline;
     * a cloud processor sends the selected audio and may incur service charges.
     * Input is never modified. The selected temporary is removed on normal
     * completion or failure; a process crash may leave it in the private cache.
     */
    public static <T> Result<T> withRange(RecordingLibrary.Session session,Path partsDirectory,
            Path privateTemporaryDirectory,long startMs,long endMs,Processor<T> processor) throws IOException {
        if(session==null||partsDirectory==null||privateTemporaryDirectory==null||processor==null)
            throw new IllegalArgumentException("recording, parts, private temporary directory and processor required");
        NativeAudio.PartsResult parts=NativeAudio.loadParts(session,partsDirectory);
        if(parts==null)throw new IOException("complete audio parts are unavailable for this recording; original retained");
        return withValidatedParts(parts,privateTemporaryDirectory,startMs,endMs,processor);
    }

    static <T> Result<T> withValidatedParts(NativeAudio.PartsResult parts,Path privateTemporaryDirectory,
            long startMs,long endMs,Processor<T> processor) throws IOException {
        if(startMs<0||endMs<=startMs||parts.samples<=0)throw new IOException("invalid selected audio range; original retained");
        long start,end;
        try {start=Math.multiplyExact(startMs,16);end=Math.multiplyExact(endMs,16);}
        catch(ArithmeticException error){throw new IOException("selected audio range exceeds recording",error);}
        long maxMs=parts.samples/16+(parts.samples%16==0?0:1);
        if(start>=parts.samples||endMs>maxMs)throw new IOException("selected audio range exceeds recording");
        end=Math.min(end,parts.samples);
        long samples=end-start;
        if(samples>(0xffffffffL-36)/2)throw new IOException("selected range exceeds WAV format capacity; original retained");
        long bytes=samples*2;
        long cursor=0;
        for(NativeAudio.Part part:parts.parts) {
            if(part.firstSample!=cursor||part.samples<=0||cursor>Long.MAX_VALUE-part.samples)
                throw new IOException("audio parts do not cover the recording");
            cursor+=part.samples;
        }
        if(cursor!=parts.samples)throw new IOException("audio parts do not cover the recording");
        Path directory=privateTemporaryDirectory.toAbsolutePath();Files.createDirectories(directory);
        Path temporary=Files.createTempFile(directory,"companion-asr-range-", ".wav");
        try {
            writeRange(parts,temporary,start,end,bytes);
            T value=processor.process(temporary);
            try {Files.deleteIfExists(temporary);return new Result<>(value,null);}
            catch(IOException|SecurityException failure){return new Result<>(value,temporary);}
        } catch(IOException|RuntimeException|Error failure) {
            try {Files.deleteIfExists(temporary);}catch(IOException|SecurityException cleanup){failure.addSuppressed(cleanup);}
            throw failure;
        }
    }

    private static void writeRange(NativeAudio.PartsResult parts,Path target,long start,long end,long bytes)throws IOException {
        ByteBuffer h=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);
        h.put(new byte[]{'R','I','F','F'}).putInt((int)(36+bytes)).put(new byte[]{'W','A','V','E','f','m','t',' '})
            .putInt(16).putShort((short)1).putShort((short)1).putInt(16000).putInt(32000)
            .putShort((short)2).putShort((short)16).put(new byte[]{'d','a','t','a'}).putInt((int)bytes);
        byte[] buffer=new byte[64*1024],header=new byte[44];long written=0;
        try(OutputStream out=Files.newOutputStream(target)) {
            out.write(h.array());
            for(NativeAudio.Part part:parts.parts) {
                long lo=Math.max(start,part.firstSample),hi=Math.min(end,part.firstSample+part.samples);
                if(hi<=lo)continue;
                if(!Files.isRegularFile(part.path,LinkOption.NOFOLLOW_LINKS)||Files.size(part.path)!=44+part.samples*2)
                    throw new IOException("audio part missing or changed; original retained");
                try(RandomAccessFile input=new RandomAccessFile(part.path.toFile(),"r")) {
                    input.readFully(header);
                    if(!Arrays.equals(header,DecodedAudioParts.expectedHeader(part.samples)))
                        throw new IOException("audio part format changed; original retained");
                    input.seek(44+(lo-part.firstSample)*2);long left=(hi-lo)*2;
                    while(left>0){int n=(int)Math.min(left,buffer.length);input.readFully(buffer,0,n);out.write(buffer,0,n);left-=n;written+=n;}
                }
            }
        }
        if(written!=bytes)throw new IOException("selected audio range could not be read; original retained");
    }
}
