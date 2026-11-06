package com.denzic.companion.mobile;
import java.util.*;
import java.nio.file.*;
import java.io.*;
import static com.denzic.companion.mobile.RecorderWire.*;

/** The real FW66685 offer/descriptor is a protocol vector, not an audio fixture. */
public final class DeviceRecordingsTest {
 static void check(boolean b){if(!b)throw new AssertionError();}
 static final class Link implements RecordingClient.Link {
  final byte[] offer,status;final Queue<byte[]> replies=new ArrayDeque<>();int commands,erase;boolean forged;
  Link(byte[] o,byte[] s){offer=o.clone();status=s.clone();}
  public int mtu(){return 512;} public void close(){} public void subscribe(UUID id){}
  public byte[] read(UUID id){return status.clone();}
  public void write(UUID id,byte[] value)throws IOException {
   check(id.equals(RecordingClient.RECORDING_CONSUME));commands++;
   if(value[4]==1) {
    check(Arrays.equals(Arrays.copyOfRange(value,16,44),Arrays.copyOfRange(offer,16,44)));
    replies.add(value.clone());byte[] o=offer.clone();if(forged)o[36]^=1;put32(o,92,crc(o,0,92));replies.add(o);
   }else {
    check(value[4]==2||value[4]==3);byte[] e=offer.clone();e[4]=value[4];put32(e,92,crc(e,0,92));check(Arrays.equals(value,e));
    if(value[4]==2)erase++;e[5]=2;put32(e,92,crc(e,0,92));replies.add(e);
   }
  }
  public byte[] await(UUID id,long timeout)throws IOException {byte[] p=replies.poll();if(p==null)throw new java.net.SocketTimeoutException();return p;}
 }
 public static void main(String[] args)throws Exception {
  Path root=Paths.get(args[0]);byte[] p=Files.readAllBytes(root.resolve("offer.bin")),status=Files.readAllBytes(root.resolve("status.bin"));
  Descriptor selected=Descriptor.decode(Files.readAllBytes(root.resolve("descriptor.bin")));long request=u32(p,8);
  check(DeviceRecordings.group(Arrays.asList(selected)).size()==1);
  DeviceRecordings.Session row=DeviceRecordings.group(Arrays.asList(selected)).get(0);
  check(row.complete&&row.segments==1&&row.durationMillis==selected.sampleCount/16);
  Link cancel=new Link(p,status);check(!DeviceRecordings.delete(cancel,selected,request,offer->false));check(cancel.commands==2&&cancel.erase==0);
  Link accept=new Link(p,status);check(DeviceRecordings.delete(accept,selected,request,offer->true));check(accept.commands==2&&accept.erase==1);
  Link forged=new Link(p,status);forged.forged=true;
  try{DeviceRecordings.delete(forged,selected,request,offer->true);throw new AssertionError("different session accepted");}catch(IOException expected){}
  check(forged.commands==1&&forged.erase==0);
  byte[] second=selected.wireBytes();put32(second,28,1);put64(second,32,selected.sampleCount);put32(second,88,2);put32(second,108,crc(second,0,108));
  Descriptor missing=Descriptor.decode(second);row=DeviceRecordings.group(Arrays.asList(missing)).get(0);check(!row.complete&&row.startedUnixSeconds==0);
  List<DeviceRecordings.Session> grouped=DeviceRecordings.group(Arrays.asList(selected,missing));check(grouped.size()==1&&grouped.get(0).complete);
  System.out.println("PASS_REAL_FIRMWARE_WIRE_VECTOR_CANCEL_EXACT_SESSION_DELETE_FORGED_OFFER_AND_LOGICAL_GROUPING_SOFTWARE_ONLY");
 }
}
