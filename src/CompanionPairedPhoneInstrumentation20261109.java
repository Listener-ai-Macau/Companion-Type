package com.denzic.companion.qa;

import android.app.Instrumentation;
import android.os.Bundle;

/** No activity is launched. Engineering runner uses the installed app's native backend. */
public final class CompanionPairedPhoneInstrumentation20261109 extends Instrumentation {
    private Bundle arguments;
    @Override public void onCreate(Bundle value) { arguments=value; start(); }
    @Override public void onStart() {
        Bundle result=new Bundle();
        try {
            String mode=arguments.getString("mode","inventory");
            CompanionPairedPhoneAsr20261109.main(new String[]{
                getTargetContext().getApplicationInfo().sourceDir,
                getTargetContext().getCacheDir().getAbsolutePath()+"/paired-asr-20261109-r1",mode});
            result.putString("ownedComparator","completed; inspect bound state.json and outputs");
            finish(-1,result);
        } catch(Throwable failure) {
            result.putString("ownedComparatorFailure",failure.toString());
            finish(1,result);
        }
    }
}
