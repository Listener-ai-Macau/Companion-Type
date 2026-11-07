package com.denzic.companion.mobile;
import java.io.*;
import java.nio.file.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONObject;

/** Exercise the real updater with unavailable boot probes and a distinct
 * verification connector. No Android radio/hardware timing qualification. */
public final class SystemUpdateVerificationTest {
    public static void main(String[] args)throws Exception {
        Path root=Paths.get(args[0]);JSONObject m=new JSONObject(new String(Files.readAllBytes(root.resolve("ota_manifest.json")),"UTF-8"));
        SystemUpdatePackage pack=SystemUpdatePackage.validate(m,Files.readAllBytes(root.resolve(m.getString("file"))));
        SystemUpdateTest.Peripheral peripheral=new SystemUpdateTest.Peripheral(pack);
        final int[] calls={0,0};final String[] metrics={null};
        SystemUpdateClient.Connector connector=new SystemUpdateClient.Connector(){
            public RecordingClient.Link connect()throws IOException {
                if(++calls[0]!=1)throw new IOException("normal admission factory reused during post-install probes");
                return peripheral.connect();
            }
            public RecordingClient.Link connectForVerification()throws IOException {
                if(++calls[1]<3)throw new IOException("boot install unavailable");
                return peripheral.connect();
            }
        };
        SystemUpdateClient.transfer(connector,pack,new AtomicBoolean(),new SystemUpdateClient.Progress(){
            public void update(String phase,long accepted,long total){}
            public void metrics(String json){metrics[0]=json;}
        });
        if(calls[0]!=1||calls[1]!=3||peripheral.begin!=1||peripheral.finish!=1||!peripheral.closed||!peripheral.installed)
            throw new AssertionError("Unavailable probes must not reopen admission, resend FINISH or credit an unverified install");
        JSONObject observed=new JSONObject(metrics[0]);
        if(!observed.getBoolean("installed")||observed.getInt("verifyAttempts")!=3||observed.getInt("verifyFailures")!=2)
            throw new AssertionError("retain exact failed probes and installed identity metrics");
        if(!SystemUpdateClient.verify(connector,pack,"1415161718191a1b1c1d1e1f")||calls[0]!=1||calls[1]!=4)
            throw new AssertionError("manual read-back must use verification transport only");
        peripheral.other=true;
        try{SystemUpdateClient.verify(connector,pack,"1415161718191a1b1c1d1e1f");throw new AssertionError("wrong UID accepted");}
        catch(IOException expected){}
        if(peripheral.finish!=1)throw new AssertionError("read-back must never mutate install state");
        System.out.println("PASS actual updater: separate verification factory, two unavailable boots retained, FINISH once, exact identity, closed owners, manual verification and wrong-UID refusal");
    }
}
