package com.denzic.companion.app;
import android.app.Instrumentation;
import android.os.Bundle;
import android.content.*;
import com.denzic.companion.mobile.*;
import java.io.*;
import org.json.*;

/** No Activity, no Bluetooth calls, separate app-private test data only. */
public final class DeviceClosureInstrumentation extends Instrumentation {
    @Override public void onCreate(Bundle arguments){super.onCreate(arguments);start();}
    int checks;void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    @Override public void onStart(){Bundle result=new Bundle();try{
        Context c=getTargetContext();JSONObject initial=DeviceUpdateService.status(c);check(!initial.getBoolean("running")&&initial.getString("phase").equals("idle"),"idle");
        JSONObject pack;try(InputStream in=c.getAssets().open("full-update.zip")){pack=DeviceUpdateService.prepare(c,in);}
        check(pack.getLong("firmwareVersion")==66685&&pack.getLong("bytes")==1359700,"real signed producer package");
        JSONObject selected=DeviceUpdateService.status(c);check(selected.getJSONObject("prepared").getString("id").equals(pack.getString("id")),"selected package retained");
        SharedPreferences p=c.getSharedPreferences("companion_device_update",Context.MODE_PRIVATE);
        for(String phase:new String[]{"checking","transferring","installing","verifying"}){
            check(p.edit().putString("phase",phase).putString("transactionId",pack.getString("id")).putString("uid","120011000d50335754363720").putString("address","C8:ED:45:EB:95:B4").putLong("accepted",4040).putLong("total",1359700).commit(),"persist prior task");
            JSONObject state=DeviceUpdateService.status(c);check(!state.getBoolean("running")&&state.getString("phase").equals("interrupted")&&state.getBoolean("canVerify")&&!state.getBoolean("canCancel"),"dead process is unconfirmed, never auto-resumed or complete: "+phase);
        }
        p.edit().putString("phase","complete").commit();check(DeviceUpdateService.status(c).getString("phase").equals("complete"),"explicit completed receipt remains distinct");
        File stored=new File(DeviceUpdateService.directory(c),pack.getString("id")+".zip");try(RandomAccessFile file=new RandomAccessFile(stored,"rw")){file.seek(4096);int b=file.read();file.seek(4096);file.write(b^1);}
        boolean rejected=false;try{DeviceUpdateService.load(c,pack.getString("id"));}catch(IOException expected){rejected=true;}check(rejected,"changed retained package rejected before reuse");
        result.putString("result",new JSONObject().put("status","PASS_ANDROID_NATIVE_PACKAGE_AND_INTERRUPTION_STATE_ONLY").put("checks",checks).put("physicalBluetoothUsed",false).put("foregroundServiceStarted",false).put("activityStarted",false).put("modelRun",false).toString());finish(-1,result);
    }catch(Throwable error){result.putString("error",error.toString());finish(1,result);}}
}
