package com.denzic.companion.mobile;
import java.nio.file.*;
import java.util.*;
import java.io.IOException;
/** Exact production callback with actual newly captured dated metadata; no JNI
 * load, Bluetooth, original audio payload or application-private mutation. */
public final class NativeControlMetadataTest {
    public static void main(String[] args)throws Exception{
        byte[] original=Files.readAllBytes(Paths.get(args[0]));if(original.length!=120)throw new AssertionError("Expected actual dated test-session metadata");RecorderWire.Descriptor date=RecorderWire.Descriptor.decode(original);Path root=Paths.get(args[1]);Files.createDirectories(root);
        for(int bytes:new int[]{112,120}){Path dir=Files.createDirectory(root.resolve("valid"+bytes));String key=SegmentReceiver.key(date);Files.write(dir.resolve(key+".meta"),Arrays.copyOf(original,bytes));Files.write(dir.resolve(key+".cop1"),new byte[]{1});String[] found=new NativeRecordingControl.Callbacks(null,null,dir).localFiles();if(found.length!=1||!found[0].endsWith(key+".cop1"))throw new AssertionError("Valid original rejected");}
        Path corrupt=Files.createDirectory(root.resolve("corrupt"));byte[] bad=original.clone();bad[112]^=1;Files.write(corrupt.resolve(SegmentReceiver.key(date)+".meta"),bad);boolean rejected=false;try{new NativeRecordingControl.Callbacks(null,null,corrupt).localFiles();}catch(IOException expected){rejected=true;}if(!rejected)throw new AssertionError("Changed date CRC accepted");
        if(!Arrays.equals(original,Files.readAllBytes(Paths.get(args[0]))))throw new AssertionError("Original fixture changed");System.out.println("PASS exact actual dated120B and legacy112B metadata callback; corrupt CRC refused, original retained; NO_BLUETOOTH_OR_AUDIO_DECODE");
    }
}
