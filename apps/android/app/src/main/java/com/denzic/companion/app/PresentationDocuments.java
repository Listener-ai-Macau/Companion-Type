package com.denzic.companion.app;

import com.denzic.companion.mobile.MeetingDocumentSections;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;

/** Editable PresentationML. No generation service, model or external resources. */
final class PresentationDocuments {
    static final int MAX_SLIDES=250,BODY_LINES=9;
    static final class Slide {final String title;final List<String> body=new ArrayList<>();Slide(String t){title=t;}}
    static List<Slide> pages(String title,List<MeetingDocumentSections.Section> sections)throws IOException{
        List<Slide> slides=new ArrayList<>();slides.add(new Slide(shortTitle(title)));
        if(title.codePointCount(0,title.length())>48)slides.add(append(slides,new Slide("会议名称（续）"),MaterialLayout.wrap(title,140)));
        Slide current=null;
        for(MaterialLayout.Line line:MaterialLayout.lines(sections)){
            if(line.level>0){if(current!=null)slides.add(current);current=new Slide(shortTitle(line.text));
                if(line.text.codePointCount(0,line.text.length())>48)current=append(slides,current,MaterialLayout.wrap(line.text,140));
            }else{
                if(current==null)current=new Slide("会议材料");
                if(line.text.trim().isEmpty()&&(current.body.isEmpty()||current.body.get(current.body.size()-1).isEmpty()))continue;
                current=append(slides,current,MaterialLayout.wrap(line.text,140));
            }
            if(slides.size()>MAX_SLIDES)throw tooLarge();
        }
        if(current!=null)slides.add(current);if(slides.size()>MAX_SLIDES)throw tooLarge();return slides;
    }
    private static IOException tooLarge(){return new IOException("所选内容超过250页，请减少内容或分批导出PPTX。");}
    private static String shortTitle(String text){return text.codePointCount(0,text.length())<=48?text:text.substring(0,text.offsetByCodePoints(0,22))+"…";}
    private static Slide append(List<Slide> slides,Slide current,List<String> lines)throws IOException{
        for(String line:lines){if(current.body.size()==BODY_LINES){slides.add(current);current=new Slide(current.title);}current.body.add(line);if(slides.size()>MAX_SLIDES)throw tooLarge();}return current;
    }
    static void write(String title,List<MeetingDocumentSections.Section> sections,OutputStream out)throws IOException{
        List<Slide> slides=pages(title,sections);Map<String,String> parts=Presentation054Base.parts();
        StringBuilder types=new StringBuilder(),ids=new StringBuilder(),rels=new StringBuilder();
        for(int i=1;i<=slides.size();i++){
            types.append("<Override PartName=\"/ppt/slides/slide").append(i).append(".xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slide+xml\"/>");
            ids.append("<p:sldId id=\"").append(255+i).append("\" r:id=\"rId").append(i).append("\"/>");
            rels.append("<Relationship Id=\"rId").append(i).append("\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide").append(i).append(".xml\"/>");
            parts.put("ppt/slides/slide"+i+".xml",slide(slides.get(i-1),i,slides.size()));
            parts.put("ppt/slides/_rels/slide"+i+".xml.rels",Presentation054Base.SLIDE_RELS);
        }
        parts.put("[Content_Types].xml",Presentation054Base.CONTENT_TYPES.replace("@@SLIDES@@",types));
        parts.put("ppt/presentation.xml",Presentation054Base.PRESENTATION.replace("@@SLIDES@@",ids));
        parts.put("ppt/_rels/presentation.xml.rels",Presentation054Base.PRESENTATION_RELS.replace("@@SLIDES@@",rels));
        try(ZipOutputStream zip=new ZipOutputStream(out)){for(Map.Entry<String,String> p:parts.entrySet()){ZipEntry e=new ZipEntry(p.getKey());e.setTime(0);zip.putNextEntry(e);zip.write(p.getValue().getBytes(StandardCharsets.UTF_8));zip.closeEntry();}}
    }
    private static String box(int id,String name,int x,int y,int w,int h,List<String> lines,int size,boolean bold,String color){
        StringBuilder ps=new StringBuilder();
        for(String text:lines)ps.append("<a:p><a:pPr><a:lnSpc><a:spcPts val=\"").append(size>=4000?5200:size>=3000?3800:size>=1800?2800:1400).append("\"/></a:lnSpc></a:pPr><a:r><a:rPr lang=\"zh-CN\" sz=\"").append(size).append("\" b=\"").append(bold?1:0).append("\"><a:solidFill><a:srgbClr val=\"").append(color).append("\"/></a:solidFill><a:latin typeface=\"Microsoft YaHei\"/><a:ea typeface=\"Microsoft YaHei\"/></a:rPr><a:t xml:space=\"preserve\">").append(MaterialLayout.xml(text)).append("</a:t></a:r><a:endParaRPr lang=\"zh-CN\" sz=\"").append(size).append("\"/></a:p>");
        return "<p:sp><p:nvSpPr><p:cNvPr id=\""+id+"\" name=\""+name+"\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x=\""+x+"\" y=\""+y+"\"/><a:ext cx=\""+w+"\" cy=\""+h+"\"/></a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap=\"none\" lIns=\"0\" tIns=\"0\" rIns=\"0\" bIns=\"0\"><a:noAutofit/></a:bodyPr><a:lstStyle/>"+ps+"</p:txBody></p:sp>";
    }
    private static String slide(Slide slide,int page,int total){
        boolean cover=page==1;List<String> title=MaterialLayout.wrap(slide.title,cover?72:96);
        int bodyY=Math.max(1750000,500000+title.size()*38*12700+160000);
        String shapes=box(2,"标题",680000,cover?1800000:500000,10800000,cover?2200000:1500000,title,cover?4200:3200,true,"172B40")
            +box(3,"保存的正文",710000,bodyY,10700000,6350000-bodyY-180000,slide.body.isEmpty()?Collections.singletonList(""):slide.body,2000,false,"27364A")
            +box(4,"页码",680000,6350000,10800000,220000,Collections.singletonList(page+" / "+total),1000,false,"667589");
        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><p:sld xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\"><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val=\"F8FAFC\"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree>"+Presentation054Base.GROUP+shapes+"</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>";
    }
}
