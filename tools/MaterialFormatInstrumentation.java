package com.denzic.companion.app;
import android.app.Instrumentation;
import android.app.Activity;
import android.os.Bundle;
import android.graphics.BitmapFactory;
import com.denzic.companion.mobile.MeetingDocumentSections;
import java.io.*;
import java.util.*;
import org.json.*;

/** Separate no-Activity public-fixture test package. Never targets the user's app. */
public final class MaterialFormatInstrumentation extends Instrumentation {
    @Override public void onCreate(Bundle arguments){super.onCreate(arguments);start();}
    @Override public void onStart(){Bundle result=new Bundle();
        try{
            File dir=new File(getTargetContext().getFilesDir(),"public-material054");if(!dir.mkdirs()&&!dir.isDirectory())throw new IOException("QA output unavailable");
            List<MeetingDocumentSections.Section> sections=Arrays.asList(
                new MeetingDocumentSections.Section("会议纪要","> 内容为虚构验收材料，需核对\n## 采购与交付\n尚未批准20%的追加费用。\n11月8日前核对报价，未确认就不支付。\n## 后续安排\n由小王先核对接口与样品；确认后再安排交付。",true),
                new MeetingDocumentSections.Section("保存时的原文依据", "原话 #不是标题 **不是新增事实** <A&B> 😀\nThis purchase has not been approved. Keep the conditions and the original quotation.",false));
            String title="公开示例·采购与交付复盘";
            File png=new File(dir,"saved-material.png");try(OutputStream out=new FileOutputStream(png)){MindmapImage.write(title,sections,out);}
            try(OutputStream out=new FileOutputStream(new File(dir,"saved-material.pptx"))){PresentationDocuments.write(title,sections,out);}
            try(OutputStream out=new FileOutputStream(new File(dir,"saved-material.xlsx"))){StructuredWorkbook.write(title,sections,out);}
            try(OutputStream out=new FileOutputStream(new File(dir,"saved-material.mm"))){out.write(MaterialLayout.mindmap(title,sections).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
            BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;BitmapFactory.decodeFile(png.getAbsolutePath(),options);
            MindmapLayout plan=new MindmapLayout(title,sections);if(options.outWidth!=plan.width||options.outHeight!=plan.height)throw new IOException("PNG dimensions do not match full plan");
            JSONObject report=new JSONObject().put("status","ANDROID_NATIVE_CANVAS_PNG_AND_FILE_EXPORTS_PASSED").put("width",options.outWidth).put("height",options.outHeight).put("nodes",plan.boxes.size()).put("pngBytes",png.length()).put("ownerDataUsed",false).put("deviceIo",false).put("modelInference",false).put("activityOpened",false);
            try(OutputStream out=new FileOutputStream(new File(dir,"result.json"))){out.write(report.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));}
            result.putString("publicResult",report.toString());finish(Activity.RESULT_OK,result);
        }catch(Throwable error){result.putString("error",error.toString());finish(Activity.RESULT_CANCELED,result);}
    }
}
