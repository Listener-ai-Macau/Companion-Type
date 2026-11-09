package com.denzic.companion.qa;

import android.os.Process;
import dalvik.system.PathClassLoader;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.lang.reflect.*;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Isolated engineering comparator, not a customer UI or a replacement backend.
 * Loads the installed app's unchanged JNI/model; writes only this public QA cache.
 * No activity, microphone, Bluetooth, network, references or original library. */
public final class CompanionPairedPhoneAsr20261109 {
    private static Path root;
    private static void save(String name,JSONObject data)throws Exception {
        Path output=root.resolve(name),temporary=root.resolve(name+".tmp");
        Files.write(temporary,data.toString().getBytes(StandardCharsets.UTF_8));
        Files.move(temporary,output,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
    }
    private static String sha(Path path)throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] block=new byte[65536];
        try(java.io.InputStream in=Files.newInputStream(path)){int n;while((n=in.read(block))!=-1)digest.update(block,0,n);}
        StringBuilder out=new StringBuilder();for(byte value:digest.digest())out.append(String.format(Locale.ROOT,"%02x",value&255));return out.toString();
    }
    public static void main(String[] args)throws Exception {
        if(args.length!=3)throw new IllegalArgumentException("APK, QA directory and inventory/run required");
        Process.setThreadPriority(Process.THREAD_PRIORITY_LOWEST);
        root=Paths.get(args[1]).toRealPath();
        if(!root.toString().matches("/data/user/0/com\\.denzic\\.companion\\.app/cache/paired-asr-20261109-r1"))throw new SecurityException("Owned QA cache required");
        JSONObject state=new JSONObject().put("pid",Process.myPid()).put("mode",args[2]).put("modelWeightsChanged",false).put("referenceRead",false).put("originalLibraryTouched",false);
        try {
            PathClassLoader loader=new PathClassLoader(args[0],args[0]+"!/lib/arm64-v8a",CompanionPairedPhoneAsr20261109.class.getClassLoader());
            Class<?> nativeClass=Class.forName("com.denzic.companion.mobile.NativeLocalTranscription",true,loader);
            Class<?> progressClass=Class.forName("com.denzic.companion.mobile.NativeLocalTranscription$Progress",true,loader);
            Method transcribe=nativeClass.getMethod("transcribeDetailedWithProgress",Path.class,Path.class,Path.class,progressClass);
            state.put("state","INSTALLED_NATIVE_ASR_API_LOADED_NO_MODEL");save("state.json",state);
            if("inventory".equals(args[2])){System.out.println(state);return;}
            if(!"run".equals(args[2]))throw new IllegalArgumentException("Unsupported mode");
            Path modelRoot=Paths.get("/data/user/0/com.denzic.companion.app/files/companion-models");
            String expected="8234905d74db17f7466a1cd110ce20f57c1ff9c1fc95db0615d8931955da5c54";
            if(!expected.equals(sha(modelRoot.resolve("funasr-paraformer-large-zh-2024/model.int8.onnx"))))throw new IllegalStateException("Pinned deployed model changed");
            JSONArray cases=new JSONArray(new String(Files.readAllBytes(root.resolve("audio-only.json")),StandardCharsets.UTF_8));
            for(int i=0;i<cases.length();i++) {
                if(Files.exists(root.resolve("stop.request")))throw new InterruptedException("Owned comparator stopped");
                JSONObject item=cases.getJSONObject(i);final String id=item.getString("id");
                if(!id.matches("[A-Za-z0-9_-]+"))throw new IllegalArgumentException("Invalid case id");
                Set<String> keys=new HashSet<>();Iterator<String> names=item.keys();while(names.hasNext())keys.add(names.next());
                if(!keys.equals(new HashSet<>(Arrays.asList("id","wav","sha256"))))throw new IllegalArgumentException("Audio-only input required");
                Path wav=root.resolve(item.getString("wav")).normalize();if(!wav.getParent().equals(root)||!item.getString("sha256").equals(sha(wav)))throw new SecurityException("Bound public audio required");
                Path output=root.resolve(id+"-output.json");
                if(Files.exists(output))throw new IllegalStateException("Do not overwrite an earlier neural result");
                final long began=System.nanoTime();
                Object callback=Proxy.newProxyInstance(loader,new Class<?>[]{progressClass},(proxy,method,values)->{
                    if(method.getName().equals("onProgress")) {
                        save("progress.json",new JSONObject().put("case",id).put("processedMillis",values[0]).put("totalMillis",values[1]).put("elapsedSeconds",(System.nanoTime()-began)/1e9));
                        return !Files.exists(root.resolve("stop.request"));
                    }
                    if(method.getName().equals("toString"))return "PublicPairedAsrProgress";
                    if(method.getName().equals("hashCode"))return System.identityHashCode(proxy);
                    if(method.getName().equals("equals"))return proxy==values[0];
                    return null;
                });
                state.put("state","RUNNING_INSTALLED_NATIVE_ASR").put("case",id).put("caseIndex",i);save("state.json",state);
                String result=(String)transcribe.invoke(null,wav,modelRoot,root.resolve(id+"-cache"),callback);
                JSONObject parsed=new JSONObject(result);if(parsed.optString("text","").trim().isEmpty())throw new IllegalStateException("Empty native result retained as failure");
                Files.write(output,result.getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
                save(id+"-complete.json",new JSONObject().put("id",id).put("audioSha256",item.getString("sha256")).put("outputSha256",sha(output)).put("elapsedSeconds",(System.nanoTime()-began)/1e9).put("characters",parsed.getString("text").length()).put("modelSha256",expected).put("qualityQualified",false));
            }
            state.put("state","COMPLETE_INSTALLED_NATIVE_ASR_COMPARATOR_UNSCORED");save("state.json",state);System.out.println(state);
        } catch(Throwable error) {
            Throwable cause=error instanceof InvocationTargetException?((InvocationTargetException)error).getTargetException():error;
            state.put("state","INCOMPLETE_OWNED_COMPARATOR_RETAINED").put("errorClass",cause.getClass().getName()).put("error",String.valueOf(cause));save("state.json",state);throw new RuntimeException(cause);
        }
    }
}
