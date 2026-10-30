package com.denzic.companion.mobile;

import android.bluetooth.BluetoothDevice;
import android.content.Context;
import java.io.IOException;

/** Entry points for a mobile UI; Bluetooth operations run off the UI thread. */
public final class CompanionAndroidBackend {
    private CompanionAndroidBackend(){}
    public static AndroidDevices.Scan discover(Context context,AndroidDevices.Listener listener) throws IOException {
        return AndroidDevices.discover(context,listener);
    }
    /** Connect a user-selected paired device and negotiate its real recording capability. */
    public static RecordingClient connect(Context context,BluetoothDevice selectedDevice) throws IOException {
        return new RecordingClient(AndroidGattLink.connect(context,selectedDevice));
    }
}
