package com.denzic.companion.app;
import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;
import java.util.*;

/** Temporary, exact-file URI grants; never exposes recording or library directories. */
public final class ExportFileProvider extends ContentProvider {
    @Override public boolean onCreate(){return true;}
    private PreparedExports.Entry entry(Uri uri,boolean verify)throws Exception{
        List<String> parts=uri.getPathSegments();if(!"content".equals(uri.getScheme())||!getContext().getPackageName().concat(".exports").equals(uri.getAuthority())||parts.size()!=2)throw new FileNotFoundException("Invalid export URI");
        PreparedExports.Entry e=new PreparedExports(getContext().getCacheDir().toPath()).load(parts.get(0),verify);if(!e.meta.getString("filename").equals(parts.get(1)))throw new FileNotFoundException("Invalid export name");return e;
    }
    static Uri uri(Context context,PreparedExports.Entry entry)throws Exception{return new Uri.Builder().scheme("content").authority(context.getPackageName()+".exports").appendPath(entry.id()).appendPath(entry.meta.getString("filename")).build();}
    static Intent shareIntent(Context context,PreparedExports.Entry entry)throws Exception{
        Uri uri=uri(context,entry);Intent intent=new Intent(Intent.ACTION_SEND).setType(entry.meta.getString("mime")).putExtra(Intent.EXTRA_STREAM,uri).putExtra(Intent.EXTRA_SUBJECT,entry.meta.optString("title","Companion")).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.setClipData(ClipData.newUri(context.getContentResolver(),entry.meta.getString("filename"),uri));return intent;
    }
    @Override public String getType(Uri uri){try{return entry(uri,false).meta.getString("mime");}catch(Exception e){return null;}}
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){
        try{PreparedExports.Entry e=entry(uri,false);String[] names=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor cursor=new MatrixCursor(names);Object[] values=new Object[names.length];for(int i=0;i<names.length;i++){if(OpenableColumns.DISPLAY_NAME.equals(names[i]))values[i]=e.meta.getString("filename");else if(OpenableColumns.SIZE.equals(names[i]))values[i]=e.meta.getLong("bytes");}cursor.addRow(values);return cursor;}catch(Exception e){return null;}
    }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
        if(!"r".equals(mode))throw new FileNotFoundException("Read only");try{return ParcelFileDescriptor.open(entry(uri,true).file.toFile(),ParcelFileDescriptor.MODE_READ_ONLY);}catch(Exception e){throw new FileNotFoundException("Export unavailable");}
    }
    @Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException("Read only");}
    @Override public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException("Read only");}
    @Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException("Read only");}
}
