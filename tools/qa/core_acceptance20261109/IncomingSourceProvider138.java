package com.denzic.companion.qa.incoming138;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;
import java.util.Arrays;

/** Finite, read-only provider of this case's owned public files. */
public final class IncomingSourceProvider138 extends ContentProvider {
    static boolean valid(String name){return Arrays.asList("public-incoming138.wav","material.docx","public-whiteboard138.png","public-bad138.wav","public-long138.wav").contains(name);}
    static Uri uri(String name){if(!valid(name))throw new IllegalArgumentException();return new Uri.Builder().scheme("content").authority("com.denzic.companion.qa.incoming138.files").appendPath(name).build();}
    static String mime(String name){return name.endsWith(".docx")?"application/vnd.openxmlformats-officedocument.wordprocessingml.document":name.endsWith(".png")?"image/png":"audio/wav";}
    private File file(Uri uri){String name=uri.getLastPathSegment();if(!valid(name)||uri.getPathSegments().size()!=1)throw new IllegalArgumentException();return new File(getContext().getFilesDir(),name);}
    @Override public boolean onCreate(){return true;}
    @Override public String getType(Uri uri){file(uri);return mime(uri.getLastPathSegment());}
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){
        File file=file(uri);String[] columns=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;
        MatrixCursor cursor=new MatrixCursor(columns);Object[] row=new Object[columns.length];
        for(int i=0;i<columns.length;i++)row[i]=OpenableColumns.DISPLAY_NAME.equals(columns[i])?file.getName():OpenableColumns.SIZE.equals(columns[i])?file.length():null;
        cursor.addRow(row);return cursor;
    }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{if(!"r".equals(mode))throw new FileNotFoundException("Read only public fixture");return ParcelFileDescriptor.open(file(uri),ParcelFileDescriptor.MODE_READ_ONLY);}
    @Override public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
    @Override public int delete(Uri uri,String where,String[] args){throw new UnsupportedOperationException();}
    @Override public int update(Uri uri,ContentValues values,String where,String[] args){throw new UnsupportedOperationException();}
}
