package com.denzic.companion.shareqa056;
import android.app.Activity;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** Local-only recipient of explicitly shared public test files. No network,
 * contacts, broad storage permission or access to the source app's private data. */
public final class ShareReceiver056 extends Activity {
    @Override public void onCreate(Bundle state){super.onCreate(state);accept(getIntent());}
    @Override public void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);accept(intent);}
    private void accept(Intent intent){
        if("com.denzic.companion.shareqa056.PUBLIC_CLIPBOARD".equals(intent.getAction())){clipboardPanel();return;}
        TextView text=new TextView(this);text.setTextSize(17);text.setPadding(40,100,40,60);setContentView(text);
        try{
            if(!Intent.ACTION_SEND.equals(intent.getAction()))throw new IOException("请通过 Companion 的系统分享选择此接收端。");
            Uri uri=intent.getParcelableExtra(Intent.EXTRA_STREAM);if(uri==null||!"content".equals(uri.getScheme())||!"com.denzic.companion.app.exports".equals(uri.getAuthority()))throw new IOException("不是 Companion 的单文件分享。");
            if((intent.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)==0)throw new SecurityException("Missing read grant");
            String filename="",mime=getContentResolver().getType(uri);long declared=-1;
            try(Cursor cursor=getContentResolver().query(uri,null,null,null,null)){if(cursor==null||!cursor.moveToFirst())throw new IOException("Missing shared metadata");filename=cursor.getString(cursor.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME));declared=cursor.getLong(cursor.getColumnIndexOrThrow(OpenableColumns.SIZE));}
            if(declared<0||declared>20*1024*1024)throw new IOException("Test file size unsupported");
            String id=Long.toString(System.currentTimeMillis());File copy=new File(getFilesDir(),id+".payload");long bytes=0;MessageDigest digest=MessageDigest.getInstance("SHA-256");
            try(InputStream in=getContentResolver().openInputStream(uri);FileOutputStream out=new FileOutputStream(copy)){if(in==null)throw new IOException("Shared stream unavailable");byte[] b=new byte[32768];int n;while((n=in.read(b))!=-1){bytes+=n;if(bytes>20*1024*1024)throw new IOException("Test file too large");out.write(b,0,n);digest.update(b,0,n);}out.getFD().sync();}
            if(bytes!=declared)throw new IOException("Shared payload differs from declared size");
            boolean writeDenied=false;try(android.os.ParcelFileDescriptor ignored=getContentResolver().openFileDescriptor(uri,"w")){throw new IOException("Unexpected write access");}catch(SecurityException|FileNotFoundException expected){writeDenied=true;}
            boolean otherUriDenied=false;Uri unrelated=uri.buildUpon().appendPath("not-granted").build();try(InputStream ignored=getContentResolver().openInputStream(unrelated)){throw new IOException("Unexpected broader URI grant");}catch(SecurityException expected){otherUriDenied=true;}
            StringBuilder sha=new StringBuilder();for(byte value:digest.digest())sha.append(String.format(Locale.ROOT,"%02x",value&255));
            JSONObject receipt=new JSONObject().put("id",id).put("filename",filename).put("bytes",bytes).put("declaredBytes",declared).put("mime",mime).put("intentMime",intent.getType()).put("sha256",sha.toString()).put("readOnly",writeDenied).put("otherUriDenied",otherUriDenied).put("clipDataItems",intent.getClipData()==null?0:intent.getClipData().getItemCount()).put("sourceAuthority",uri.getAuthority()).put("localOnly",true);
            try(FileOutputStream out=new FileOutputStream(new File(getFilesDir(),id+".json"))){out.write(receipt.toString(2).getBytes("UTF-8"));out.getFD().sync();}
            text.setText("已在本机接收\n\n"+filename+"\n\n"+bytes+" 字节\n\n只读授权："+writeDenied+"\n其它路径已拒绝："+otherUriDenied+"\n\n内容仅保存在本机验收程序中，没有网络传输。");
        }catch(Exception error){text.setText("接收检查失败\n\n"+error);try(FileOutputStream out=new FileOutputStream(new File(getFilesDir(),"failure-"+System.currentTimeMillis()+".txt"))){out.write(error.toString().getBytes("UTF-8"));}catch(Exception ignored){}}
    }

    /** Pasting only after Companion reports copying explicitly public fixture.
     * An unexpected clipboard is never recorded or displayed in diagnostics. */
    private void clipboardPanel(){
        LinearLayout column=new LinearLayout(this);column.setOrientation(LinearLayout.VERTICAL);column.setPadding(32,80,32,32);
        TextView heading=new TextView(this);heading.setText("公开测试文字粘贴验收");heading.setTextSize(19);column.addView(heading);
        EditText field=new EditText(this);field.setHint("这里只粘贴明确标注的公开虚构验收文字");field.setMinLines(5);column.addView(field);
        Button paste=new Button(this);paste.setText("粘贴公开测试文字");column.addView(paste);
        Button verify=new Button(this);verify.setText("核对公开文字");column.addView(verify);
        TextView result=new TextView(this);column.addView(result);setContentView(column);
        paste.setOnClickListener(v->{field.requestFocus();field.onTextContextMenuItem(android.R.id.paste);});
        verify.setOnClickListener(v->{try{
            String value=field.getText().toString();
            if(!value.contains("【公开虚构的导出验收文字，不是录音转写或真实会议】"))throw new IOException("未发现本轮公开测试标记；未保存剪贴板内容");
            if(!value.contains("追加20%的费用尚未批准。")||!value.contains("小陈在11月8日前核对报价")||!value.contains("# literal **keep** <A&B> 😀"))throw new IOException("公开文字的否定、负责人日期或原样符号不完整");
            byte[] data=value.getBytes("UTF-8");String id="clipboard-"+System.currentTimeMillis();
            try(FileOutputStream out=new FileOutputStream(new File(getFilesDir(),id+".txt"))){out.write(data);out.getFD().sync();}
            StringBuilder digest=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(data))digest.append(String.format(Locale.ROOT,"%02x",b&255));
            JSONObject receipt=new JSONObject().put("result","PASS_PUBLIC_TEXT_PASTED_FROM_PRODUCT_COPY").put("id",id).put("bytes",data.length).put("sha256",digest.toString()).put("localOnly",true);
            try(FileOutputStream out=new FileOutputStream(new File(getFilesDir(),id+".json"))){out.write(receipt.toString(2).getBytes("UTF-8"));out.getFD().sync();}
            result.setText("公开文字已核对：否定、负责人、日期及原样符号完整。只保存在本机验收程序。");
        }catch(Exception error){result.setText("未通过："+error.getMessage());}});
    }
}
