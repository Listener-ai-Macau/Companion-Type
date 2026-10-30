# Companion Android recording backend — integration candidate

This library is the first Android backend for a future mobile UI. It follows the
Listener local-first approach: the selected Companion is accessed over Bluetooth,
and encoded recording segments are saved in the app's private storage. No server,
account, ASR provider, or shared credential is built in. This is an engineering
candidate, not a released mobile app or a claim of phone/device acceptance.

Add this directory as an Android library module to the host application's Gradle
project (which supplies the Android Gradle plugin and API 35 SDK). The host app
owns Bluetooth permission requests, device selection, system pairing and UI. On
Android 12 and later request Bluetooth scan and connect at runtime; on earlier
supported releases request fine location for scanning. The manifest includes the
corresponding declarations. A device must already be system paired before connect.
Keep a connection and transfer in an appropriate user-visible foreground lifetime;
the library does not provide a service or schedule background operations.

Use `CompanionAndroidBackend.discover(context, listener)` to find candidates. The
returned `Scan` stops after 12 seconds or can be closed sooner. Dispatch listener
callbacks to the UI thread if needed. After the user selects and pairs a device,
perform the following on a worker thread:

```java
Path directory = context.getFilesDir().toPath().resolve("companion-recordings");
try (RecordingClient client = CompanionAndroidBackend.connect(context, selectedDevice)) {
    List<RecorderWire.Descriptor> segments = client.listRecordings();
    // After the user selects a segment from this current list:
    Path encoded = client.download(selectedRecordingId, directory,
        (received, total) -> { /* update progress on the UI thread */ });
}
List<RecordingLibrary.Entry> saved = RecordingLibrary.list(directory);
List<RecordingLibrary.Session> recordings = RecordingLibrary.sessions(directory);
```

`download` retains an interrupted partial file and resumes that exact segment on
the next attempt. It checks packet integrity, final SHA-256 and CRC before exposing
the complete local copy. `RecordingLibrary` reports verified, partial and damaged
copies; verified means encoded bytes match the device descriptor, not that they
have been decoded or played. `sessions` groups segments by device, epoch and
session and reports whether the local set is complete, incomplete or damaged;
it does not yet decode or offer playback. `RecordingClient.close()` closes the connection and
can be used to interrupt a transfer; it does not stop device recording. No operation
here deletes or consumes recordings on the device.

The current scope is discovery, connection, V2 recording directory, encoded-segment
transfer, resume, and local inventory. Playback/decoding, session assembly, ASR,
meeting notes, start/stop controls, automatic sync, foreground service, iOS and
real-phone/device acceptance remain to be implemented or validated. Synthetic wire
tests are not a substitute for that acceptance. Errors should be surfaced to the
user so the user can retry; do not present an unfinished transfer as a recording.
