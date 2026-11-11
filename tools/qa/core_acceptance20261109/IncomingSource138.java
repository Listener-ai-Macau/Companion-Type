package com.denzic.companion.qa.incoming138;

import android.app.Activity;
import android.content.ClipData;
import android.content.ComponentName;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.ArrayList;

/** Disposable public-fixture sender. No microphone, network, contacts or storage permission. */
public final class IncomingSource138 extends Activity {
    private String name,mode;
    private Uri uri(){return IncomingSourceProvider138.uri(name);}
    private void button(LinearLayout layout,String label,Runnable action){
        Button button=new Button(this);button.setText(label);button.setOnClickListener(view->{
            try{action.run();}catch(Exception error){((TextView)layout.getChildAt(0)).setText("公开测试未完成："+error.getClass().getSimpleName());}
        });layout.addView(button);
    }
    @Override public void onCreate(Bundle state){super.onCreate(state);render();}
    @Override public void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);render();}
    private void render(){
        name=getIntent().getStringExtra("name");mode=getIntent().getStringExtra("mode");
        if(!IncomingSourceProvider138.valid(name)){finish();return;}
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setPadding(24,32,24,24);
        TextView title=new TextView(this);title.setText("Companion 公开文件来源验收\n"+name+"\n仅公开生成音频与文档图片；不访问用户资料。");layout.addView(title);
        button(layout,"公开：分享选定文件",()->{
            Intent send=new Intent("view".equals(mode)?Intent.ACTION_VIEW:Intent.ACTION_SEND);
            if("view".equals(mode))send.setDataAndType(uri(),IncomingSourceProvider138.mime(name));
            else{send.setType(IncomingSourceProvider138.mime(name));send.putExtra(Intent.EXTRA_STREAM,uri());}
            send.setClipData(ClipData.newRawUri(name,uri()));send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            send.setComponent(new ComponentName("com.denzic.companion.app","com.denzic.companion.app.MainActivity"));startActivity(send);
        });
        button(layout,"公开：分享文档和图片",()->{
            Uri doc=IncomingSourceProvider138.uri("material.docx"),image=IncomingSourceProvider138.uri("public-whiteboard138.png");
            Intent send=new Intent(Intent.ACTION_SEND_MULTIPLE);send.setType("*/*");ArrayList<Uri> list=new ArrayList<>();list.add(doc);list.add(image);send.putParcelableArrayListExtra(Intent.EXTRA_STREAM,list);
            ClipData clip=ClipData.newRawUri("public documents",doc);clip.addItem(new ClipData.Item(image));send.setClipData(clip);send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            send.setComponent(new ComponentName("com.denzic.companion.app","com.denzic.companion.app.MainActivity"));startActivity(send);
        });
        button(layout,"公开：撤销选定文件读取权限",()->revokeUriPermission(uri(),Intent.FLAG_GRANT_READ_URI_PERMISSION));
        button(layout,"公开：恢复选定文件读取权限",()->grantUriPermission("com.denzic.companion.app",uri(),Intent.FLAG_GRANT_READ_URI_PERMISSION));
        setContentView(layout);
    }
}
