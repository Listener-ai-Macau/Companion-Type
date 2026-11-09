package com.denzic.companion.qa;
import android.app.UiAutomation;
import android.os.*;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.view.accessibility.*;
import android.graphics.Rect;
import org.json.*;
import java.util.*;

/** Shell UiAutomator input restricted to the explicitly owned non-main display.
 * No APK installation, accessibility-setting changes or physical-display roots. */
public final class NativeUiStandard110 extends com.android.uiautomator.testrunner.UiAutomatorTestCase {
 public void testRun()throws Exception{
  String[] argv={new String(android.util.Base64.decode(getParams().getString("requestB64"),0),"UTF-8")};
  System.out.println("COMPANION_UI_STAGE=started pid="+android.os.Process.myPid());
  JSONObject args=new JSONObject(argv[0]);int display=args.getInt("display");if(display<=0)throw new IllegalArgumentException("Non-main display required");
  UiAutomation ui=null;
  try{
   Object device=getUiDevice();java.lang.reflect.Method bridgeMethod=device.getClass().getDeclaredMethod("getAutomatorBridge");bridgeMethod.setAccessible(true);Object bridge=bridgeMethod.invoke(device);Class<?> type=bridge.getClass();java.lang.reflect.Method method=null;while(type!=null&&method==null){try{method=type.getDeclaredMethod("getUiAutomation");}catch(NoSuchMethodException ignored){type=type.getSuperclass();}}if(method!=null){method.setAccessible(true);ui=(UiAutomation)method.invoke(bridge);}else{type=bridge.getClass();while(type!=null&&ui==null){for(java.lang.reflect.Field field:type.getDeclaredFields())if(UiAutomation.class.isAssignableFrom(field.getType())){field.setAccessible(true);ui=(UiAutomation)field.get(bridge);break;}type=type.getSuperclass();}if(ui==null){StringBuilder diagnostic=new StringBuilder(bridge.getClass().getName());type=bridge.getClass();while(type!=null){for(java.lang.reflect.Field field:type.getDeclaredFields())diagnostic.append(" ").append(field.getName()).append(":").append(field.getType().getName());type=type.getSuperclass();}throw new IllegalStateException("Stock bridge reference unavailable: "+diagnostic);}}
   AccessibilityServiceInfo info=ui.getServiceInfo();info.flags|=AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS|AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;ui.setServiceInfo(info);Thread.sleep(350);
   List<AccessibilityWindowInfo> windows=ui.getWindowsOnAllDisplays().get(display);if(windows==null||windows.isEmpty())throw new IllegalStateException("No windows on owned display");
   List<AccessibilityNodeInfo> nodes=new ArrayList<>();JSONArray result=new JSONArray();
   for(AccessibilityWindowInfo window:windows){
    if(window.getDisplayId()!=display)throw new IllegalStateException("Wrong display");AccessibilityNodeInfo root=window.getRoot();if(root==null)continue;String pkg=String.valueOf(root.getPackageName());
    if(!(pkg.equals("com.denzic.companion.app")||pkg.startsWith("com.denzic.companion.shareqa")||pkg.equals("com.google.android.documentsui")||pkg.equals("com.android.documentsui")||pkg.equals("com.android.fileexplorer")||pkg.equals("com.miui.packageinstaller")||pkg.equals("com.google.android.packageinstaller")||pkg.equals("com.android.packageinstaller")||pkg.equals("android")||pkg.equals("com.android.intentresolver")||pkg.equals("com.miui.securitycenter")))continue;
    ArrayDeque<AccessibilityNodeInfo> queue=new ArrayDeque<>();queue.add(root);while(!queue.isEmpty()){AccessibilityNodeInfo n=queue.remove();nodes.add(n);if(nodes.size()>4000)throw new IllegalStateException("Too many nodes");for(int i=0;i<n.getChildCount();i++){AccessibilityNodeInfo child=n.getChild(i);if(child!=null)queue.add(child);}}
   }
   String action=args.optString("action","dump"),label=args.optString("label",""),id=args.optString("id","");
   if(!action.equals("dump")){
    List<AccessibilityNodeInfo> matches=new ArrayList<>();for(AccessibilityNodeInfo n:nodes)if((!id.isEmpty()&&id.equals(n.getViewIdResourceName()))||(!label.isEmpty()&&(label.contentEquals(n.getText()==null?"":n.getText())||label.contentEquals(n.getContentDescription()==null?"":n.getContentDescription()))))matches.add(n);
    int index=args.optInt("index",0);if(index<0||index>=matches.size())throw new IllegalStateException("Observed control missing");AccessibilityNodeInfo n=matches.get(index);boolean ok;
    if(action.equals("click")){for(int i=0;i<6&&!n.isClickable()&&n.getParent()!=null;i++)n=n.getParent();if(!n.isEnabled()||!n.isClickable())throw new IllegalStateException("Control disabled");ok=n.performAction(AccessibilityNodeInfo.ACTION_CLICK);}
    else if(action.equals("setText")){Bundle value=new Bundle();value.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,args.getString("value"));ok=n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,value);}
    else throw new IllegalArgumentException("Unsupported action");if(!ok)throw new IllegalStateException("UI action rejected");
   }
   for(AccessibilityNodeInfo n:nodes){String text=n.getText()==null?"":n.getText().toString(),desc=n.getContentDescription()==null?"":n.getContentDescription().toString();if(text.isEmpty()&&desc.isEmpty()&&n.getViewIdResourceName()==null)continue;Rect rect=new Rect();n.getBoundsInScreen(rect);result.put(new JSONObject().put("text",text).put("desc",desc).put("id",n.getViewIdResourceName()).put("class",String.valueOf(n.getClassName())).put("enabled",n.isEnabled()).put("bounds",rect.toShortString()));}
   System.out.println("COMPANION_UI="+new JSONObject().put("display",display).put("action",action).put("nodes",result));
  }finally{}
 }
}
