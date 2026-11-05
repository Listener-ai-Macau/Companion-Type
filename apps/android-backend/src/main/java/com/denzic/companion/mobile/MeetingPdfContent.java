package com.denzic.companion.mobile;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Presentation of saved text only. Never changes a stored meeting or calls a service. */
final class MeetingPdfContent {
    static final int BODY=0,HEADING=1,SECTION=2,QUOTE=3,BULLET=4,CODE=5,DETAIL=6;
    static final class Block {
        final int kind;final String text;
        Block(int kind,String text){this.kind=kind;this.text=text;}
    }
    private static final Pattern HEADING_LINE=Pattern.compile("^#{1,6}\\s+(.+?)\\s*$");
    private static final Pattern BULLET_LINE=Pattern.compile("^\\s*[-*+]\\s+(.+)$");
    private static final Pattern TASK_FIELDS=Pattern.compile("^(.+) \\(owner: (.+), due: (.+)\\)$");
    private MeetingPdfContent(){}

    static List<Block> markdown(String markdown){
        String[] lines=readableMetadata(markdown).split("\\r?\\n",-1);
        List<Block> result=new ArrayList<>();String fence=null;
        for(String line:lines){
            String trimmed=line.trim();
            if(trimmed.startsWith("```")||trimmed.startsWith("~~~")){
                String marker=trimmed.substring(0,3);
                if(fence==null){fence=marker;continue;}
                if(fence.equals(marker)){fence=null;continue;}
            }
            if(fence!=null){result.add(new Block(CODE,line.isEmpty()?" ":line));continue;}
            if(trimmed.isEmpty())continue;
            Matcher heading=HEADING_LINE.matcher(trimmed),bullet=BULLET_LINE.matcher(line);
            if(heading.matches())result.add(new Block(HEADING,inline(heading.group(1))));
            else if(trimmed.startsWith(">"))result.add(new Block(QUOTE,inline(trimmed.substring(1).trim())));
            else if(bullet.matches()){
                String text=bullet.group(1);
                boolean task=text.matches("^\\[[xX ]\\]\\s+.*");
                if(text.matches("^\\[[xX]\\]\\s+.*"))text="已完成 · "+text.substring(4);
                else if(text.startsWith("[ ] "))text="待办 · "+text.substring(4);
                Matcher fields=TASK_FIELDS.matcher(text);
                // This is the existing serialized checklist field syntax. Do not
                // reinterpret arbitrary prose or an ambiguous delimiter as a person.
                if(task&&fields.matches()&&text.indexOf(", due: ")==text.lastIndexOf(", due: ")){
                    result.add(new Block(BULLET,inline(fields.group(1))));
                    result.add(new Block(DETAIL,"负责人："+fields.group(2)));
                    result.add(new Block(DETAIL,"时间："+fields.group(3)));
                }else result.add(new Block(BULLET,inline(text)));
            }else result.add(new Block(BODY,inline(line)));
        }
        return result;
    }
    private static String inline(String text){
        return text.replaceAll("\\*\\*([^*]+)\\*\\*","$1").replaceAll("__([^_]+)__","$1");
    }

    /** Recognize the COMPLETE old generated header, even after a recording was renamed.
     * Ordinary prose, code and incomplete lookalikes stay verbatim. Only machine metadata
     * is replaced with a readable explanation; all meeting sections remain in order. */
    static String readableMetadata(String markdown){
        String[] lines=markdown.split("\\r?\\n",-1);String fence=null;
        String[] old={"## Summary","## Decisions","## Action Items","## Questions","## Keywords"};
        String[] labels={"## 会议摘要","## 讨论结论（需核对）","## 行动事项","## 待解问题","## 关键词"};
        for(int start=0;start+7<lines.length;start++){
            String line=lines[start].trim();
            if(line.startsWith("```")||line.startsWith("~~~")){String marker=line.substring(0,3);if(fence==null)fence=marker;else if(fence.equals(marker))fence=null;continue;}
            if(fence!=null||!lines[start].startsWith("# ")||!lines[start+1].isEmpty()
                ||!lines[start+2].startsWith("Generated: ")||!lines[start+3].startsWith("Duration: ")
                ||!lines[start+4].startsWith("Source: ")||!lines[start+5].startsWith("Minutes engine: ")
                ||!lines[start+6].isEmpty()||!lines[start+7].equals(old[0]))continue;
            int[] positions=new int[old.length];positions[0]=start+7;boolean complete=true;String nestedFence=null;
            for(int section=1;section<old.length;section++){
                positions[section]=-1;
                for(int at=positions[section-1]+1;at<lines.length;at++){
                    String current=lines[at].trim();
                    if(current.startsWith("```")||current.startsWith("~~~")){String marker=current.substring(0,3);if(nestedFence==null)nestedFence=marker;else if(nestedFence.equals(marker))nestedFence=null;continue;}
                    if(nestedFence==null&&lines[at].equals(old[section])){positions[section]=at;break;}
                }
                if(positions[section]<0){complete=false;break;}
            }
            if(!complete)continue;
            String engine=lines[start+5].substring("Minutes engine: ".length());
            // Do not turn a test/unknown timestamp or a segment's duration into a
            // claim about the recording. Exact metadata stays in the saved source.
            lines[start]="> 生成说明："+(engine.startsWith("llm_")?"AI 整理":engine.startsWith("rules_")?"本地整理":"已保存的整理结果")+"。内容请结合原文核对；原始生成信息保留在本机资料中。";
            for(int at=start+1;at<start+7;at++)lines[at]="";
            for(int section=0;section<positions.length;section++)lines[positions[section]]=labels[section];
            break;
        }
        return String.join("\n",lines);
    }
}
