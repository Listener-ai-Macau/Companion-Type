package com.denzic.companion.mobile;
public final class GattDeadServiceJvmTest {
    static void check(boolean value){if(!value)throw new AssertionError();}
    public static void main(String[] args){
        android.os.DeadObjectException dead=new android.os.DeadObjectException();
        RuntimeException actualShape=new RuntimeException(dead);
        RecordingSyncRunner.LinkFailure failure=AndroidGattLink.recoverablePlatformFailure(actualShape);
        check(failure.getCause()==actualShape&&AndroidGattLink.deadBluetoothService(actualShape));
        check(AndroidGattLink.recoverablePlatformFailure(new RuntimeException(new RuntimeException(dead)))!=null);
        RuntimeException unknown=new IllegalStateException("fixture programming failure");
        try{AndroidGattLink.recoverablePlatformFailure(unknown);throw new AssertionError();}catch(RuntimeException same){check(same==unknown);}
        SecurityException permission=new SecurityException("fixture permission failure",dead);
        try{AndroidGattLink.recoverablePlatformFailure(permission);throw new AssertionError();}catch(SecurityException same){check(same==permission);}
        check(!AndroidGattLink.deadBluetoothService(new RuntimeException("ordinary error")));
        System.out.println("PASS actual AndroidGattLink dead-Binder classifier: exact observed RuntimeException(DeadObjectException) becomes typed LinkFailure with cause; nested death/cleanup recognized; security and unrelated programming failures never retried. SOFTWARE ONLY");
    }
}
