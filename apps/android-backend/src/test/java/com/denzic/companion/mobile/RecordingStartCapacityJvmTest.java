package com.denzic.companion.mobile;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class RecordingStartCapacityJvmTest {
 static void check(boolean value){if(!value)throw new AssertionError();}
 static final class Link implements RecordingClient.Link {
  byte[][] values;int reads,writes;
  Link(byte[]... values){this.values=values;}
  public int mtu(){return 512;}public void subscribe(UUID id){}public byte[] read(UUID id){return values[Math.min(reads++,values.length-1)].clone();}
  public void write(UUID id,byte[] value){writes++;}public byte[] await(UUID id,long timeout){throw new AssertionError();}public void close(){}
 }
 public static void main(String[] args)throws Exception {
  byte[] busy=Files.readAllBytes(Paths.get(args[0])),ready=Files.readAllBytes(Paths.get(args[1]));
  Link normal=new Link(ready);check(Arrays.equals(new NativeRecordingControl.Callbacks(normal,true).identity(),ready)&&normal.reads==1&&normal.writes==0);
  Link refresh=new Link(busy,busy,ready);check(Arrays.equals(new NativeRecordingControl.Callbacks(refresh,true).identity(),ready)&&refresh.reads==3&&refresh.writes==0);
  Link query=new Link(busy);check(Arrays.equals(new NativeRecordingControl.Callbacks(query).identity(),busy)&&query.reads==1);
  Link stuck=new Link(busy);long before=System.nanoTime();try{new NativeRecordingControl.Callbacks(stuck,true).identity();throw new AssertionError();}catch(IOException expected){check(expected.getMessage().contains("更新剩余空间")&&!expected.getMessage().contains("升级"));}check(System.nanoTime()-before<2_000_000_000L&&stuck.writes==0);
  byte[] changed=ready.clone();changed[20]^=1;Link wrong=new Link(busy,changed);try{new NativeRecordingControl.Callbacks(wrong,true).identity();throw new AssertionError();}catch(IOException expected){check(expected.getMessage().contains("身份已变化"));}check(wrong.writes==0);
  byte[] malformed=ready.clone();malformed[41]=0;Link unknown=new Link(malformed);check(Arrays.equals(new NativeRecordingControl.Callbacks(unknown,true).identity(),malformed)&&unknown.reads==1);
  byte[] old=busy.clone();old[39]='1';old[40]=1;Link legacy=new Link(old);check(Arrays.equals(new NativeRecordingControl.Callbacks(legacy,true).identity(),old)&&legacy.reads==1);
  Thread.currentThread().interrupt();Link interrupted=new Link(busy);try{new NativeRecordingControl.Callbacks(interrupted,true).identity();throw new AssertionError();}catch(IOException expected){check(Thread.currentThread().isInterrupted()&&interrupted.writes==0);}finally{Thread.interrupted();}
  System.out.println("PASS_ACTUAL_CAPTURED_BUSY_READY_START_WAIT_BOUND_IDENTITY_INTERRUPTION_NO_COMMAND_REPLAY_AND_LEGACY_UNCHANGED");
 }
}
