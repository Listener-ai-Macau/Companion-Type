package com.denzic.companion.uidriver059;
import android.app.*;
import android.os.*;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.view.accessibility.*;
import android.graphics.Rect;
import org.json.*;
import java.util.*;

/** Test-only ordinary accessibility input, restricted to the supplied non-main
 * virtual display. Does not retrieve roots or text from the physical display. */
public final class NativeUi059 extends Instrumentation {
    private Bundle args;
    @Override public void onCreate(Bundle b){args=b;start();}
    @Override public void onStart(){Bundle reply=new Bundle();try{
        int display=Integer.parseInt(args.getString("display","-1"));if(display<=0)throw new IllegalArgumentException("Non-main display required");
        UiAutomation ui=getUiAutomation(UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES);
        AccessibilityServiceInfo info=ui.getServiceInfo();info.flags|=AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS|AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;ui.setServiceInfo(info);
        Thread.sleep(500);
        List<AccessibilityWindowInfo> windows=ui.getWindowsOnAllDisplays().get(display);
        if(windows==null||windows.isEmpty())throw new IllegalStateException("No windows on selected virtual display");
        List<AccessibilityNodeInfo> nodes=new ArrayList<>();JSONArray result=new JSONArray();
        for(AccessibilityWindowInfo window:windows){
            if(window.getDisplayId()!=display)throw new IllegalStateException("Wrong display");
            AccessibilityNodeInfo root=window.getRoot();if(root==null)continue;
            String pkg=String.valueOf(root.getPackageName());
            if(!(pkg.equals("com.denzic.companion.app")||pkg.startsWith("com.denzic.companion.shareqa")||pkg.equals("com.google.android.documentsui")||pkg.equals("com.android.documentsui")||pkg.equals("com.android.fileexplorer")||pkg.equals("com.miui.packageinstaller")||pkg.equals("com.google.android.packageinstaller")||pkg.equals("com.android.packageinstaller")||pkg.equals("android")||pkg.equals("com.android.intentresolver")||pkg.equals("com.miui.securitycenter")))continue;
            ArrayDeque<AccessibilityNodeInfo> queue=new ArrayDeque<>();queue.add(root);
            while(!queue.isEmpty()){
                AccessibilityNodeInfo n=queue.remove();nodes.add(n);if(nodes.size()>4000)throw new IllegalStateException("Too many nodes");
                for(int i=0;i<n.getChildCount();i++){AccessibilityNodeInfo child=n.getChild(i);if(child!=null)queue.add(child);}
            }
        }
        String action=args.getString("action","dump"),label=args.getString("label",""),id=args.getString("id","");
        if(!action.equals("dump")){
            List<AccessibilityNodeInfo> matches=new ArrayList<>();for(AccessibilityNodeInfo n:nodes){
                if((!id.isEmpty()&&id.equals(n.getViewIdResourceName()))||(!label.isEmpty()&&(label.contentEquals(n.getText()==null?"":n.getText())||label.contentEquals(n.getContentDescription()==null?"":n.getContentDescription()))))matches.add(n);
            }
            int index=Integer.parseInt(args.getString("index","0"));if(index<0||index>=matches.size())throw new IllegalStateException("Observed control missing: "+label+id);
            AccessibilityNodeInfo n=matches.get(index);boolean success;
            if(action.equals("click")){
                for(int i=0;i<6&&!n.isClickable()&&n.getParent()!=null;i++)n=n.getParent();
                if(!n.isEnabled()||!n.isClickable())throw new IllegalStateException("Observed control not enabled/clickable");
                success=n.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            }else if(action.equals("setText")){
                Bundle value=new Bundle();value.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,args.getString("value",""));success=n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,value);
            }else throw new IllegalArgumentException("Unsupported ordinary input");
            if(!success)throw new IllegalStateException("Ordinary UI action rejected");
        }
        for(AccessibilityNodeInfo n:nodes){String text=n.getText()==null?"":n.getText().toString(),desc=n.getContentDescription()==null?"":n.getContentDescription().toString();
            if(text.isEmpty()&&desc.isEmpty()&&n.getViewIdResourceName()==null)continue;
            Rect rect=new Rect();n.getBoundsInScreen(rect);
            result.put(new JSONObject().put("text",text).put("desc",desc).put("id",n.getViewIdResourceName()).put("class",String.valueOf(n.getClassName())).put("clickable",n.isClickable()).put("enabled",n.isEnabled()).put("bounds",rect.toShortString()));
        }
        reply.putString("result",new JSONObject().put("display",display).put("action",action).put("nodes",result).toString());finish(Activity.RESULT_OK,reply);
    }catch(Throwable error){reply.putString("error",error.toString());finish(Activity.RESULT_CANCELED,reply);}}
}
