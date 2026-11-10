package com.denzic.companion.app;

import android.graphics.*;
import java.io.*;
import java.nio.file.Path;

/** Only validated local raster images; no SVG, scripts, external URLs or full-size decode. */
final class RecordingNoteImages {
    static BitmapFactory.Options inspect(Path file)throws IOException{
        BitmapFactory.Options info=new BitmapFactory.Options();info.inJustDecodeBounds=true;BitmapFactory.decodeFile(file.toString(),info);
        if(info.outWidth<=0||info.outHeight<=0||info.outWidth>24000||info.outHeight>24000||(long)info.outWidth*info.outHeight>80000000L||!("image/jpeg".equals(info.outMimeType)||"image/png".equals(info.outMimeType)||"image/webp".equals(info.outMimeType)))throw new IOException("图片无法读取或尺寸过大，请选择JPEG、PNG或WebP图片。");return info;
    }
    static void validate(Path file,String extension)throws IOException{
        BitmapFactory.Options info=inspect(file);String actual="image/jpeg".equals(info.outMimeType)?"jpg":"image/png".equals(info.outMimeType)?"png":"webp";if(!actual.equals(extension))throw new IOException("图片格式与文件类型不符，请重新选择原图片。");
    }
    static InputStream thumbnail(Path file)throws IOException{
        BitmapFactory.Options info=inspect(file),options=new BitmapFactory.Options();options.inSampleSize=1;while(Math.max(info.outWidth,info.outHeight)/options.inSampleSize>1280)options.inSampleSize*=2;options.inPreferredConfig=Bitmap.Config.RGB_565;
        Bitmap bitmap=BitmapFactory.decodeFile(file.toString(),options);if(bitmap==null)throw new IOException("图片暂不能预览，原图片仍保留。");try{ByteArrayOutputStream out=new ByteArrayOutputStream();if(!bitmap.compress(Bitmap.CompressFormat.JPEG,88,out))throw new IOException("图片预览未完成。");return new ByteArrayInputStream(out.toByteArray());}finally{bitmap.recycle();}
    }
    private RecordingNoteImages(){}
}
