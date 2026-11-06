package com.denzic.companion.app;
import com.denzic.companion.mobile.MeetingDocumentSections;
import java.util.*;
import java.util.zip.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Saved text as inline strings. Never interpret a source line as an Excel formula. */
final class StructuredWorkbook {
    static void write(String title,List<MeetingDocumentSections.Section> sections,OutputStream out)throws IOException{
        MaterialLayout.lines(sections); // common explicit content budget, no truncation
        StringBuilder data=new StringBuilder();int row=1;
        data.append(row(row++,"会议名称","",title)).append(row(row++,"内容","行号","已保存正文"));
        for(MeetingDocumentSections.Section section:sections){int line=0;for(String text:section.text.split("\\r?\\n",-1)){
            line++;if(text.isEmpty()){data.append(row(row++,section.title,String.valueOf(line),""));continue;}
            for(int start=0;start<text.length();){int count=Math.min(16000,text.codePointCount(start,text.length()));int end=text.offsetByCodePoints(start,count);
                data.append(row(row++,section.title,String.valueOf(line),text.substring(start,end)));start=end;}
        }}
        Map<String,String> parts=new LinkedHashMap<>();
        parts.put("[Content_Types].xml","<?xml version=\"1.0\" encoding=\"UTF-8\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/><Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/></Types>");
        parts.put("_rels/.rels","<?xml version=\"1.0\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>");
        parts.put("xl/workbook.xml","<?xml version=\"1.0\" encoding=\"UTF-8\"?><workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"会议资料\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>");
        parts.put("xl/_rels/workbook.xml.rels","<?xml version=\"1.0\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/><Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>");
        parts.put("xl/styles.xml","<?xml version=\"1.0\"?><styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><fonts count=\"1\"><font><sz val=\"11\"/><name val=\"Microsoft YaHei\"/></font></fonts><fills count=\"2\"><fill><patternFill patternType=\"none\"/></fill><fill><patternFill patternType=\"gray125\"/></fill></fills><borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs><cellXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\" applyAlignment=\"1\"><alignment vertical=\"top\" wrapText=\"1\"/></xf></cellXfs><cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles></styleSheet>");
        parts.put("xl/worksheets/sheet1.xml","<?xml version=\"1.0\" encoding=\"UTF-8\"?><worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetViews><sheetView workbookViewId=\"0\"><pane ySplit=\"2\" topLeftCell=\"A3\" activePane=\"bottomLeft\" state=\"frozen\"/></sheetView></sheetViews><cols><col min=\"1\" max=\"1\" width=\"28\" customWidth=\"1\"/><col min=\"2\" max=\"2\" width=\"8\" customWidth=\"1\"/><col min=\"3\" max=\"3\" width=\"90\" customWidth=\"1\"/></cols><sheetData>"+data+"</sheetData><autoFilter ref=\"A2:C"+(row-1)+"\"/></worksheet>");
        try(ZipOutputStream zip=new ZipOutputStream(out)){for(Map.Entry<String,String> p:parts.entrySet()){ZipEntry e=new ZipEntry(p.getKey());e.setTime(0);zip.putNextEntry(e);zip.write(p.getValue().getBytes(StandardCharsets.UTF_8));zip.closeEntry();}}
    }
    private static String row(int r,String a,String b,String c){return "<row r=\""+r+"\">"+cell("A"+r,a)+cell("B"+r,b)+cell("C"+r,c)+"</row>";}
    private static String cell(String address,String value){return "<c r=\""+address+"\" t=\"inlineStr\"><is><t xml:space=\"preserve\">"+MaterialLayout.xml(value)+"</t></is></c>";}
}
