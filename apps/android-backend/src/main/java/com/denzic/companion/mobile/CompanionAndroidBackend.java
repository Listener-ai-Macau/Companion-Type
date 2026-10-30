package com.denzic.companion.mobile;

import android.bluetooth.BluetoothDevice;
import android.content.Context;
import java.io.IOException;
import java.util.List;

/** Entry points for a mobile UI; Bluetooth operations run off the UI thread. */
public final class CompanionAndroidBackend {
    private CompanionAndroidBackend(){}
    /** Candidates already paired in Android settings, including devices with custom names. */
    public static List<BluetoothDevice> pairedDevices(Context context) throws IOException {
        return AndroidDevices.pairedDevices(context);
    }
    public static AndroidDevices.Scan discover(Context context,AndroidDevices.Listener listener) throws IOException {
        return AndroidDevices.discover(context,listener);
    }
    /** Connect a user-selected paired device and negotiate its real recording capability. */
    public static RecordingClient connect(Context context,BluetoothDevice selectedDevice) throws IOException {
        return new RecordingClient(AndroidGattLink.connect(context,selectedDevice));
    }
}
