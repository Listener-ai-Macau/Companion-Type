package com.denzic.companion.app;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** One explicit request; never logs credentials, response bodies or source text. */
final class TranslationTransport {
    interface Connector { HttpURLConnection open(URL url) throws Exception; }
    private static final int MAX_RESPONSE=1024*1024;
    static String post(String endpoint,String key,byte[] payload) throws Exception {
        return post(endpoint,key,payload,url -> (HttpURLConnection)url.openConnection());
    }
    static String post(String endpoint,String key,byte[] payload,Connector connector) throws Exception {
        final URI uri;
        try { uri=new URI(endpoint); } catch(Exception invalid) { throw new IllegalArgumentException("请填写完整的 HTTPS 服务地址。"); }
        if(!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost()==null || uri.getUserInfo()!=null || uri.getFragment()!=null || uri.getQuery()!=null)
            throw new IllegalArgumentException("请填写完整的 HTTPS 服务地址，不要在地址中填写密钥。");
        if(key==null || key.trim().isEmpty() || key.length()>1024 || key.indexOf('\r')>=0 || key.indexOf('\n')>=0)
            throw new IllegalArgumentException("请检查 AI 服务密钥。");
        HttpURLConnection connection=null;
        try {
            connection=connector.open(uri.toURL());
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(8000);connection.setReadTimeout(45000);
            connection.setRequestMethod("POST");connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type","application/json; charset=utf-8");
            connection.setRequestProperty("Authorization","Bearer "+key);
            connection.setFixedLengthStreamingMode(payload.length);
            try(java.io.OutputStream out=connection.getOutputStream()){out.write(payload);}
            int status=connection.getResponseCode();
            if(status==401 || status==403)throw new IllegalStateException("服务拒绝了密钥，请检查配置。");
            if(status==402 || status==429)throw new IllegalStateException("服务额度不足或请求过于频繁，请稍后重试。");
            if(status<200 || status>=300)throw new IllegalStateException("翻译服务暂不可用，请检查配置后重试。");
            if(connection.getContentLengthLong()>MAX_RESPONSE)throw new IllegalStateException("翻译结果过大，未显示；原文仍保留。");
            try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] buffer=new byte[8192];int n;
                while((n=in.read(buffer))!=-1){if(out.size()+n>MAX_RESPONSE)throw new IllegalStateException("翻译结果过大，未显示；原文仍保留。");out.write(buffer,0,n);}
                return new String(out.toByteArray(),StandardCharsets.UTF_8);
            }
        } catch(IllegalStateException e){throw e;}
          catch(Exception e){throw new IllegalStateException("无法连接翻译服务，请检查网络和配置；原文仍保留。");}
        finally {if(connection!=null)connection.disconnect();}
    }
}
