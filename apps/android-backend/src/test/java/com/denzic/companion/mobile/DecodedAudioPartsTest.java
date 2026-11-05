package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.Collections;

/** Receipt protects a completed multi-WAV recording without modifying originals. */
public final class DecodedAudioPartsTest {
    private interface Checked{void run()throws Exception;}
    private static void fails(Checked action)throws Exception{try{action.run();throw new AssertionError("expected failure");}catch(IOException expected){}}
    private static void check(boolean value,String reason){if(!value)throw new AssertionError(reason);}
    private static void wav(Path path,int samples)throws IOException {
        int size=samples*2;ByteBuffer b=ByteBuffer.allocate(44+size).order(ByteOrder.LITTLE_ENDIAN);
        b.put(new byte[]{'R','I','F','F'}).putInt(size+36).put(new byte[]{'W','A','V','E','f','m','t',' '});
        b.putInt(16).putShort((short)1).putShort((short)1).putInt(16000).putInt(32000).putShort((short)2).putShort((short)16);
        b.put(new byte[]{'d','a','t','a'}).putInt(size);for(int i=0;i<samples;i++)b.putShort((short)(i+1));Files.write(path,b.array());
    }
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory(Paths.get(args[0]),"audio-parts-receipt-");Path dir=root.resolve("parts");Files.createDirectory(dir);
        Path first=dir.resolve("part-00000000.wav"),second=dir.resolve("part-00000001.wav");wav(first,10);wav(second,7);
        byte[] source=new byte[32];source[0]=42;
        NativeAudio.PartsResult result=new NativeAudio.PartsResult(dir,17,true,Arrays.asList(new NativeAudio.Part(first,0,10),new NativeAudio.Part(second,10,7)),
            Collections.singletonList(new NativeAudio.Bookmark(1,14,11,220)),source);
        DecodedAudioParts.save(result);NativeAudio.PartsResult reopened=DecodedAudioParts.load(dir,source);
        check(reopened!=null&&reopened.samples==17&&reopened.captureComplete&&reopened.parts.size()==2&&reopened.parts.get(1).firstSample==10,"reopen failed");
        check(reopened.bookmarks.size()==1&&reopened.bookmarks.get(0).playbackSamples==11,"bookmark moved");
        byte[] other=source.clone();other[0]++;check(DecodedAudioParts.load(dir,other)==null,"wrong source accepted");
        byte[] original=Files.readAllBytes(second),changed=original.clone();changed[45]^=1;Files.write(second,changed);
        fails(()->DecodedAudioParts.load(dir,source));check(Arrays.equals(Files.readAllBytes(second),changed),"changed audio overwritten");
        Files.write(second,original);check(DecodedAudioParts.load(dir,source)!=null,"restored audio unavailable");
        Path receipt=dir.resolve(".companion-parts");byte[] saved=Files.readAllBytes(receipt);saved[48]^=1;Files.write(receipt,saved);
        fails(()->DecodedAudioParts.load(dir,source));check(Arrays.equals(Files.readAllBytes(second),original),"receipt damage modified audio");
        Path partial=root.resolve("partial");Files.createDirectory(partial);wav(partial.resolve("part-00000000.wav"),3);
        check(DecodedAudioParts.load(partial,source)==null,"unfinished output was exposed as complete");
        System.out.println("PASS ordered parts, source binding, restart and damaged-file handling");
    }
}
