package com.denzic.companion.app;

import java.io.IOException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Literal, local search. Never edits stored text or invokes a model/service. */
final class MeetingLibrarySearch {
    private static final Pattern MINUTES_PREFIX=Pattern.compile("(?:#{1,6}\\s+|[-*+]\\s+|>\\s+)");
    interface Reader { SavedText read(String key,String source) throws IOException; }
    static final class SavedText {
        final String text;final boolean stale;
        SavedText(String text,boolean stale){this.text=text;this.stale=stale;}
    }
    static final class Match {
        final String source,snippet;final int start,end;final boolean stale;
        Match(String source,String snippet,int start,int end,boolean stale){this.source=source;this.snippet=snippet;this.start=start;this.end=end;this.stale=stale;}
    }
    static final class Result {
        final Match match;final int unreadable;
        Result(Match match,int unreadable){this.match=match;this.unreadable=unreadable;}
    }
    private final Pattern pattern;
    private final boolean fullText;
    MeetingLibrarySearch(String query,boolean fullText){
        if(query==null||query.trim().isEmpty()||query.length()>120)throw new IllegalArgumentException("请输入1至120个字符");
        pattern=Pattern.compile(Pattern.quote(query.trim()),Pattern.CASE_INSENSITIVE|Pattern.UNICODE_CASE);
        this.fullText=fullText;
    }
    Result find(String key,String title,Reader reader){
        Match match=match(title,"title",false);if(match!=null||!fullText)return new Result(match,0);
        int unreadable=0;
        for(String source:new String[]{"transcript","minutes"}){
            try{
                SavedText saved=reader.read(key,source);
                if(saved!=null&&(match=match(saved.text,source,saved.stale))!=null)return new Result(match,unreadable);
            }catch(IOException failure){unreadable++;}
        }
        return new Result(null,unreadable);
    }
    private Match match(String text,String source,boolean stale){
        if(text==null)return null;Matcher found=pattern.matcher(text);if(!found.find())return null;
        int lineStart=text.lastIndexOf('\n',found.start()-1)+1;
        int from=Math.max(lineStart,found.start()-28),to=Math.min(text.length(),found.end()+60);
        int lineEnd=text.indexOf('\n',found.end());if(lineEnd>=0)to=Math.min(to,lineEnd);
        if(source.equals("minutes")&&from==lineStart){
            Matcher marker=MINUTES_PREFIX.matcher(text).region(from,text.length());
            if(marker.lookingAt()&&marker.end()<=found.start())from=marker.end();
        }
        if(from>0&&Character.isLowSurrogate(text.charAt(from))&&Character.isHighSurrogate(text.charAt(from-1)))from--;
        if(to<text.length()&&to>0&&Character.isHighSurrogate(text.charAt(to-1))&&Character.isLowSurrogate(text.charAt(to)))to++;
        String prefix=from>0?"…":"",suffix=to<text.length()?"…":"";
        return new Match(source,prefix+text.substring(from,to)+suffix,prefix.length()+found.start()-from,prefix.length()+found.end()-from,stale);
    }
}
