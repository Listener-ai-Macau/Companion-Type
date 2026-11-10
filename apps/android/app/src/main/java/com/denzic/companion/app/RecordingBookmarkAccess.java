package com.denzic.companion.app;
import com.denzic.companion.mobile.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Device marks remain device metadata; only the native decoder maps them to playable audio. */
final class RecordingBookmarkAccess {
    private static final long SAFE=9007199254740991L;
    static String binding(RecordingLibrary.Session session)throws Exception{
        if(session.imported!=null)return ImportedAudio.hash(session.imported.fingerprint());
        MessageDigest hash=MessageDigest.getInstance("SHA-256");
        for(RecordingLibrary.Entry entry:session.segments){byte[] wire=entry.descriptor.wireBytes();wire[95]=0;Arrays.fill(wire,108,112,(byte)0);hash.update(wire);}
        StringBuilder value=new StringBuilder();for(byte b:hash.digest())value.append(String.format(Locale.ROOT,"%02x",b&255));return value.toString();
    }
    static JSONObject describe(String key,String libraryToken,String binding,NativeAudio.VerifiedPrefix source)throws Exception{
        if(source==null||source.encodedSamples<0||source.encodedSamples>SAFE||source.bookmarks.size()>10000)throw new IOException("重点资料无法完整读取，原录音已保留。");
        JSONArray marks=new JSONArray();Set<String> ids=new HashSet<>();
        for(NativeAudio.SourceBookmark mark:source.bookmarks){
            if(mark.sequence<0||mark.sourceSamples<0||mark.sourceSamples>source.encodedSamples||mark.elapsedMillis<0||mark.elapsedMillis>SAFE)throw new IOException("重点位置无效，原录音已保留。");
            String id=mark.sequence+":"+mark.sourceSamples+":"+mark.elapsedMillis;if(!ids.add(id))throw new IOException("重点标识重复，暂不能确定回听位置。");
            marks.put(new JSONObject().put("sequence",Long.toString(mark.sequence)).put("sourceSamples",mark.sourceSamples).put("elapsedMs",mark.elapsedMillis));
        }
        return new JSONObject().put("key",key).put("libraryToken",libraryToken).put("binding",binding).put("complete",source.captureComplete).put("marks",marks);
    }
    static final class Playback {
        final int part,offsetMs;final long positionMs;
        Playback(int part,int offset,long position){this.part=part;offsetMs=offset;positionMs=position;}
    }
    static Playback playback(NativeAudio.PartsResult parts,String sequence,long sourceSamples,long elapsedMs)throws Exception{
        if(parts==null||parts.samples<=0||parts.samples>SAFE)throw new IOException("当前已保存音频的时长无法确认。");
        NativeAudio.Bookmark found=null;
        for(NativeAudio.Bookmark mark:parts.bookmarks)if(Long.toString(mark.sequence).equals(sequence)&&mark.sourceSamples==sourceSamples&&mark.elapsedMillis==elapsedMs){if(found!=null)throw new IOException("这条重点不能唯一定位，请重新读取重点。");found=mark;}
        if(found==null)throw new IOException("这条重点尚未对应到已保存音频，请重新读取或完成接收后重试。");
        long sample=found.playbackSamples;if(sample<0||sample>=parts.samples)throw new IOException("重点位于当前可用录音的末尾，暂没有可回听内容。");
        for(int i=0;i<parts.parts.size();i++){
            NativeAudio.Part part=parts.parts.get(i);if(part.firstSample<0||part.samples<=0||part.firstSample>SAFE-part.samples)throw new IOException("已保存音频的位置无法确认。");
            if(sample>=part.firstSample&&sample-part.firstSample<part.samples){long offset=(sample-part.firstSample)/16;if(offset>Integer.MAX_VALUE)throw new IOException("当前音频分段过长，暂不能定位。");return new Playback(i,(int)offset,sample/16);}
        }
        throw new IOException("重点所在的音频分段尚不可用，请完成接收后重试。");
    }
    static byte[] text(String title,JSONObject data)throws Exception{
        StringBuilder out=new StringBuilder(title).append("\n设备重点清单\n\n重点由录音卡按键标记，不是 AI 结论。时间为设备记录的录音经过时间；暂停或缺失分段可能使回听时间不同。\n");
        if(!data.getBoolean("complete"))out.append("当前只包含已接收分段中的重点，完整录音可能还有其他重点。\n");
        JSONArray marks=data.getJSONArray("marks");if(marks.length()==0)throw new IOException("当前已保存的录音中没有可导出的设备重点。");
        for(int i=0;i<marks.length();i++){long seconds=marks.getJSONObject(i).getLong("elapsedMs")/1000;out.append(String.format(Locale.ROOT,"\n%02d:%02d:%02d  设备重点 %d",seconds/3600,seconds/60%60,seconds%60,i+1));}
        return out.append('\n').toString().getBytes(StandardCharsets.UTF_8);
    }
    private RecordingBookmarkAccess(){}
}
