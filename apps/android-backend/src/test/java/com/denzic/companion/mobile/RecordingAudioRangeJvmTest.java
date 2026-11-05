package com.denzic.companion.mobile;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

public final class RecordingAudioRangeJvmTest {
    public static void main(String[] args)throws Exception {
        Path root=Paths.get(args[0]).toAbsolutePath();Files.createDirectories(root);
        Path a=root.resolve("part-a.wav"),b=root.resolve("part-b.wav"),cache=root.resolve("private-temp");
        byte[] first=wav(32000,(byte)1),second=wav(32000,(byte)2);
        Files.write(a,first);Files.write(b,second);
        List<NativeAudio.Part> list=Arrays.asList(new NativeAudio.Part(a,0,32000),new NativeAudio.Part(b,32000,32000));
        NativeAudio.PartsResult parts=new NativeAudio.PartsResult(root,64000,true,list,Collections.emptyList(),new byte[32]);
        final Path[] selected=new Path[1];
        RecordingAudioRange.Result<String> result=RecordingAudioRange.withValidatedParts(parts,cache,1500,2500,path->{
            selected[0]=path;byte[] clip=Files.readAllBytes(path);
            if(clip.length!=32044)throw new AssertionError("selected duration");
            for(int i=44;i<16044;i++)if(clip[i]!=1)throw new AssertionError("first part");
            for(int i=16044;i<32044;i++)if(clip[i]!=2)throw new AssertionError("second part");
            return "selected-only";
        });
        if(!"selected-only".equals(result.value)||result.retainedTemporary!=null||Files.exists(selected[0]))throw new AssertionError("success cleanup");
        if(!Arrays.equals(first,Files.readAllBytes(a))||!Arrays.equals(second,Files.readAllBytes(b)))throw new AssertionError("source changed");
        try {RecordingAudioRange.withValidatedParts(parts,cache,200,300,path->{throw new IOException("synthetic failure");});throw new AssertionError("missing failure");}
        catch(IOException expected){if(!"synthetic failure".equals(expected.getMessage()))throw expected;}
        try(java.util.stream.Stream<Path> pending=Files.list(cache)){if(pending.findAny().isPresent())throw new AssertionError("failure left temporary");}
        try {RecordingAudioRange.withValidatedParts(parts,cache,3999,4001,path->"unexpected");throw new AssertionError("invalid range");}
        catch(IOException expected){}
        if(!Arrays.equals(first,Files.readAllBytes(a))||!Arrays.equals(second,Files.readAllBytes(b)))throw new AssertionError("source changed");
        System.out.println("PASS Android backend selects the exact cross-part range and cleans private temporary on success and failure");
    }
    private static byte[] wav(int samples,byte value)throws IOException {
        byte[] header=DecodedAudioParts.expectedHeader(samples),out=Arrays.copyOf(header,header.length+samples*2);
        Arrays.fill(out,44,out.length,value);return out;
    }
}
