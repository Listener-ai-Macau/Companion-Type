package com.denzic.companion.mobile;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.CRC32;
public final class RecordingDirectoryStreamJvmTest {
 static void check(boolean value){if(!value)throw new AssertionError();}
 static final class Link implements RecordingClient.Link {
  final byte[] status,golden;final boolean stale;byte[] last;int requests,cursor,options,delivered;boolean invalidated;
  Link(byte[] golden,int version,boolean stale){this.golden=golden;this.stale=stale;status=new byte[116];status[0]=1;RecorderWire.put32(status,4,version);RecorderWire.put32(status,12,0x57424155L);for(int i=0;i<12;i++)status[20+i]=(byte)(i+1);System.arraycopy(new byte[]{'C','R','V','2',2,0,32,0},0,status,84,8);RecorderWire.put32(status,92,7);RecorderWire.put64(status,96,7);status[104]=64;status[107]=4;status[108]=(byte)253;status[109]=1;RecorderWire.put32(status,112,RecorderWire.crc(status,84,28));}
  public int mtu(){return 512;}public boolean calendarSupported(){return true;}public void subscribe(UUID id){}public byte[] read(UUID id){return status.clone();}public void close(){}
  public void write(UUID id,byte[] value)throws IOException {last=value.clone();if(value[1]==0x20){requests++;options=value[2]&255;cursor=(int)RecorderWire.u32(value,12);if(requests>1&&(options&2)!=0)check(cursor==0);}}
  public byte[] await(UUID id,long timeout)throws IOException {
   if(id.equals(RecordingClient.RECORDING_CONTROL))return last.clone();
   check(id.equals(RecordingClient.RECORDING_LIST));long nonce=RecorderWire.u32(last,8);
   if(stale&&!invalidated&&delivered==1){invalidated=true;byte[] e=new byte[16];System.arraycopy(new byte[]{'C','R','E','2',2,0,16,0},0,e,0,8);RecorderWire.put32(e,8,nonce);RecorderWire.put32(e,12,8);return e;}
   if(cursor>=4)throw new IOException("unexpected extra directory wait");
   byte[] page=Arrays.copyOfRange(golden,cursor*140,(cursor+1)*140);check(page.length==140&&page[1]==1);RecorderWire.put32(page,16,nonce);if(invalidated)RecorderWire.put32(page,4,999);CRC32 c=new CRC32();c.update(page,0,20);c.update(page,24,116);RecorderWire.put32(page,20,c.getValue());cursor++;delivered++;return page;
  }
 }
 public static void main(String[] args)throws Exception {
  byte[] golden=Files.readAllBytes(Paths.get(args[0]));check(golden.length==560);
  for(int version:new int[]{66702,66703}){
   Link link=new Link(golden,version,false);RecordingTransferMetrics metrics=new RecordingTransferMetrics();try(RecordingClient client=new RecordingClient(link,metrics)){List<RecorderWire.Descriptor> rows=client.listRecordings();check(rows.size()==4&&link.requests==(version==66703?1:4)&&link.options==(version==66703?3:1));for(int i=0;i<4;i++)check(rows.get(i).recordingId==i+1);check(metrics.json().contains("\"directoryRequests\":"+link.requests)&&metrics.json().contains("\"directoryPages\":4")&&metrics.json().contains("\"streamDirectoryRequests\":"+(version==66703?1:0)));}
  }
  Link stale=new Link(golden,66703,true);try(RecordingClient client=new RecordingClient(stale)){List<RecorderWire.Descriptor> rows=client.listRecordings();check(rows.size()==4&&stale.requests==2&&stale.invalidated);for(int i=0;i<4;i++)check(rows.get(i).recordingId==i+1);}
  System.out.println("PASS_REAL_C_PRODUCER_PAGES_NEW_FIRMWARE_ONE_REQUEST_OLD_FIRMWARE_PAGED_AND_STALE_RESTART_NO_MIXED_GENERATIONS");
 }
}
