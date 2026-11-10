package com.denzic.companion.app;
import android.media.*;
import com.denzic.companion.mobile.ImportedAudio;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

/** Android extract/decode only. No recording, network, model or Opus re-encoding. */
final class PlatformMediaImport {
 interface Observer {void progress(String phase,long processed,long total)throws IOException;}
 static List<Long> decode(Path original,Path stage,Observer observer)throws Exception {
  MediaExtractor extractor=new MediaExtractor();MediaCodec codec=null;
  try(FileInputStream input=new FileInputStream(original.toFile());Waves waves=new Waves(stage,observer)){
   verifyRiff(original);
   extractor.setDataSource(input.getFD());int track=-1;MediaFormat format=null;
   for(int i=0;i<extractor.getTrackCount();i++){MediaFormat candidate=extractor.getTrackFormat(i);String mime=candidate.getString(MediaFormat.KEY_MIME);if(mime!=null&&mime.startsWith("audio/")){track=i;format=candidate;break;}}
   if(track<0)throw new IOException("文件中没有可用音轨，请选择音频或带声音的视频。");
   extractor.selectTrack(track);String mime=format.getString(MediaFormat.KEY_MIME);long duration=format.containsKey(MediaFormat.KEY_DURATION)?format.getLong(MediaFormat.KEY_DURATION):0;
   if(duration>24L*60*60*1000000)throw new IOException("单份导入最多支持24小时，请先分成较短的文件。");
   Converter converter=new Converter(waves);long lastActivity=android.os.SystemClock.elapsedRealtime();long processed=0;
   if("audio/raw".equals(mime)){
    converter.configure(format);ByteBuffer buffer=ByteBuffer.allocate(1024*1024);
    while(true){observer.progress("正在处理音轨",processed,duration);buffer.clear();int size=extractor.readSampleData(buffer,0);if(size<0)break;if(size>buffer.capacity())throw new IOException("音频单帧过大，暂不能导入。");buffer.position(0);buffer.limit(size);converter.accept(buffer);processed=Math.max(processed,extractor.getSampleTime());if(!extractor.advance())break;}
   }else{
    format.setInteger(MediaFormat.KEY_PCM_ENCODING,AudioFormat.ENCODING_PCM_16BIT);codec=MediaCodec.createDecoderByType(mime);codec.configure(format,null,null,0);codec.start();MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();boolean inputEnd=false,outputEnd=false;
    while(!outputEnd){observer.progress("正在处理音轨",processed,duration);boolean activity=false;
     if(!inputEnd){int index=codec.dequeueInputBuffer(10000);if(index>=0){ByteBuffer buffer=codec.getInputBuffer(index);if(buffer==null)throw new IOException("无法读取音频解码缓冲。");buffer.clear();int size=extractor.readSampleData(buffer,0);if(size<0){codec.queueInputBuffer(index,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inputEnd=true;}else{if(size>buffer.capacity())throw new IOException("音频单帧过大，暂不能导入。");int flags=extractor.getSampleFlags();if((flags&MediaExtractor.SAMPLE_FLAG_ENCRYPTED)!=0)throw new IOException("受保护的音轨暂不能导入。");codec.queueInputBuffer(index,0,size,extractor.getSampleTime(),0);extractor.advance();}activity=true;}}
     int output=codec.dequeueOutputBuffer(info,10000);
     if(output==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){converter.configure(codec.getOutputFormat());activity=true;}
     else if(output>=0){try{if(info.size>0&&(info.flags&MediaCodec.BUFFER_FLAG_CODEC_CONFIG)==0){if(converter.pcm==null)converter.configure(codec.getOutputFormat());ByteBuffer buffer=codec.getOutputBuffer(output);if(buffer==null)throw new IOException("音频解码结果暂不可读。");buffer.position(info.offset);buffer.limit(info.offset+info.size);converter.accept(buffer.slice());processed=Math.max(processed,info.presentationTimeUs);}outputEnd=(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;activity=true;}finally{codec.releaseOutputBuffer(output,false);}}
     long now=android.os.SystemClock.elapsedRealtime();if(activity)lastActivity=now;else if(now-lastActivity>30000)throw new IOException("音轨解码长时间没有进展，请重试或换一个文件。");
    }
   }
   if(converter.pcm==null)throw new IOException("文件中没有解码出音频。");converter.pcm.finish();List<Long> result=waves.finish();if(result.isEmpty())throw new IOException("文件中没有可保存的声音。");observer.progress("正在校验并保存",1,1);return result;
  }finally{if(codec!=null){try{codec.stop();}catch(Exception ignored){}codec.release();}extractor.release();}
 }
 private static void verifyRiff(Path file)throws IOException {
  try(InputStream in=Files.newInputStream(file)){byte[] h=new byte[12];int n=in.read(h);if(n==12&&h[0]=='R'&&h[1]=='I'&&h[2]=='F'&&h[3]=='F'&&h[8]=='W'&&h[9]=='A'&&h[10]=='V'&&h[11]=='E'){long expected=Integer.toUnsignedLong(ByteBuffer.wrap(h,4,4).order(ByteOrder.LITTLE_ENDIAN).getInt())+8;if(expected>Files.size(file))throw new IOException("音频文件不完整，请重新获取原文件。");}}
 }
 private static final class Converter {
  final Waves waves;SpeechPcmConverter pcm;int rate,channels,encoding;float[] floats=new float[0];
  Converter(Waves waves){this.waves=waves;}
  void configure(MediaFormat f)throws IOException {int r=f.getInteger(MediaFormat.KEY_SAMPLE_RATE),c=f.getInteger(MediaFormat.KEY_CHANNEL_COUNT),e=f.containsKey(MediaFormat.KEY_PCM_ENCODING)?f.getInteger(MediaFormat.KEY_PCM_ENCODING):AudioFormat.ENCODING_PCM_16BIT;if(pcm!=null){if(rate!=r||channels!=c||encoding!=e)throw new IOException("音轨中途改变采样格式，暂不能完整导入。");return;}rate=r;channels=c;encoding=e;pcm=new SpeechPcmConverter(r,c,waves::write);}
  void accept(ByteBuffer b)throws IOException {b.order(ByteOrder.LITTLE_ENDIAN);int width=encoding==AudioFormat.ENCODING_PCM_16BIT?2:encoding==AudioFormat.ENCODING_PCM_FLOAT||encoding==AudioFormat.ENCODING_PCM_32BIT?4:encoding==AudioFormat.ENCODING_PCM_8BIT?1:encoding==AudioFormat.ENCODING_PCM_24BIT_PACKED?3:0;if(width==0||b.remaining()%(width*channels)!=0)throw new IOException("暂不能完整读取这个PCM音频格式。");int length=b.remaining()/width;if(length>8*1024*1024)throw new IOException("解码单帧过大，暂不能导入。");if(floats.length<length)floats=new float[length];for(int i=0;i<length;i++){if(encoding==AudioFormat.ENCODING_PCM_FLOAT)floats[i]=b.getFloat();else if(width==2)floats[i]=b.getShort()/32768f;else if(width==1)floats[i]=((b.get()&255)-128)/128f;else if(width==3){int n=(b.get()&255)|((b.get()&255)<<8)|(b.get()<<16);floats[i]=n/8388608f;}else floats[i]=b.getInt()/2147483648f;}pcm.process(floats,length);}
 }
 private static final class Waves implements AutoCloseable {
  final Path directory;final Observer observer;final List<Long> samples=new ArrayList<>();RandomAccessFile out;long count,total;byte[] buffer=new byte[65536];int used;
  Waves(Path directory,Observer observer){this.directory=directory;this.observer=observer;}
  void write(short value)throws IOException {if(out==null){if(samples.size()>=24)throw new IOException("音频超过24小时导入上限。");out=new RandomAccessFile(ImportedAudio.part(directory,samples.size()).toFile(),"rw");out.write(new byte[44]);count=0;}
   buffer[used++]=(byte)value;buffer[used++]=(byte)(value>>>8);count++;total++;if(used==buffer.length)flush();if(count==57_600_000L)finishPart();}
  void flush()throws IOException {if(used==0)return;observer.progress("正在保存音频",total/16,0);if(directory.toFile().getUsableSpace()<used+16L*1024*1024)throw new IOException("手机存储空间不足，所选原文件未改变。");out.write(buffer,0,used);used=0;}
  void finishPart()throws IOException {if(out==null)return;flush();ByteBuffer h=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);h.put(new byte[]{'R','I','F','F'}).putInt((int)(count*2+36)).put(new byte[]{'W','A','V','E','f','m','t',' '}).putInt(16).putShort((short)1).putShort((short)1).putInt(16000).putInt(32000).putShort((short)2).putShort((short)16).put(new byte[]{'d','a','t','a'}).putInt((int)(count*2));out.seek(0);out.write(h.array());out.getFD().sync();out.close();out=null;samples.add(count);}
  List<Long> finish()throws IOException {finishPart();return new ArrayList<>(samples);}
  public void close()throws IOException {if(out!=null){out.close();out=null;}}
 }
}
