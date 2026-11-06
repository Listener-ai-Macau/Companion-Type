package com.denzic.companion.app;

import android.graphics.*;
import com.denzic.companion.mobile.MeetingDocumentSections;
import java.io.*;
import java.util.List;

/** Android Canvas only; no WebView capture, network, GPU inference or external fonts. */
final class MindmapImage {
    static void write(String title,List<MeetingDocumentSections.Section> sections,OutputStream out)throws IOException{
        MindmapLayout plan=new MindmapLayout(title,sections);Bitmap bitmap=null;
        try{
            bitmap=Bitmap.createBitmap(plan.width,plan.height,Bitmap.Config.ARGB_8888);
            Canvas canvas=new Canvas(bitmap);canvas.drawColor(Color.rgb(246,248,252));
            Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(2);paint.setColor(Color.rgb(200,213,230));
            for(MindmapLayout.Box box:plan.boxes)for(MindmapLayout.Box child:box.children){
                Path path=new Path();float x=box.x+box.width,y=box.y+box.height/2f,ex=child.x,ey=child.y+child.height/2f;
                path.moveTo(x,y);path.cubicTo(x+38,y,ex-38,ey,ex,ey);canvas.drawPath(path,paint);
            }
            paint.setStyle(Paint.Style.FILL);
            for(MindmapLayout.Box box:plan.boxes){
                boolean root=box==plan.root;paint.setColor(root?Color.rgb(23,43,64):box.children.isEmpty()?Color.WHITE:Color.rgb(232,239,248));
                canvas.drawRoundRect(new RectF(box.x,box.y,box.x+box.width,box.y+box.height),12,12,paint);
                paint.setTypeface(Typeface.create("sans-serif",root?Typeface.BOLD:Typeface.NORMAL));paint.setTextSize(box.font);paint.setColor(root?Color.WHITE:Color.rgb(39,54,74));
                float baseline=box.y+14-paint.getFontMetrics().top;
                for(String line:box.lines){canvas.drawText(line,box.x+18,baseline,paint);baseline+=box.font+8;}
            }
            if(!bitmap.compress(Bitmap.CompressFormat.PNG,100,out))throw new IOException("导图图片保存失败，请重试。");
        }catch(OutOfMemoryError error){throw new IOException("手机暂时没有足够内存生成这张长图，请减少内容或保存为可编辑导图。",error);}
        finally{if(bitmap!=null)bitmap.recycle();}
    }
}
