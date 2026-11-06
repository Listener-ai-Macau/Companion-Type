package com.denzic.companion.app;

import com.denzic.companion.mobile.MeetingDocumentSections;
import java.io.IOException;
import java.util.*;

/** Fully measure before allocating a phone bitmap; no partial/cropped export. */
final class MindmapLayout {
    static final class Box {
        final MaterialLayout.Node node;final List<String> lines;final List<Box> children=new ArrayList<>();
        final int x,width,font,height;int y,subtree;
        Box(MaterialLayout.Node n,int level){
            node=n;x=24+level*354;width=level==0?280:320;font=level==0?24:n.children.isEmpty()?20:22;
            lines=MaterialLayout.wrap(n.text,(width-36)*4/font);
            // Balance the final two short CJK title lines without changing any text.
            if(level==0&&lines.size()>1&&n.text.matches("[^A-Za-z0-9\\s]+")&&lines.get(lines.size()-1).codePointCount(0,lines.get(lines.size()-1).length())<=2){
                String joined=lines.remove(lines.size()-2)+lines.remove(lines.size()-1);int mid=joined.offsetByCodePoints(0,(joined.codePointCount(0,joined.length())+1)/2);
                lines.add(joined.substring(0,mid));lines.add(joined.substring(mid));
            }
            height=28+Math.max(1,lines.size())*(font+8);
            for(MaterialLayout.Node child:n.children)children.add(new Box(child,level+1));
            int childHeight=0;for(Box c:children)childHeight+=c.subtree+16;
            subtree=Math.max(height,Math.max(0,childHeight-16));
        }
        void position(int top){y=top+(subtree-height)/2;int childY=top;for(Box c:children){c.position(childY);childY+=c.subtree+16;}}
        int right(){int right=x+width;for(Box c:children)right=Math.max(right,c.right());return right;}
        void flatten(List<Box> out){out.add(this);for(Box c:children)c.flatten(out);}
    }
    final Box root;final int width,height;final List<Box> boxes=new ArrayList<>();
    MindmapLayout(String title,List<MeetingDocumentSections.Section> sections)throws IOException{
        root=new Box(MaterialLayout.tree(title,sections),0);width=root.right()+24;height=root.subtree+48;
        if(width>4096||height>10000||(long)width*height>12000000)throw new IOException("导图图片尺寸较大，请减少所选内容，或保存为可编辑导图/Word；本次未生成裁切图片。");
        root.position(24);root.flatten(boxes);
    }
}
