package com.denzic.companion.app;
import org.json.JSONObject;

/** Provider defaults must not silently turn bounded translation into reasoning. */
public final class TranslationProtocolTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception{
        String source="满30元免费配送；范围先说30公里、后说20公里，需核对。🚀";
        JSONObject official=TranslationProtocol.request(source,"en","deepseek-v4-flash","https://api.deepseek.com/chat/completions");
        check(official.getJSONObject("thinking").getString("type").equals("disabled"),"DeepSeek thinking default leaked into translation");
        check(official.getInt("max_tokens")==8192,"output budget absent");
        check(official.getJSONArray("messages").getJSONObject(1).getString("content").equals(source),"source altered");
        JSONObject custom=TranslationProtocol.request(source,"ja","custom-model","https://api.deepseek.com.example.org/chat/completions");
        check(!custom.has("thinking")&&!custom.has("max_tokens"),"vendor option sent to unrelated provider");
        String complete="{\"choices\":[{\"finish_reason\":\"stop\",\"message\":{\"content\":\"Complete translation\"}}]}";
        check(TranslationProtocol.response(complete).equals("Complete translation"),"complete result rejected");
        try{TranslationProtocol.response(complete.replace("stop","length"));throw new AssertionError("truncated result accepted");}catch(IllegalStateException expected){}
        Exception cause=new java.net.SocketTimeoutException("test deadline");
        try{TranslationChunks.run(source,s->{throw cause;},null);throw new AssertionError("failed chunk accepted");}catch(IllegalStateException expected){check(expected.getCause()==cause,"failure cause discarded");}
        System.out.println("PASS provider-specific non-thinking translation, unchanged source/custom provider, truncation rejection and failure preservation");
    }
}
