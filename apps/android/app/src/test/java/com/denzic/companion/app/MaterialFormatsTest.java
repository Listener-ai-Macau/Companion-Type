package com.denzic.companion.app;
import com.denzic.companion.mobile.MeetingDocumentSections;
import org.json.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.io.*;
import java.util.zip.*;

public final class MaterialFormatsTest {
    interface Work{void run()throws Exception;}
    static void check(boolean b,String why){if(!b)throw new AssertionError(why);}
    static void rejects(Work w)throws Exception{try{w.run();}catch(IOException expected){return;}throw new AssertionError("Expected explicit refusal");}
    static String repeat(String s,int n){StringBuilder b=new StringBuilder();for(int i=0;i<n;i++)b.append(s);return b.toString();}
    public static void main(String[] args)throws Exception{
        Path out=Paths.get(args[0]);Files.createDirectories(out);
        String source="The purchase has not been approved. 尚未批准20%的追加费用 <A&B> 😀";
        List<String> wrapped=MaterialLayout.wrap(source,48);check(String.join("",wrapped).equals(source),"wrapping preserves every source code point");
        check(MaterialLayout.wrap(repeat("W",60),68).stream().allMatch(s->s.length()<=17),"wide Latin letters fit");
        List<MeetingDocumentSections.Section> sections=Arrays.asList(
            new MeetingDocumentSections.Section("用户补充", "# 原话不是标题\n=HYPERLINK(\"https://example.invalid\",\"literal\")\n否定：不要把报价当作已批准。",false),
            new MeetingDocumentSections.Section("AI 材料 · 项目汇报", "> AI 材料（需核对）\n## 采购结论\n"+repeat(source+"\n",34)+"## 原文依据\n11月8日前核对报价，未确认就不支付20%。",true));
        List<PresentationDocuments.Slide> pages=PresentationDocuments.pages("公开虚构材料·采购与交付复盘",sections);
        StringBuilder all=new StringBuilder();for(PresentationDocuments.Slide page:pages){check(page.body.size()<=9,"paginated body budget");all.append(page.title);for(String line:page.body)all.append(line);}
        check(all.toString().contains("# 原话不是标题"),"literal source heading preserved");
        check(all.toString().contains("11月8日前核对报价，未确认就不支付20%。"),"citation/deadline/negation retained");
        check(all.toString().split("The purchase has not been approved",-1).length==35,"every repeated body sentence kept");
        check(pages.size()>5,"long saved content paginated");
        try(OutputStream file=Files.newOutputStream(out.resolve("saved-material.pptx"))){PresentationDocuments.write("公开虚构材料·采购与交付复盘",sections,file);}
        try(OutputStream file=Files.newOutputStream(out.resolve("saved-material.xlsx"))){StructuredWorkbook.write("公开虚构材料·采购与交付复盘",sections,file);}
        Files.write(out.resolve("saved-material.mm"),MaterialLayout.mindmap("公开虚构材料·采购与交付复盘",sections).getBytes(StandardCharsets.UTF_8));
        MindmapLayout map=new MindmapLayout("公开示例·采购与交付复盘",sections);for(MindmapLayout.Box box:map.boxes){check(box.x>=0&&box.y>=0&&box.x+box.width<=map.width&&box.y+box.height<=map.height,"all diagram nodes within full bitmap bounds");}
        check(map.width*(long)map.height<=12000000,"bitmap allocation budget");
        Files.write(out.resolve("diagram-plan.json"),new JSONObject().put("width",map.width).put("height",map.height).put("nodes",map.boxes.size()).toString().getBytes(StandardCharsets.UTF_8));
        rejects(()->new MindmapLayout("过长导图",Arrays.asList(new MeetingDocumentSections.Section("长段",repeat("一句话\n",200),false))));
        rejects(()->PresentationDocuments.pages("长文",Arrays.asList(new MeetingDocumentSections.Section("原文",repeat("甲",150001),false))));
        String longTitle=repeat("会议名称需要完整保留",12);StringBuilder titlePages=new StringBuilder();for(PresentationDocuments.Slide page:PresentationDocuments.pages(longTitle,sections))for(String line:page.body)titlePages.append(line);check(titlePages.toString().contains(longTitle),"long title continuation never lost");
        JSONObject material=new JSONObject().put("id","137c45e9-e02f-42ad-b05f-316411cbd203").put("title","已保存周报").put("body","尚未批准追加费用。").put("edited",true).put("result",new JSONObject().put("incomplete",true).put("items",new JSONArray().put(new JSONObject().put("citation",new JSONObject().put("title","公开会议").put("quote","11月8日前先核对报价。\n# literal quote **keep markers**")))));
        JSONArray materials=new JSONArray().put(material);ExportContents.Source sourceOnly=new ExportContents.Source("public","录音标题","library-one",null,null,null,new JSONArray(),materials);
        JSONObject info=sourceOnly.info();check(info.getJSONArray("materials").length()==1,"saved material discoverable without minutes or transcript");
        List<MeetingDocumentSections.Section> selected=sourceOnly.select(new JSONArray().put("material:"+material.getString("id")));String copied=MeetingDocumentSections.plain(selected);
        check(copied.contains("尚未批准")&&copied.contains("11月8日前先核对报价。")&&copied.contains("人工编辑")&&copied.contains("未完成的查询"),"material retains body, citations and disclosures");
        check(copied.contains("# literal quote **keep markers**"),"saved quotation stays verbatim instead of becoming Markdown instructions");
        List<MeetingDocumentSections.Section> wordInput=new ArrayList<>(sections);wordInput.addAll(selected);
        List<MeetingDocumentSections.Section> word=MaterialLayout.wordSections(wordInput);
        check(word.stream().filter(v->v.markdown).count()==1,"multiple saved AI materials remain compatible with existing Word formatter");
        check(MeetingDocumentSections.plain(word).contains("# literal quote **keep markers**"),"Word-compatible selection retains literal citations");
        JSONObject reordered=new JSONObject();List<String> keys=new ArrayList<>(material.keySet());Collections.reverse(keys);for(String k:keys)reordered.put(k,material.get(k));
        check(info.getString("binding").equals(new ExportContents.Source("public","录音标题","library-one",null,null,null,new JSONArray(),new JSONArray().put(reordered)).info().getString("binding")),"JSON field order does not falsely invalidate source");
        JSONObject second=new JSONObject(material.toString()).put("id","4a21a86a-2b19-45d2-a5c9-339ba7fd253a");
        String firstOrder=new ExportContents.Source("public","录音标题","library-one",null,null,null,new JSONArray(),new JSONArray().put(material).put(second)).info().getString("binding");
        String reverseOrder=new ExportContents.Source("public","录音标题","library-one",null,null,null,new JSONArray(),new JSONArray().put(second).put(material)).info().getString("binding");
        check(firstOrder.equals(reverseOrder),"filesystem/list ordering does not falsely invalidate unchanged materials");
        material.put("body","内容已修改");check(!info.getString("binding").equals(sourceOnly.info().getString("binding")),"material modification invalidates prepared source");
        rejects(()->new ExportContents.Source("public","录音标题","library-one",null,null,null,new JSONArray()).select(new JSONArray().put("material:"+material.getString("id"))));
        rejects(()->sourceOnly.select(new JSONArray().put("material:"+material.getString("id")).put("material:"+material.getString("id"))));
        PreparedExports prepared=new PreparedExports(out.resolve("cache"));JSONObject meta=new JSONObject().put("key","public").put("libraryToken","library-one").put("warnings",new JSONArray());
        PreparedExports.Entry fixed=prepared.create(meta,"saved.pptx","application/vnd.openxmlformats-officedocument.presentationml.presentation",copied,stream->PresentationDocuments.write("公开材料",selected,stream));
        ByteArrayOutputStream saved=new ByteArrayOutputStream();prepared.write(prepared.load(fixed.id(),true),saved);check(Arrays.equals(saved.toByteArray(),Files.readAllBytes(fixed.file)),"saving/sharing uses identical prepared binary");
        rejects(()->prepared.create(meta,"failed.png","image/png",copied,stream->{stream.write(1);throw new IOException("source changed after rendering");}));
        try(java.util.stream.Stream<Path> paths=Files.list(prepared.root)){check(paths.noneMatch(p->p.getFileName().toString().startsWith(".prepare-")),"failed render never publishes a partial file");}
        System.out.println("PASS Android production exporters: exact text/citations/disclosures; literal headings; long-title and content pagination; PPTX/XLSX/MM files; bitmap layout limits/bounds (not actual Android drawing); saved-material-only selection; canonical source binding/order/change/deletion/duplicates; immutable handoff and failed publication cleanup. Slides="+pages.size()+", diagram="+map.width+"x"+map.height);
    }
}
