package com.denzic.companion.app;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.AtomicFile;
import android.util.Base64;
import org.json.JSONObject;
import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

/** Device-bound service credentials. Never returned through the WebView or library backup. */
final class AiServiceVault {
    private static final String ALIAS="companion.ai.service.v1";
    private final AtomicFile file;
    private JSONObject session;
    AiServiceVault(Context context){file=new AtomicFile(new File(context.getNoBackupFilesDir(),"ai-service-v1.json"));}
    private javax.crypto.SecretKey key() throws Exception {
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(ks.containsAlias(ALIAS))return (javax.crypto.SecretKey)ks.getKey(ALIAS,null);
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return generator.generateKey();
    }
    private JSONObject read() throws Exception {
        if(session!=null)return session;
        if(!file.getBaseFile().exists())return null;
        byte[] raw=file.readFully();if(raw.length>32768)throw new IOException("AI服务配置无法读取，请重新配置；录音仍保留。");
        JSONObject outer=new JSONObject(new String(raw,StandardCharsets.UTF_8));
        if(outer.optInt("version")!=1)throw new IOException("AI服务配置版本不受支持，请重新配置。");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(outer.getString("iv"),Base64.NO_WRAP)));
        cipher.updateAAD(ALIAS.getBytes(StandardCharsets.UTF_8));
        return new JSONObject(new String(cipher.doFinal(Base64.decode(outer.getString("data"),Base64.NO_WRAP)),StandardCharsets.UTF_8));
    }
    synchronized JSONObject status() throws Exception {
        JSONObject value;
        try{value=read();}catch(Exception error){return new JSONObject().put("configured",false).put("saved",true).put("error","AI服务配置无法解密，请重新保存或清除；已有资料仍保留。");}
        return new JSONObject().put("configured",value!=null).put("saved",value!=null&&file.getBaseFile().exists())
            .put("endpoint",value==null?"https://api.deepseek.com/chat/completions":value.getString("endpoint"))
            .put("model",value==null?"deepseek-chat":value.getString("model"))
            .put("verified",value!=null&&value.optBoolean("verified",false));
    }
    static void validate(String endpoint,String model) throws Exception {
        URI uri=new URI(endpoint);
        if(!"https".equalsIgnoreCase(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getRawQuery()!=null||uri.getFragment()!=null)
            throw new IOException("请填写完整的HTTPS服务地址，地址中不要包含密钥或查询参数。");
        if(model.trim().isEmpty()||model.length()>200||model.contains("\n"))throw new IOException("请填写有效的服务模型名称。");
    }
    synchronized JSONObject save(JSONObject args) throws Exception {
        String endpoint=args.getString("endpoint").trim(),model=args.getString("model").trim(),secret=args.optString("apiKey","").trim();validate(endpoint,model);
        if(secret.isEmpty()){JSONObject old=read();if(old!=null){if(!new URI(endpoint).getHost().equalsIgnoreCase(new URI(old.getString("endpoint")).getHost()))throw new IOException("更换服务站点时请重新填写该站点的密钥。");secret=old.getString("apiKey");}}
        if(secret.isEmpty()||secret.length()>8192||secret.contains("\n")||secret.contains("\r"))throw new IOException("请填写有效的服务密钥。");
        JSONObject value=new JSONObject().put("endpoint",endpoint).put("model",model).put("apiKey",secret).put("verified",false);
        if(args.optBoolean("remember",true)){write(value);session=null;}else{file.delete();session=value;}
        return status();
    }
    private void write(JSONObject value) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());cipher.updateAAD(ALIAS.getBytes(StandardCharsets.UTF_8));
        JSONObject outer=new JSONObject().put("version",1).put("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP))
            .put("data",Base64.encodeToString(cipher.doFinal(value.toString().getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP));
        FileOutputStream out=null;
        try{out=file.startWrite();out.write(outer.toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(out);}catch(Exception e){if(out!=null)file.failWrite(out);throw new IOException("AI服务尚未确认保存，请重试；原配置仍保留。",e);}
    }
    synchronized JSONObject credentials() throws Exception {JSONObject v=read();if(v==null)throw new IOException("请先在设置中保存AI服务，再回到会议整理。");return new JSONObject(v.toString());}
    synchronized void verified() {try{JSONObject value=read();if(value==null)return;value.put("verified",true);if(session!=null)session=value;else write(value);}catch(Exception ignored){/* Successful work must not be reported as failed because status could not be saved. */}}
    synchronized JSONObject clear() throws Exception {session=null;file.delete();if(file.getBaseFile().exists())throw new IOException("尚未确认清除AI服务，请重试。");return status();}
}
