package com.denzic.companion.app;
import com.denzic.companion.mobile.LibraryBackup;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.JSONObject;
public final class PlaybackBackupCompatibilityTest {
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]),meet=root.resolve("meetings"),rec=root.resolve("recordings");Files.createDirectories(meet);Files.createDirectories(rec);
  byte[] original="EXPLICIT FICTIONAL METADATA BACKUP COMPATIBILITY ONLY".getBytes(StandardCharsets.UTF_8);Files.write(meet.resolve("original.txt"),original);
  String binding=new String(new char[64]).replace('\0','c');PlaybackProgress progress=new PlaybackProgress(meet,p->{});progress.save("public-checkpoint",binding,601500,1.75,false);
  ByteArrayOutputStream bytes=new ByteArrayOutputStream();LibraryBackup.write(bytes,rec,meet,null);Path restored=root.resolve("restored");LibraryBackup.restore(new ByteArrayInputStream(bytes.toByteArray()),restored);
  JSONObject checkpoint=new PlaybackProgress(restored.resolve("meetings"),p->{}).load("public-checkpoint",binding,1000000);
  if(checkpoint.getLong("positionMs")!=601500||checkpoint.getDouble("speed")!=1.75)throw new AssertionError("Current frozen backend backup lost the new playback metadata");
  if(!Arrays.equals(Files.readAllBytes(restored.resolve("meetings/original.txt")),original)||!Arrays.equals(Files.readAllBytes(meet.resolve("original.txt")),original))throw new AssertionError("Original data changed");
  System.out.println("PASS actual frozen backend LibraryBackup write/restore retains owned recording playback checkpoint and original metadata bytes; no owner data, audio inference or device qualification.");
 }
}
