package com.denzic.companion.app;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;
public final class IncomingAttachmentStoreTest {
 static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
 interface Checked{void run()throws Exception;}
 static void rejected(Checked task)throws Exception{try{task.run();throw new AssertionError("accepted invalid change");}catch(IOException expected){}}
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]);Files.createDirectories(root);String key="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:1:1";
  RecordingNotes notes=new RecordingNotes(root,p->{});JSONObject old=notes.save(key,0,"","原有人工备注 12000元，不改写转写",null,0);String oldEntry=old.getJSONArray("entries").getJSONObject(0).toString();
  byte[] png=Base64.getDecoder().decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=");
  String id=UUID.randomUUID().toString();int[] checks={0};RecordingNotes.ImageCheck check=file->{checks[0]++;require(Arrays.equals(Files.readAllBytes(file),png),"image bytes changed");};
  JSONObject saved=notes.addIncomingImage(key,1,id,"公开白板.png","png",new ByteArrayInputStream(png),check);
  require(saved.getLong("revision")==2&&saved.getJSONArray("entries").length()==2,"image entry not committed");
  require(oldEntry.equals(saved.getJSONArray("entries").getJSONObject(0).toString()),"old human note changed");
  JSONObject image=saved.getJSONArray("entries").getJSONObject(1);require(image.getString("id").equals(id),"fixed receipt identity lost");require(Arrays.equals(png,Files.readAllBytes(notes.verifiedImage(key,image.getJSONObject("image")))),"original image not exact");
  JSONObject retry=notes.addIncomingImage(key,1,id,"公开白板.png","png",new ByteArrayInputStream(new byte[]{0}),file->{throw new AssertionError("retry read a revoked source");});
  require(retry.getLong("revision")==2&&retry.getJSONArray("entries").length()==2&&checks[0]==1,"lost-reply retry duplicated or rewrote image");
  require(new RecordingNotes(root,p->{}).incomingImagePresent(key,id,"公开白板.png"),"restart did not recognize saved image");
  rejected(()->notes.incomingImagePresent(key,id,"另一张.png"));
  rejected(()->notes.addIncomingImage(key,1,UUID.randomUUID().toString(),"失效.png","png",new ByteArrayInputStream(png),check));
  require(notes.read(key).getLong("revision")==2,"stale save altered notes");
  String doc=UUID.randomUUID().toString();byte[] text="公开补充材料，不是会议事实。预算待确认。".getBytes(StandardCharsets.UTF_8);DocumentContextStore docs=new DocumentContextStore(root,p->{});
  JSONObject first=docs.add(key,0,doc,"公开材料.txt",new ByteArrayInputStream(text));require(Arrays.equals(text,Files.readAllBytes(docs.original(key,1,doc))),"document original not exact");
  docs.add(key,0,doc,"公开材料.txt",new ByteArrayInputStream(text));require(docs.read(key).getLong("revision")==1&&docs.read(key).getJSONArray("rows").length()==1,"lost-reply document retry duplicated");
  require(oldEntry.equals(notes.read(key).getJSONArray("entries").getJSONObject(0).toString()),"document import changed old note");
  require(new DocumentContextStore(root,p->{}).read(key).getJSONArray("rows").length()==1,"document restart failed");
  System.out.println("PASS current native image/doc stores, fixed receipt lost-reply retry, exact originals, old notes preserved, stale revision rejected, reopen");
 }
}
