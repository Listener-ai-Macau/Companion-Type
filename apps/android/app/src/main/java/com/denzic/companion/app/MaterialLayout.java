package com.denzic.companion.app;

import com.denzic.companion.mobile.MeetingDocumentSections;
import java.io.IOException;
import java.util.*;
import java.util.regex.*;

/** Layout only: literal transcript/translation lines never become structural headings. */
final class MaterialLayout {
    static final class Line {
        final String text; final int level;
        Line(String t,int l){text=t;level=l;}
    }
    static List<Line> lines(List<MeetingDocumentSections.Section> sections)throws IOException{
        if(sections==null||sections.isEmpty())throw new IOException("请先选择已保存内容。");
        List<Line> lines=new ArrayList<>();int count=0;
        for(MeetingDocumentSections.Section section:sections){
            count+=section.text.codePointCount(0,section.text.length());
            if(count>150000)throw new IOException("所选内容过长，请减少内容或分批导出。");
            lines.add(new Line(section.title,1));String fence=null;
            for(String line:section.text.split("\\r?\\n",-1)){
                String structural=line.trim();
                if(section.markdown){
                    // A quoted saved heading is presentation structure, never a new fact.
                    while(structural.startsWith(">"))structural=structural.substring(1).trim();
                    Matcher f=Pattern.compile("^(`{3,}|~{3,}).*$").matcher(structural);
                    if(f.matches()){
                        String mark=f.group(1);
                        if(fence==null){fence=mark;continue;}
                        if(mark.charAt(0)==fence.charAt(0)&&mark.length()>=fence.length()){fence=null;continue;}
                    }
                    if(fence==null){
                        Matcher h=Pattern.compile("^(#{1,6})\\s+(.+)$").matcher(structural);
                        if(h.matches()){lines.add(new Line(h.group(2),h.group(1).length()+1));continue;}
                    }
                }
                lines.add(new Line(line,0));
            }
        }
        return lines;
    }
    static int units(int cp){
        if(cp=='\t')return 16;
        if(cp>=0x0300&&cp<=0x036f||cp>=0xfe00&&cp<=0xfe0f||cp==0x200d)return 0;
        if(cp<128){if("WMwm@#%".indexOf(cp)>=0)return 4;return Character.isWhitespace(cp)||"ilI.,:;!'`|".indexOf(cp)>=0?2:3;}
        return cp<=0x024f?3:4;
    }
    /** Existing native Word styling accepts one Markdown section; keep further
     * saved sections readable and complete, with literal citations untouched. */
    static List<MeetingDocumentSections.Section> wordSections(List<MeetingDocumentSections.Section> sections)throws IOException{
        boolean styled=false;List<MeetingDocumentSections.Section> result=new ArrayList<>();
        for(MeetingDocumentSections.Section section:sections){
            if(!section.markdown||!styled){result.add(section);styled|=section.markdown;continue;}
            List<Line> lines=lines(Collections.singletonList(section));StringBuilder body=new StringBuilder();
            for(int i=1;i<lines.size();i++){if(i>1)body.append('\n');body.append(lines.get(i).text);}
            result.add(new MeetingDocumentSections.Section(section.title,body.toString(),false));
        }return result;
    }
    static List<String> wrap(String text,int width){
        List<String> result=new ArrayList<>();
        for(String raw:text.split("\\r?\\n",-1)){
            if(raw.isEmpty()){result.add("");continue;}
            int start=0;
            while(start<raw.length()){
                int end=start,size=0,lastSpace=-1;
                while(end<raw.length()){
                    int cp=raw.codePointAt(end),u=units(cp);if(size+u>width&&end>start)break;
                    size+=u;end+=Character.charCount(cp);if(cp==' ')lastSpace=end;
                }
                if(end<raw.length()&&lastSpace>start&&lastSpace-start>(end-start)/2)end=lastSpace;
                result.add(raw.substring(start,end));start=end;
            }
        }
        return result;
    }
    static String xml(String text){
        StringBuilder b=new StringBuilder();
        for(int i=0;i<text.length();){int cp=text.codePointAt(i);i+=Character.charCount(cp);
            if(cp=='&')b.append("&amp;");else if(cp=='<')b.append("&lt;");else if(cp=='>')b.append("&gt;");
            else if(cp=='\"')b.append("&quot;");else if(cp=='\'')b.append("&apos;");
            else if(cp==9||cp==10||cp==13||cp>=32&&cp<=0xD7FF||cp>=0xE000&&cp<=0xFFFD||cp>=0x10000&&cp<=0x10FFFF)b.appendCodePoint(cp);
            else b.append('\uFFFD');
        }return b.toString();
    }
    static final class Node {
        final String text;final List<Node> children=new ArrayList<>();final int depth;
        Node(String t,int d){text=t;depth=d;}
    }
    static Node tree(String title,List<MeetingDocumentSections.Section> sections)throws IOException{return tree(title,sections,true);}
    static Node tree(String title,List<MeetingDocumentSections.Section> sections,boolean image)throws IOException{
        Node root=new Node(title,0);List<Node> stack=new ArrayList<>();stack.add(root);int nodes=1,chars=title.length();
        for(Line l:lines(sections)){
            if(l.text.trim().isEmpty())continue;
            if(l.level>0){while(stack.size()>1&&stack.get(stack.size()-1).depth>=l.level)stack.remove(stack.size()-1);
                Node n=new Node(l.text,l.level);stack.get(stack.size()-1).children.add(n);stack.add(n);
            }else stack.get(stack.size()-1).children.add(new Node(l.text,99));
            nodes++;chars+=l.text.length();
            if(image&&(nodes>180||chars>12000))throw new IOException("导图内容较长，请只选需要的纪要或材料；完整长文可保存为Word或TXT。");
        }return root;
    }
    static String mindmap(String title,List<MeetingDocumentSections.Section> sections)throws IOException{
        Node tree=tree(title,sections,false);return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><map version=\"1.0.1\">"+nodeXml(tree)+"</map>";
    }
    private static String nodeXml(Node node){StringBuilder b=new StringBuilder("<node TEXT=\"").append(xml(node.text)).append("\">");for(Node n:node.children)b.append(nodeXml(n));return b.append("</node>").toString();}
}
