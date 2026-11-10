package com.denzic.companion.app;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
public final class PlaybackProgressTest {
    static void check(boolean v,String message){if(!v)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception{
        Path root=Paths.get(args[0]);Files.createDirectories(root);String binding=new String(new char[64]).replace('\0','a');
        PlaybackProgress store=new PlaybackProgress(root.resolve("one"),p->{});
        check(store.load("record-A",binding,1000000).getLong("positionMs")==0,"new recording must start at zero");
        store.save("record-A",binding,123450,1.5,false);
        JSONObject got=new PlaybackProgress(root.resolve("one"),p->{}).load("record-A",binding,1000000);
        check(got.getLong("positionMs")==123450&&got.getDouble("speed")==1.5&&got.getBoolean("saved"),"reopening lost playback state");
        check(store.load("record-B",binding,1000000).getLong("positionMs")==0,"position leaked to another recording");
        check(new PlaybackProgress(root.resolve("two"),p->{}).load("record-A",binding,1000000).getLong("positionMs")==0,"position leaked to another library");
        check(store.load("record-A",binding.replace('a','b'),1000000).optBoolean("sourceChanged"),"changed source must invalidate the old position");
        check(store.load("record-A",binding,1000).getLong("positionMs")==0,"stale position past new duration must not be clamped into different audio");
        try{store.save("record-A",binding,1,Double.NaN,false);throw new AssertionError("NaN rate accepted");}catch(java.io.IOException expected){}
        check(store.load("record-A",binding,1000000).getLong("positionMs")==123450,"rejected input changed the saved checkpoint");
        store.save("record-A",binding,900000,2,true);got=store.load("record-A",binding,1000000);check(got.getLong("positionMs")==0&&got.getBoolean("completed")&&got.getDouble("speed")==2,"completed recording should restart, retaining speed");
        Path checkpoint;try(java.util.stream.Stream<Path> files=Files.list(root.resolve("one"))){checkpoint=files.filter(p->p.toString().endsWith(".playback.json")).findFirst().get();}
        String invalid="{\"version\":1,\"binding\":\""+binding+"\",\"positionMs\":1.5,\"speed\":1,\"completed\":false}";
        Files.write(checkpoint,invalid.getBytes(StandardCharsets.UTF_8));check(store.load("record-A",binding,1000000).has("warning"),"fractional damaged position was silently coerced");
        check(new String(Files.readAllBytes(checkpoint),StandardCharsets.UTF_8).equals(invalid),"reading damaged state must not delete or overwrite it");
        PlaybackProgress unavailable=new PlaybackProgress(root.resolve("unavailable"),p->{throw new java.io.IOException("injected sync failure");});
        try{unavailable.save("record-A",binding,5000,1,false);throw new AssertionError("failed durable save reported success");}catch(java.io.IOException expected){}
        System.out.println("PASS checkpoint reopen, separate recordings/libraries, descriptor invalidation, duration bounds, completed restart, rejected rates, damaged-data retention and durable-save failure.");
    }
}
