package com.denzic.companion.mobile;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.*;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.*;

/** Selected saved content. Literals never become Markdown instructions or headings. */
public final class MeetingDocumentSections {
    private MeetingDocumentSections(){}
    public static final class Section{
        public final String title,text;public final boolean markdown;
        public Section(String title,String text,boolean markdown){
            if(title==null||title.trim().isEmpty()||text==null||text.trim().isEmpty())throw new IllegalArgumentException("nonempty section required");
            this.title=title;this.text=text;this.markdown=markdown;
        }
    }
    public static String plain(List<Section> sections){
        StringBuilder out=new StringBuilder();for(Section s:sections){
            if(out.length()>0)out.append("\n\n");out.append(s.title).append('\n');
            if(s.markdown){for(MeetingPdfContent.Block b:MeetingPdfContent.markdown(s.text))out.append(b.text).append('\n');}
            else out.append(s.text);
        }return out.toString();
    }
    private static String fence(String value){
        int longest=0,run=0;for(int i=0;i<value.length();i++){if(value.charAt(i)=='`'){run++;longest=Math.max(longest,run);}else run=0;}
        StringBuilder marker=new StringBuilder();for(int i=0;i<Math.max(3,longest+1);i++)marker.append('`');return marker.toString();
    }
    public static String markdown(List<Section> sections){
        StringBuilder out=new StringBuilder();for(Section s:sections){
            if(out.length()>0)out.append("\n\n");out.append("## ").append(s.title).append("\n\n");
            if(s.markdown)out.append(s.text);else{String f=fence(s.text);out.append(f).append("text\n").append(s.text).append('\n').append(f);}
        }return out.toString();
    }
    private static final String W="http://schemas.openxmlformats.org/wordprocessingml/2006/main";
    private static Element element(Document d,String name){return d.createElementNS(W,"w:"+name);}
    private static Element paragraph(Document d,String text,String style){
        Element p=element(d,"p");if(style!=null){Element pr=element(d,"pPr"),st=element(d,"pStyle");st.setAttributeNS(W,"w:val",style);pr.appendChild(st);p.appendChild(pr);}
        Element r=element(d,"r"),t=element(d,"t");t.setAttributeNS("http://www.w3.org/XML/1998/namespace","xml:space","preserve");
        StringBuilder safe=new StringBuilder();for(int i=0;i<text.length();i++){char c=text.charAt(i);safe.append((c<32&&c!='\n'&&c!='\r'&&c!='\t')||c=='\ufffe'||c=='\uffff'?'\ufffd':c);}
        t.appendChild(d.createTextNode(safe.toString()));r.appendChild(t);p.appendChild(r);return p;
    }
    /** Reuse the shared native Word writer's styles, numbered lists, footer and
     * minutes formatting; append literal source sections as escaped XML text. */
    public static byte[] word(String title,List<Section> sections)throws IOException{
        if(sections==null||sections.isEmpty())throw new IOException("请选择导出内容。");
        Section md=null;for(Section s:sections)if(s.markdown){if(md!=null)throw new IOException("只支持一份纪要正文。");md=s;}
        byte[] base=NativeMeetingDocuments.wordContent(title,md==null?"Companion export placeholder":md.text);
        try{
            Map<String,byte[]> files=new LinkedHashMap<>();try(ZipInputStream in=new ZipInputStream(new ByteArrayInputStream(base))){ZipEntry e;byte[] buffer=new byte[16384];while((e=in.getNextEntry())!=null){ByteArrayOutputStream out=new ByteArrayOutputStream();int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);files.put(e.getName(),out.toByteArray());}}
            DocumentBuilderFactory factory=DocumentBuilderFactory.newInstance();factory.setNamespaceAware(true);factory.setExpandEntityReferences(false);
            Document document=factory.newDocumentBuilder().parse(new ByteArrayInputStream(files.get("word/document.xml")));
            Element body=(Element)document.getElementsByTagNameNS(W,"body").item(0);Node titleNode=body.getFirstChild(),settings=null;List<Node> minutes=new ArrayList<>();
            for(Node n=body.getFirstChild();n!=null;n=n.getNextSibling()){if(n instanceof Element&&"sectPr".equals(n.getLocalName()))settings=n.cloneNode(true);else if(n!=titleNode)minutes.add(n.cloneNode(true));}
            while(body.hasChildNodes())body.removeChild(body.getFirstChild());body.appendChild(titleNode.cloneNode(true));
            for(Section s:sections){body.appendChild(paragraph(document,s.title,"Heading1"));if(s.markdown){for(Node n:minutes)body.appendChild(n.cloneNode(true));}else{
                String[] lines=s.text.split("\\r?\\n",-1);boolean compact=s.text.length()<=1500&&lines.length<=8;
                for(int i=0;i<lines.length;i++){Element p=paragraph(document,lines[i],null);if(compact&&i<lines.length-1){Element properties=element(document,"pPr");properties.appendChild(element(document,"keepNext"));p.insertBefore(properties,p.getFirstChild());}body.appendChild(p);}
            }}
            if(settings!=null)body.appendChild(settings);ByteArrayOutputStream xml=new ByteArrayOutputStream();Transformer transformer=TransformerFactory.newInstance().newTransformer();transformer.setOutputProperty(OutputKeys.ENCODING,"UTF-8");transformer.transform(new DOMSource(document),new StreamResult(xml));files.put("word/document.xml",xml.toByteArray());
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(ZipOutputStream zip=new ZipOutputStream(bytes)){for(Map.Entry<String,byte[]> f:files.entrySet()){zip.putNextEntry(new ZipEntry(f.getKey()));zip.write(f.getValue());zip.closeEntry();}}return bytes.toByteArray();
        }catch(Exception e){throw new IOException("Word文档生成失败；已保存资料保持不变。",e);}
    }
}
