package com.denzic.companion.app;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
public final class IncomingFileQueueTest {
 static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
 interface Checked{void run()throws Exception;}
 static void rejected(Checked task)throws Exception{try{task.run();throw new AssertionError("accepted invalid operation");}catch(java.io.IOException expected){}}
 static JSONArray file(String name,String suffix)throws Exception{return new JSONArray().put(new JSONObject().put("uri","content://public.test/"+suffix).put("name",name).put("mime","application/octet-stream").put("bytes",500));}
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]);Files.createDirectories(root);IncomingFileQueue queue=new IncomingFileQueue(root,p->{});
  queue.receive(file("预算.xlsx","budget"));require(queue.list().length()==1,"first receive");String id=queue.list().getJSONObject(0).getString("id");
  require(!queue.list().getJSONObject(0).has("uri"),"native URI leaked into presentation");
  queue.receive(file("预算.xlsx","budget"));require(queue.list().length()==1,"pending duplicate was duplicated");
  require(new IncomingFileQueue(root,p->{}).get(id).getString("kind").equals("document"),"restart lost file classification");
  byte[] original=Files.readAllBytes(root.resolve("companion-incoming-v1.json"));
  JSONArray invalid=file("正常.mp3","normal").put(new JSONObject().put("uri","file:///private/secret").put("name","x.wav").put("mime","audio/wav").put("bytes",1));
  rejected(()->queue.receive(invalid));require(Arrays.equals(original,Files.readAllBytes(root.resolve("companion-incoming-v1.json"))),"partial mixed delivery committed");
  queue.bind(id,"original","meeting-a","第一场会议");queue.state(id,"attempting","开始保存");
  rejected(()->queue.bind(id,"original","meeting-b","另一场会议"));rejected(()->queue.bind(id,"restored","meeting-a","相同key但另一资料库"));
  queue.state(id,"failed","中断");queue.bind(id,"original","meeting-a","第一场会议");queue.state(id,"complete","已保存");
  require(new IncomingFileQueue(root,p->{}).get(id).getString("state").equals("complete"),"restart lost receipt");
  // Multiple recreated Activity/Service store objects must serialize publication.
  ExecutorService pool=Executors.newFixedThreadPool(4);List<Future<?>> work=new ArrayList<>();
  for(int i=0;i<8;i++){final int n=i;work.add(pool.submit(()->{try{new IncomingFileQueue(root,p->{}).receive(file("公开-"+n+".wav","parallel-"+n));}catch(Exception e){throw new RuntimeException(e);}}));}
  for(Future<?> f:work)f.get();pool.shutdown();require(queue.list().length()==9,"concurrent reception lost an item");
  JSONArray tooMany=new JSONArray();for(int i=0;i<17;i++)tooMany.put(file("x.mp3","too-"+i).getJSONObject(0));original=Files.readAllBytes(root.resolve("companion-incoming-v1.json"));rejected(()->queue.receive(tooMany));require(Arrays.equals(original,Files.readAllBytes(root.resolve("companion-incoming-v1.json"))),"overlimit changed receipt");
  queue.remove(id);require(queue.list().length()==8,"scoped remove");queue.remove(id);require(queue.list().length()==8,"repeated dismiss changed other deliveries");
  queue.receive(file("清除此条材料.txt","purge-own"));queue.receive(file("保留另一资料库.txt","purge-other"));
  String own=null,foreign=null;JSONArray staged=queue.list();for(int i=0;i<staged.length();i++){JSONObject row=staged.getJSONObject(i);if(row.getString("name").equals("清除此条材料.txt"))own=row.getString("id");if(row.getString("name").equals("保留另一资料库.txt"))foreign=row.getString("id");}
  queue.bind(own,"original","same-recording","本条会议");queue.bind(foreign,"other-library","same-recording","另一资料库同key");String foreignBefore=queue.get(foreign).toString();int countBefore=queue.list().length();
  queue.removeBound("original","same-recording");require(queue.list().length()==countBefore-1,"scoped purge did not remove own receipt");require(queue.get(foreign).toString().equals(foreignBefore),"purge removed another library receipt");require(queue.list().length()==9,"purge changed unbound receipts");
  String body=new String(Files.readAllBytes(root.resolve("companion-incoming-v1.json")),java.nio.charset.StandardCharsets.UTF_8);Files.write(root.resolve("companion-incoming-v1.json"),body.replace("公开-0","篡改-0").getBytes(java.nio.charset.StandardCharsets.UTF_8));
  rejected(()->queue.list());require(new String(Files.readAllBytes(root.resolve("companion-incoming-v1.json")),java.nio.charset.StandardCharsets.UTF_8).contains("篡改-0"),"corruption was silently overwritten");
  System.out.println("PASS pending-receipt cold-reload / dedup / whole-delivery validation / immutable targets / concurrent instances / quota / scoped dismissal / corruption retention");
 }
}
