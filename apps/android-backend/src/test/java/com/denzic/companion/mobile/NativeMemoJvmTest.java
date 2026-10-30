package com.denzic.companion.mobile;

public final class NativeMemoJvmTest {
    public static void main(String[] args) throws Exception {
        String result=NativeMemo.extract("明天买牛奶，然后带上蓝色文件夹。",10000);
        if(!result.contains("明天买牛奶")||!result.contains("蓝色文件夹")||!result.contains("\"complete\":false"))
            throw new AssertionError("memo draft did not retain source or draft status");
        try{NativeMemo.extract("",10000);throw new AssertionError("empty transcript accepted");}
        catch(java.io.IOException expected){}
        System.out.println("NativeMemo JNI test passed");
    }
}
