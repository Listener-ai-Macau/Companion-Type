package com.denzic.companion.app;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.io.IOException;

/** Real Java matching results for the browser contract, using explicitly fictional records. */
public final class MeetingLibrarySearchFixtures {
    static String encoded(String text){return Base64.getEncoder().encodeToString(text.getBytes(StandardCharsets.UTF_8));}
    public static void main(String[] args){
        String[] keys={"m1","m2","m3"},titles={"经营复盘","设计讨论","资料受损"};
        String[] transcripts={"嗯周五补充土豆。土豆需要确认，字面 .* [1] 也保留。","小陈检查应用图标。",""};
        String[] minutes={"## 行动事项\n- 核对仓储。","## 待解问题\n- 日历的故障应对措施待确认。",""};
        String[] queries={"土豆","经营","日历","不存在","故障",".*","嗯"};
        for(String query:queries)for(String scope:new String[]{"all","title"}){
            MeetingLibrarySearch search=new MeetingLibrarySearch(query,scope.equals("all"));
            for(int i=0;i<keys.length;i++){
                final int index=i;
                MeetingLibrarySearch.Result found=search.find(keys[i],titles[i],(key,source)->{
                    if(index==2&&source.equals("transcript"))throw new IOException("fictional damaged component");
                    return new MeetingLibrarySearch.SavedText(source.equals("transcript")?transcripts[index]:minutes[index],source.equals("minutes")&&index==1);
                });
                MeetingLibrarySearch.Match m=found.match;
                System.out.println(encoded(query)+"\t"+scope+"\t"+keys[i]+"\t"+encoded(titles[i])+"\t"+(m==null?"-":m.source)+"\t"+encoded(m==null?"":m.snippet)+"\t"+(m==null?0:m.start)+"\t"+(m==null?0:m.end)+"\t"+(m!=null&&m.stale)+"\t"+found.unreadable);
            }
        }
    }
}
