package com.denzic.companion.mobile;
import java.io.*;
import java.util.*;
import static com.denzic.companion.mobile.RecorderWire.*;
public final class DeviceMaintenanceTest {
 static void check(boolean b){if(!b)throw new AssertionError();}
 static final class Link implements RecordingClient.Link {
  final Queue<byte[]> responses=new ArrayDeque<>();int result,writes;boolean corrupt;
  public int mtu(){return 512;}public void close(){}public byte[] read(UUID u){throw new AssertionError("maintenance never reads audio");}public void subscribe(UUID u){check(u.equals(DeviceMaintenance.CONTROL));}
  public void write(UUID u,byte[] p) {
   check(u.equals(DeviceMaintenance.CONTROL)&&p.length==16&&magic(p,0,"CRM1")&&u32(p,12)==crc(p,0,12));writes++;
   byte[] out=new byte[32];System.arraycopy(p,0,out,0,12);out[5]=1;out[6]=15;out[7]=2;put32(out,12,3);put32(out,20,118);put32(out,24,u32(p,8));put32(out,28,crc(out,0,28));responses.add(out.clone());
   out[5]=(byte)result;put32(out,28,crc(out,0,28));if(corrupt)out[28]^=1;responses.add(out);
  }
  public byte[] await(UUID u,long timeout)throws IOException {check(u.equals(DeviceMaintenance.CONTROL));byte[] p=responses.poll();if(p==null)throw new java.net.SocketTimeoutException();return p;}
 }
 public static void main(String[] args)throws Exception {
  for(DeviceMaintenance.Operation operation:DeviceMaintenance.Operation.values()) {
   Link link=new Link();DeviceMaintenance.Status status=DeviceMaintenance.perform(link,operation,91);
   check(link.writes==1&&status.operation==operation&&status.settingsSaved&&status.defaultSettings&&status.bondCountValid&&status.radioEnabled&&status.bonds==2&&status.preferencesGeneration==3&&status.bondGeneration==118);
  }
  Link busy=new Link();busy.result=2;
  try{DeviceMaintenance.perform(busy,DeviceMaintenance.Operation.RESTORE_SETTINGS,91);throw new AssertionError();}catch(IOException expected){check(expected.getMessage().contains("没有停止"));}check(busy.writes==1);
  Link corrupt=new Link();corrupt.corrupt=true;
  try{DeviceMaintenance.perform(corrupt,DeviceMaintenance.Operation.CLEAR_PAIRINGS,91);throw new AssertionError();}catch(IOException expected){check(expected.getMessage().contains("校验失败"));}check(corrupt.writes==1);
  System.out.println("PASS_CRM1_CORRELATED_PENDING_SUCCESS_BUSY_CORRUPT_NO_DESTRUCTIVE_REPLAY_SOFTWARE_ONLY");
 }
}
