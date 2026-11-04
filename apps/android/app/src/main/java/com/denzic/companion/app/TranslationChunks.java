package com.denzic.companion.app;

import java.util.ArrayList;
import java.util.List;

/** Bounded, ordered long-text translation; source is never changed or persisted. */
final class TranslationChunks {
    static final int MAX_SOURCE=60000, CHUNK_SIZE=4000, MAX_RESULT=200000;
    interface Translate { String apply(String chunk) throws Exception; }
    interface Progress { void report(int completed,int total); }
    static List<String> split(String text) {
        if(text==null || text.trim().isEmpty())throw new IllegalArgumentException("请先完成转写。");
        if(text.length()>MAX_SOURCE)throw new IllegalArgumentException("转写超过 60,000 个字符，暂不能翻译；原文仍保留。");
        List<String> result=new ArrayList<>();int start=0;
        while(start<text.length()) {
            int end=Math.min(text.length(),start+CHUNK_SIZE);
            if(end<text.length()) {
                int line=text.lastIndexOf('\n',end-1);
                if(line>=start+CHUNK_SIZE/2)end=line+1;
                if(end>start && Character.isHighSurrogate(text.charAt(end-1)) && Character.isLowSurrogate(text.charAt(end)))end--;
            }
            if(end<=start)throw new IllegalStateException("无法安全分段；原文仍保留。");
            result.add(text.substring(start,end));start=end;
        }
        return result;
    }
    static String run(String text,Translate translate,Progress progress) throws Exception {
        List<String> chunks=split(text);StringBuilder output=new StringBuilder();
        for(int i=0;i<chunks.size();i++) {
            String chunk=chunks.get(i),part;
            try { part=chunk.trim().isEmpty()?chunk:translate.apply(chunk); }
            catch(Exception failure) {throw new IllegalStateException("第 "+(i+1)+"/"+chunks.size()+" 段翻译未完成；未显示不完整译文，原文仍保留。重试可能重新发送已处理的文字。");}
            if(part==null||part.trim().isEmpty()&&!chunk.trim().isEmpty()||output.length()+part.length()+2>MAX_RESULT)
                throw new IllegalStateException("译文为空或过长，未显示不完整译文；原文仍保留。");
            if(output.length()>0&&!chunk.trim().isEmpty())output.append("\n\n");output.append(part);
            if(progress!=null)progress.report(i+1,chunks.size());
        }
        return output.toString();
    }
    private TranslationChunks() {}
}
