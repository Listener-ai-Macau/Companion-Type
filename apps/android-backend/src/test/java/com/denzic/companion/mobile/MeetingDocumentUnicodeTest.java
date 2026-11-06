package com.denzic.companion.mobile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.*;

public final class MeetingDocumentUnicodeTest {
    public static void main(String[] args)throws Exception{
        DocumentBuilderFactory factory=DocumentBuilderFactory.newInstance();factory.setNamespaceAware(true);
        Document document=factory.newDocumentBuilder().newDocument();Element root=document.createElementNS("urn:companion:test","q:root");
        root.setAttributeNS("http://www.w3.org/2000/xmlns/","xmlns:q","urn:companion:test");document.appendChild(root);
        String value="中文 😀 𠮷 𝄞 & < > \" # literal **keep**\t\r\n";
        root.setAttribute("value",value);root.appendChild(document.createTextNode(value+"\ud83dX\ude00\u0000\ufffe"));
        byte[] bytes=MeetingDocumentSections.serializeWordXml(document);
        Document parsed=factory.newDocumentBuilder().parse(new ByteArrayInputStream(bytes));
        if(!parsed.getDocumentElement().getAttribute("value").equals(value))throw new AssertionError("Attribute content/whitespace changed");
        if(!parsed.getDocumentElement().getTextContent().equals(value+"\ufffdX\ufffd\ufffd\ufffd"))throw new AssertionError("Scalar text changed or invalid XML1.0 character retained");
        String xml=new String(bytes,StandardCharsets.UTF_8);if(xml.contains("&#55357;")||xml.contains("&#56832;"))throw new AssertionError("Invalid surrogate references");
        if(!xml.contains("😀")||!xml.contains("𠮷")||!xml.contains("𝄞"))throw new AssertionError("Supplementary scalars lost");
        System.out.println("PASS production Word DOM serializer: namespace/attribute/text roundtrip, emoji/CJK extension/music scalar preservation, XML escaping/whitespace and malformed UTF16/control replacement");
    }
}
