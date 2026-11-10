package com.denzic.companion.app;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Bounded, sample-accurate materialization from verified local mono PCM.
 * Package-private: the service must resolve sources from its library snapshot,
 * hold their recording leases and revalidate that snapshot before publication.
 * This class neither edits source files nor publishes a library recording.
 */
final class CanonicalPcmRenderer {
 static final int RATE=16000,BUFFER=64*1024;
 static final long MAX_DATA_BYTES=(0xffffffffL-36L)&~1L;
 interface Control {void checkpoint(long copiedFrames,long totalFrames)throws IOException;}
 static final class Input {
  final String key,identity;final List<Path> parts;final List<String> hashes;
  Input(String key,String identity,List<Path> parts,List<String> hashes){
   this.key=key;this.identity=identity;this.parts=Collections.unmodifiableList(new ArrayList<>(parts==null?Collections.<Path>emptyList():parts));this.hashes=Collections.unmodifiableList(new ArrayList<>(hashes==null?Collections.<String>emptyList():hashes));
  }
 }
 static final class Clip {
  final Input input;final long start,end;
  Clip(Input input,long start,long end){this.input=input;this.start=start;this.end=end;}
 }
 static final class Result {
  final Path temporary;final long frames,bytes;final String sha256;
  Result(Path temporary,long frames,long bytes,String sha256){this.temporary=temporary;this.frames=frames;this.bytes=bytes;this.sha256=sha256;}
 }
 private static final class Part {
  final Path path;final long dataOffset,frames;final String sha256;
  Part(Path path,long dataOffset,long frames,String sha256){this.path=path;this.dataOffset=dataOffset;this.frames=frames;this.sha256=sha256;}
 }
 private static final class Prepared {
  final Input input;final List<Part> parts;final long frames;
  Prepared(Input input,List<Part> parts,long frames){this.input=input;this.parts=parts;this.frames=frames;}
 }
 private static IOException invalid(String text){return new IOException(text);}
 private static MessageDigest digest(){try{return MessageDigest.getInstance("SHA-256");}catch(java.security.NoSuchAlgorithmException e){throw new AssertionError(e);}}
 private static String hex(byte[] bytes){StringBuilder out=new StringBuilder(64);for(byte b:bytes)out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return out.toString();}
 private static boolean sha(String text){return text!=null&&text.matches("[0-9a-f]{64}");}
 private static void exact(FileChannel channel,ByteBuffer buffer,long offset)throws IOException {
  while(buffer.hasRemaining()){int n=channel.read(buffer,offset);if(n<=0)throw invalid("音频原件读取不完整，请重新准备后重试。");offset+=n;}buffer.flip();
 }
 private static long u32(ByteBuffer b,int offset){return b.getInt(offset)&0xffffffffL;}
 private static boolean tag(ByteBuffer b,int at,String text){for(int i=0;i<4;i++)if(b.get(at+i)!=(byte)text.charAt(i))return false;return true;}
 private static String hash(Path path,Control control,long done,long total)throws IOException {
  MessageDigest hash=digest();ByteBuffer buffer=ByteBuffer.allocate(BUFFER);
  try(FileChannel in=FileChannel.open(path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
   while(true){control.checkpoint(done,total);int n=in.read(buffer);if(n<0)break;if(n==0)throw invalid("音频原件暂不能读取，请稍后重试。");buffer.flip();hash.update(buffer);buffer.clear();}
  }return hex(hash.digest());
 }
 private static Part inspect(Path path,String expected,Control control)throws IOException {
  if(path==null||!sha(expected)||Files.isSymbolicLink(path)||!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS))throw invalid("音频原件身份无法确认，请重新准备。");
  long size=Files.size(path);if(size<44)throw invalid("本机回听音频不完整，请重新准备。");
  long dataOffset=-1,dataBytes=-1;boolean format=false;
  try(FileChannel in=FileChannel.open(path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
   ByteBuffer head=ByteBuffer.allocate(16).order(ByteOrder.LITTLE_ENDIAN);head.limit(12);exact(in,head,0);
   if(!tag(head,0,"RIFF")||!tag(head,8,"WAVE")||u32(head,4)+8!=size)throw invalid("本机回听音频不是完整WAV，请重新准备。");
   for(long offset=12;offset<size;){
    control.checkpoint(0,0);if(size-offset<8)throw invalid("本机回听音频区块不完整。");head.clear();head.limit(8);exact(in,head,offset);long length=u32(head,4),body=offset+8,next=body+length+(length&1);
    if(next<body||next>size)throw invalid("本机回听音频区块越界。");
    if(tag(head,0,"fmt ")){
     if(format||length<16)throw invalid("本机回听音频格式不明确。");ByteBuffer fmt=ByteBuffer.allocate(16).order(ByteOrder.LITTLE_ENDIAN);exact(in,fmt,body);
     if(fmt.getShort(0)!=1||fmt.getShort(2)!=1||u32(fmt,4)!=RATE||u32(fmt,8)!=RATE*2L||fmt.getShort(12)!=2||fmt.getShort(14)!=16)throw invalid("请先准备16kHz单声道本机回听音频，再进行编辑。");format=true;
    }else if(tag(head,0,"data")){
     if(dataOffset>=0||length==0||(length&1)!=0)throw invalid("本机回听音频采样区间无效。");dataOffset=body;dataBytes=length;
    }
    offset=next;
   }
  }
  if(!format||dataOffset<0)throw invalid("本机回听音频没有完整采样数据。");String actual=hash(path,control,0,0);if(!actual.equals(expected))throw invalid("音频原件已变化，请重新选择编辑范围。");return new Part(path,dataOffset,dataBytes/2,actual);
 }
 private static Prepared prepare(Input input,Control control)throws IOException {
  if(input==null||input.key==null||input.key.isEmpty()||input.key.length()>1200||!sha(input.identity)||input.parts.isEmpty()||input.parts.size()!=input.hashes.size()||input.parts.size()>4096)throw invalid("录音来源尚未确认，请重新读取。");
  List<Part> parts=new ArrayList<>();long frames=0;
  for(int i=0;i<input.parts.size();i++){Part p=inspect(input.parts.get(i),input.hashes.get(i),control);try{frames=Math.addExact(frames,p.frames);}catch(ArithmeticException e){throw invalid("音频来源长度超出处理范围。");}parts.add(p);}
  return new Prepared(input,parts,frames);
 }
 private static ByteBuffer header(long frames){long bytes=frames*2;ByteBuffer b=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);b.put(new byte[]{'R','I','F','F'}).putInt((int)(36+bytes)).put(new byte[]{'W','A','V','E','f','m','t',' '}).putInt(16).putShort((short)1).putShort((short)1).putInt(RATE).putInt(RATE*2).putShort((short)2).putShort((short)16).put(new byte[]{'d','a','t','a'}).putInt((int)bytes);b.flip();return b;}
 private static void write(FileChannel out,ByteBuffer buffer)throws IOException {while(buffer.hasRemaining())if(out.write(buffer)<=0)throw invalid("派生音频未完整写入，请检查存储空间。");}

 /** Returns a private temporary. Nothing enters the library until the caller
  * atomically publishes it together with its independently validated source map.
  */
 static Result render(Path privateStage,List<Clip> clips,Control control)throws IOException {
  if(control==null||clips==null||clips.isEmpty()||clips.size()>512)throw invalid("请选择有效的音频片段。");
  if(Files.isSymbolicLink(privateStage)||!Files.isDirectory(privateStage,LinkOption.NOFOLLOW_LINKS))throw invalid("编辑临时目录尚未就绪。");
  List<Prepared> sources=new ArrayList<>();long total=0;
  for(Clip clip:clips){
   control.checkpoint(0,0);if(clip==null)throw invalid("请选择有效的音频片段。");Prepared source=null;for(Prepared p:sources)if(p.input==clip.input)source=p;
   if(source==null){if(sources.size()>=128)throw invalid("本次来源过多，请分批保存。");source=prepare(clip.input,control);for(Prepared prior:sources)if(prior.input.key.equals(source.input.key))throw invalid("原音身份重复，请重新读取。");sources.add(source);}
   if(clip.start<0||clip.end<=clip.start||clip.end>source.frames)throw invalid("编辑区间超出原音范围。");
   try{total=Math.addExact(total,clip.end-clip.start);}catch(ArithmeticException e){throw invalid("派生音频长度超出处理范围。");}
   if(total>MAX_DATA_BYTES/2)throw invalid("派生音频超过单份WAV范围，请先切分保存。");
  }
  control.checkpoint(0,total);Path output=Files.createTempFile(privateStage,"derived-pcm-",".wav.part");boolean complete=false;long copied=0;
  try{
   ByteBuffer buffer=ByteBuffer.allocate(BUFFER);
   try(FileChannel out=FileChannel.open(output,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){
    write(out,header(total));
    for(Clip clip:clips){
     Prepared source=null;for(Prepared p:sources)if(p.input==clip.input)source=p;long base=0;
     for(Part part:source.parts){
      long start=Math.max(clip.start,base),end=Math.min(clip.end,base+part.frames);
      if(start<end)try(FileChannel in=FileChannel.open(part.path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
       long offset=part.dataOffset+(start-base)*2,remaining=(end-start)*2;
       while(remaining>0){control.checkpoint(copied,total);buffer.clear();buffer.limit((int)Math.min(BUFFER,remaining));exact(in,buffer,offset);int bytes=buffer.remaining();write(out,buffer);offset+=bytes;remaining-=bytes;copied+=bytes/2;}
      }
      base+=part.frames;
     }
    }
    if(copied!=total||out.size()!=44+total*2)throw invalid("派生音频尚未完整生成，原件保留。");out.force(true);
   }
   for(Prepared source:sources)for(Part part:source.parts)if(!hash(part.path,control,copied,total).equals(part.sha256))throw invalid("原音在编辑期间发生变化，已停止保存派生件。");
   control.checkpoint(copied,total);String result=hash(output,control,copied,total);complete=true;return new Result(output,total,44+total*2,result);
  }finally{
   // Only the unique file created by this operation is retired on failure.
   // The caller owns and must protect this private stage throughout rendering.
   if(!complete)Files.deleteIfExists(output);
  }
 }
 private CanonicalPcmRenderer(){}
}
