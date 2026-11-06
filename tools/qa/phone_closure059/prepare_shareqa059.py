from pathlib import Path
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');W=Path(__file__).parent
old=R/'companion-device-closure055/tools/qa/phone_closure056'
source=(old/'ShareReceiver056.java').read_text(encoding='utf8')
needle='TextView text=new TextView(this);'
assert source.count(needle)==1
source=source.replace(needle,'if("com.denzic.companion.shareqa056.PUBLIC_CLIPBOARD".equals(intent.getAction())){clipboardPanel();return;}\n        '+needle)
method='''
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
'''
at=source.rfind('}');assert at>0
source=source[:at]+method+source[at:]
dest=W/'shareqa059';dest.mkdir(exist_ok=True);(dest/'ShareReceiver056.java').write_text(source,encoding='utf8')
builder=(old/'build_share_receiver056.py').read_text(encoding='utf8')
builder=builder.replace("b=r/'docs/handoffs/20261106-device-phone-closure055/phone-followup';b.mkdir(exist_ok=True)","b=r/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';b.mkdir(parents=True,exist_ok=True)")
builder=builder.replace('share-receiver056','share-receiver059').replace("Path(__file__).parent/'ShareReceiver056.java'","Path(__file__).parent/'shareqa059/ShareReceiver056.java'")
builder=builder.replace('android:versionCode="1"','android:versionCode="2"').replace('android:versionName="056-qa"','android:versionName="059-qa"')
builder=builder.replace('Companion-Share-Receiver056-QA.apk','Companion-Share-Receiver059-QA.apk')
builder=builder.replace("'purpose':'Actual ACTION_SEND", "'clipboardPublicPasteOnly':True,'purpose':'Actual ACTION_SEND")
(W/'build_share_receiver059.py').write_text(builder,encoding='utf8')
print(str(dest/'ShareReceiver056.java'))
