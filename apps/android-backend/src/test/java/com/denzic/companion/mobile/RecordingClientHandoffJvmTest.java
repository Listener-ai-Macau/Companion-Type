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
  public byte[] await(UUID id,long timeout){return reply.clone();}public void close(){closes++;alive=false;}
 }
 static void put(String key,Object value)throws Exception{Field f=RecordingSyncService.class.getDeclaredField(key);f.setAccessible(true);f.set(null,value);}
 static RecordingClient take(String address,byte[] descriptor)throws Exception {
  Method m=RecordingSyncService.class.getDeclaredMethod("takePending",String.class,byte[].class);m.setAccessible(true);
  try{return (RecordingClient)m.invoke(null,address,descriptor);}catch(InvocationTargetException e){throw (Exception)e.getCause();}
 }
 static void offer(RecordingClient client,String address,byte[] wire)throws Exception{put("pendingClient",client);put("pendingAddress",address);put("pendingDescriptor",wire.clone());}
 public static void main(String[] args)throws Exception {
  byte[] status=Files.readAllBytes(Paths.get(args[0])),wire=Files.readAllBytes(Paths.get(args[1]));RecorderWire.Descriptor selected=RecorderWire.Descriptor.decode(wire);
  Link link=new Link(status);RecordingClient client=new RecordingClient(link);client.validateHandoff("A",selected);int negotiationWrites=link.writes;
  offer(client,"A",wire);check(take("A",wire)==client&&take("A",wire)==null&&link.closes==0&&link.writes==negotiationWrites);
  RecordingTransferMetrics metrics=new RecordingTransferMetrics();client.attachTransferMetrics(metrics);
  try{client.attachTransferMetrics(metrics);throw new AssertionError();}catch(IOException expected){}
  client.close();check(link.closes==1);
  Link wrong=new Link(status);RecordingClient second=new RecordingClient(wrong);offer(second,"A",wire);
  try{take("B",wire);throw new AssertionError();}catch(IOException expected){}check(wrong.closes==1&&take("A",wire)==null);
  Link changed=new Link(status);RecordingClient third=new RecordingClient(changed);offer(third,"A",wire);byte[] altered=wire.clone();altered[20]^=1;
  try{take("A",altered);throw new AssertionError();}catch(IOException expected){}check(changed.closes==1);
  Link died=new Link(status);RecordingClient fourth=new RecordingClient(died);died.alive=false;
  try{fourth.validateHandoff("A",selected);throw new AssertionError();}catch(RecordingSyncRunner.LinkFailure expected){}fourth.close();
  Link invalidStart=new Link(status);RecordingClient fifth=new RecordingClient(invalidStart);
  try{RecordingSyncService.start(null,null,null,null,fifth);throw new AssertionError();}catch(IllegalArgumentException expected){}check(invalidStart.closes==1);
  System.out.println("PASS_ACTUAL_SDK_SERVICE_HANDOFF_SINGLE_TAKE_EXACT_SELECTION_FAILURE_RELEASE_AND_METRICS_ATTACHMENT_NO_RENEGOTIATION");
 }
}
