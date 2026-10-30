# Companion Android recording backend — integration candidate

This library is the first Android backend for a future mobile UI. It follows the
Listener local-first approach: the selected Companion is accessed over Bluetooth,
and encoded recording segments are saved in the app's private storage. No official
server account or shared credential is included; the caller can configure its own
recognition service. This is an engineering
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
session and reports whether the local set is complete, incomplete or damaged.
`NativeAudio.decode(session, output)` exposes the shared COP1/Opus decoder, with
the original segments retained and an existing output never overwritten. It can
also return an incomplete capture as such when all recovered segments are present.
The Android ARM64 native candidate is built using `build_android_native.py`; set
the Gradle property `companionAndroidJniLibs` to the resulting `jniLibs` directory
to package it. Build the matching library for each ABI the host app supports. The
ARM64 binary and Java sources have compiled; Android packaging and actual phone
execution remain unverified. It does not provide a playback UI.
`package_android_candidate.py` can also assemble an ARM64 AAR for integration
experiments from the compiled library and an Android API jar. That archive has
not yet been validated by the Android Gradle plugin or on a phone and must not be
treated as a release artifact.
`RecordingClient.close()` closes the connection and
can be used to interrupt a transfer; it does not stop device recording. No operation
here deletes or consumes recordings on the device.

`NativeTranscription.transcribe` explicitly sends a selected WAV and caller-supplied
credentials to Volcengine. The caller must make the provider, upload and possible
fees clear before invocation. The library does not start this automatically or
store credentials. The existing service adapter has passed local synthetic-network
fixtures; Android TLS and real-service operation remain unverified. Its TLS trust
uses bundled public roots; custom user-installed roots are not supported here.

The current scope is discovery, connection, V2 recording directory, encoded-segment
transfer, resume, local inventory, and decoder/recognition candidates. Android
packaging and validation, playback UI, long-recording recognition qualification,
meeting notes, start/stop controls, automatic sync, foreground service, iOS and
real-phone/device acceptance remain to be implemented or validated. Synthetic wire
tests are not a substitute for that acceptance. Errors should be surfaced to the
user so the user can retry; do not present an unfinished transfer as a recording.
