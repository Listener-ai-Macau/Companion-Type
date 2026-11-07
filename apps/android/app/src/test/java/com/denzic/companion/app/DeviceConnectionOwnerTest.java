package com.denzic.companion.app;
import java.io.*;
public final class DeviceConnectionOwnerTest {
 static void check(boolean b){if(!b)throw new AssertionError();}
 static final class Port implements Closeable {int commands,closes;boolean alive=true,closeFails;public void close()throws IOException{closes++;alive=false;if(closeFails)throw new IOException("close failed");}}
 public static void main(String[] args)throws Exception {
  DeviceConnectionOwner<Port> owner=new DeviceConnectionOwner<>(p->p.alive);Port a=new Port();int[] opens={0};
  for(int i=0;i<5;i++)owner.use("A",()->{opens[0]++;return a;},p->{p.commands++;return null;});
  check(opens[0]==1&&a.commands==5&&a.closes==0);
  Port handed=owner.take("A");check(handed==a&&owner.take("A")==null);owner.close();check(a.closes==0);handed.close();check(a.closes==1);
  Port b=new Port();owner.use("B",()->b,p->null);Port c=new Port();owner.use("C",()->c,p->null);check(b.closes==1&&c.closes==0);
  try{owner.use("C",()->{throw new AssertionError("no reopen before one failing command");},p->{p.commands++;throw new IOException("command failed");});throw new AssertionError();}catch(IOException expected){check(expected.getMessage().equals("command failed"));}
  check(c.commands==1&&c.closes==1);Port d=new Port();owner.use("C",()->d,p->null);d.alive=false;Port e=new Port();owner.use("C",()->e,p->null);check(d.closes==1);
  check(owner.take("wrong")==null&&e.closes==1);
  Port f=new Port();f.closeFails=true;try{owner.use("F",()->f,p->{throw new IOException("original");});throw new AssertionError();}catch(IOException expected){check(expected.getMessage().equals("original")&&expected.getSuppressed().length==1);}
  Port g=new Port();owner.use("G",()->g,p->null);owner.close();owner.close();check(g.closes==1);
  System.out.println("PASS_ONE_OWNER_REUSE_ADDRESS_SWITCH_LIVENESS_SINGLE_HANDOFF_ERROR_RELEASE_NO_COMMAND_REPLAY");
 }
}
