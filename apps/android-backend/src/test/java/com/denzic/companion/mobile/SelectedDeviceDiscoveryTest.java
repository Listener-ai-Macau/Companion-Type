package com.denzic.companion.mobile;
public final class SelectedDeviceDiscoveryTest {
    public static void main(String[] args){
        String selected="C8:ED:45:EB:95:B4",other="C8:ED:45:EB:95:B5";
        if(!DeviceNames.candidate("我的录音卡",false,selected,selected))throw new AssertionError("renamed selected recorder excluded");
        if(!DeviceNames.candidate(null,false,selected,selected))throw new AssertionError("selected recorder without scan-response name excluded");
        if(DeviceNames.candidate("Companion",true,other,selected))throw new AssertionError("another nearby recorder substituted");
        if(!DeviceNames.candidate("Capture",false,other,null)||DeviceNames.candidate("Headphones",false,other,null))throw new AssertionError("ordinary discovery changed");
        System.out.println("PASS exact selected identity survives custom/missing name; other recorder rejected; ordinary discovery unchanged");
    }
}
