package com.denzic.companion.mobile;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
public final class RecordingClientHandoffJvmTest {
 static void check(boolean b){if(!b)throw new AssertionError();}
 static final class Link implements RecordingClient.Link {
  byte[] status,reply;boolean alive=true;int closes,writes;
  Link(byte[] status){this.status=status;}
  public int mtu(){return 512;}public boolean isConnected(){return alive;}public String deviceAddress(){return "A";}
  public void subscribe(UUID id){}public byte[] read(UUID id){return status.clone();}public void write(UUID id,byte[] bytes){writes++;reply=bytes.clone();}
  public byte[] await(UUID id,long timeout)throws IOException{if(reply[1]!=0x22)throw new IOException("fresh catalogue requested");return reply.clone();}public void close(){closes++;alive=false;}
 }
 static void put(String key,Object value)throws Exception{Field f=RecordingSyncService.class.getDeclaredField(key);f.setAccessible(true);f.set(null,value);}
 static RecordingClient take(String address,byte[] descriptor)throws Exception {
  Method m=RecordingSyncService.class.getDeclaredMethod("takePending",String.class,byte[].class);m.setAccessible(true);
  try{return (RecordingClient)m.invoke(null,address,descriptor);}catch(InvocationTargetException e){throw (Exception)e.getCause();}
 }
 static void offer(RecordingClient client,String address,byte[] wire)throws Exception{put("pendingClient",client);put("pendingAddress",address);put("pendingDescriptor",wire.clone());}
 static void cached(RecordingClient client,RecorderWire.Descriptor selected)throws Exception {
  Field list=RecordingClient.class.getDeclaredField("current");list.setAccessible(true);list.set(client,Collections.singletonList(selected));
  Field reusable=RecordingClient.class.getDeclaredField("catalogueReusable");reusable.setAccessible(true);reusable.set(client,true);
 }
 public static void main(String[] args)throws Exception {
  byte[] status=Files.readAllBytes(Paths.get(args[0])),wire=Files.readAllBytes(Paths.get(args[1]));RecorderWire.Descriptor selected=RecorderWire.Descriptor.decode(wire);
  Link link=new Link(status);RecordingClient client=new RecordingClient(link);client.validateHandoff("A",selected);int negotiationWrites=link.writes;
  offer(client,"A",wire);check(take("A",wire)==client&&take("A",wire)==null&&link.closes==0&&link.writes==negotiationWrites);
  RecordingTransferMetrics metrics=new RecordingTransferMetrics();cached(client,selected);client.attachTransferMetrics(metrics,selected);
  check(client.directoryForSync(selected,false).get(0).sameContent(selected)&&link.writes==negotiationWrites&&metrics.json().contains("\"reusedCatalogues\":1"));
  try{client.directoryForSync(selected,false);throw new AssertionError();}catch(IOException expected){check(link.writes>negotiationWrites);}
  try{client.attachTransferMetrics(metrics,selected);throw new AssertionError();}catch(IOException expected){}
  client.close();check(link.closes==1);
  Link wrong=new Link(status);RecordingClient second=new RecordingClient(wrong);offer(second,"A",wire);
  try{take("B",wire);throw new AssertionError();}catch(IOException expected){}check(wrong.closes==1&&take("A",wire)==null);
  Link changed=new Link(status);RecordingClient third=new RecordingClient(changed);offer(third,"A",wire);byte[] altered=wire.clone();altered[20]^=1;
  try{take("A",altered);throw new AssertionError();}catch(IOException expected){}check(changed.closes==1);
  Link died=new Link(status);RecordingClient fourth=new RecordingClient(died);died.alive=false;
  try{fourth.validateHandoff("A",selected);throw new AssertionError();}catch(RecordingSyncRunner.LinkFailure expected){}fourth.close();
  Link invalidStart=new Link(status);RecordingClient fifth=new RecordingClient(invalidStart);
  try{RecordingSyncService.start(null,null,null,null,fifth);throw new AssertionError();}catch(IllegalArgumentException expected){}check(invalidStart.closes==1);
  Link invalidResume=new Link(status);RecordingClient sixth=new RecordingClient(invalidResume);
  try{RecordingSyncService.resume(null,sixth);throw new AssertionError();}catch(NullPointerException expected){}check(invalidResume.closes==1);
  Link invalidPending=new Link(status);RecordingClient seventh=new RecordingClient(invalidPending);
  try{RecordingSyncService.resumePending(null,null,null,seventh);throw new AssertionError();}catch(IllegalArgumentException expected){}check(invalidPending.closes==1);
   for(int reason=0;reason<5;reason++){
    Link fresh=new Link(status);RecordingClient c=new RecordingClient(fresh);RecorderWire.Descriptor listed=selected;
    if(reason>=3){byte[] live=selected.wireBytes();live[92]=(byte)(reason==3?1:7);if(reason==3)Arrays.fill(live,88,92,(byte)0);java.util.zip.CRC32 crc=new java.util.zip.CRC32();crc.update(live,0,108);long sum=crc.getValue();for(int i=0;i<4;i++)live[108+i]=(byte)(sum>>>(8*i));listed=RecorderWire.Descriptor.decode(live);}
    cached(c,listed);
   if(reason==1)try{c.control(Paths.get("."),"owned",NativeRecordingControl.Action.START,-1);throw new AssertionError();}catch(IllegalArgumentException expected){}
   if(reason==2)try{c.deleteDeviceSession(selected,null);throw new AssertionError();}catch(IllegalArgumentException expected){}
    RecordingTransferMetrics observed=new RecordingTransferMetrics();c.attachTransferMetrics(observed,listed);int prior=fresh.writes;
    try{c.directoryForSync(listed,reason==0);throw new AssertionError("live/stale/pending directory reused");}catch(IOException expected){check(fresh.writes>prior);}
   check(observed.json().contains("\"reusedCatalogues\":0"));c.close();
  }
  System.out.println("PASS_ACTUAL_SDK_SERVICE_HANDOFF_SINGLE_TAKE_EXACT_SELECTION_FAILURE_RELEASE_AND_METRICS_ATTACHMENT_NO_RENEGOTIATION");
 }
}
