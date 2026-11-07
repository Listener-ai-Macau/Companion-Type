package com.denzic.companion.mobile;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
public final class RecordingStoppedBatchJvmTest {
 static void check(boolean v){if(!v)throw new AssertionError();}
 static final class Link implements RecordingClient.Link {
  final RecordingDirectoryStreamJvmTest.Link base;final int mode;int hints,waits;
  Link(byte[] golden,int version,int mode){base=new RecordingDirectoryStreamJvmTest.Link(golden,version,false);this.mode=mode;}
  public int mtu(){return base.mtu();}public void subscribe(UUID id){}public byte[] read(UUID id){return base.read(id);}public void close(){}
  public void write(UUID id,byte[] value)throws IOException{base.write(id,value);if(value[1]==0x25){hints++;check(value.length==32&&value[2]==1&&value[3]==0&&Arrays.equals(Arrays.copyOfRange(value,8,20),Arrays.copyOfRange(base.status,20,32))&&RecorderWire.u64(value,20)==7&&RecorderWire.crc(value,0,28)==RecorderWire.u32(value,28));}}
  public byte[] await(UUID id,long timeout)throws IOException{
   if(base.last[1]!=0x25)return base.await(id,timeout);waits++;
   if(mode==2)throw new java.net.SocketTimeoutException();if(mode==3)throw new RecordingSyncRunner.LinkFailure("actual link lost");
   if(mode==1||(mode==4&&waits==1)){byte[] e=new byte[]{'C','R','E','2',2,0,16,0,0,0,0,0,1,0,0,0};RecorderWire.put32(e,8,RecorderWire.u32(base.last,4)+(mode==4?1:0));return e;}
   return base.last.clone();
  }
 }
 static void prefer(RecordingClient client)throws Exception{Method m=RecordingClient.class.getDeclaredMethod("preferStoppedBatch");m.setAccessible(true);try{m.invoke(client);}catch(InvocationTargetException e){throw (Exception)e.getCause();}}
 public static void main(String[] args)throws Exception{
  byte[] golden=Files.readAllBytes(Paths.get(args[0]));
  for(int mode=0;mode<5;mode++){
   Link link=new Link(golden,66703,mode);RecordingTransferMetrics metrics=new RecordingTransferMetrics();
   try(RecordingClient client=new RecordingClient(link,metrics)){
    try{prefer(client);check(mode!=3);}catch(RecordingSyncRunner.LinkFailure expected){check(mode==3);}
    prefer(client);check(link.hints==1);
    if(mode!=3)check(metrics.json().contains("\"stoppedBatchHintRequested\":true")&&metrics.json().contains("\"stoppedBatchHintAccepted\":"+(mode==0||mode==4)));
   }
  }
  Link old=new Link(golden,66702,0);try(RecordingClient client=new RecordingClient(old)){prefer(client);check(old.hints==0);}
  Link early=new Link(golden,66703,0);try(RecordingClient client=new RecordingClient(early)){
   client.prepareStoppedReceive();check(early.hints==1);prefer(client);check(early.hints==1);
  }
  Link expired=new Link(golden,66703,0);try(RecordingClient client=new RecordingClient(expired)){
   client.prepareStoppedReceive();byte[] first=expired.base.last.clone();Thread.sleep(2100);
   prefer(client);check(expired.hints==2&&!Arrays.equals(first,expired.base.last));prefer(client);check(expired.hints==2);
  }
  Link unsupported=new Link(golden,66702,0);try(RecordingClient client=new RecordingClient(unsupported)){client.prepareStoppedReceive();prefer(client);check(unsupported.hints==0);}
  RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(Arrays.copyOfRange(golden,24,136));final long[] clock={1};RecordingTransferMetrics m=new RecordingTransferMetrics(()->clock[0]);m.segment(descriptor,0).verified();clock[0]=2;m.consumeStage(descriptor,0);clock[0]=3;m.consumeStage(descriptor,1);clock[0]=4;m.consumeStage(descriptor,2);String json=m.json();check(json.contains("\"originalVerifiedNanos\":1")&&json.contains("\"consumeLocalReadyNanos\":2")&&json.contains("\"consumeWriteCompletedNanos\":3")&&json.contains("\"consumeReplyReceivedNanos\":4")&&json.contains("\"firstWindowNanos\":null"));
  System.out.println("PASS_EXISTING_FINITE_BATCH_PROTOCOL_ONE_ATTEMPT_BUSY_TIMEOUT_FALLBACK_LINK_FAILURE_PROPAGATION_OLD_PEER_SKIP_AND_PHASES_DO_NOT_MOVE_PAYLOAD_START");
 }
}
