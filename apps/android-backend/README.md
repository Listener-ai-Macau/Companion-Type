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
`CompanionAndroidBackend.pairedDevices(context)` also lists system-paired devices,
so a user can select their device even if it has a custom name or does not
advertise the recording service. This list can include unrelated Bluetooth
devices; it is a selection list, not a claim that each device is a Companion.
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

Use `MeetingStore` in app-private storage to save and reopen a session's
transcript, notes and user-reviewed tasks. Task owner and due are literal text;
the store does not infer dates, generate tasks, or sync with the desktop.

```java
MeetingStore store = new MeetingStore(context.getFilesDir().toPath().resolve("companion-meetings"));
String key = MeetingStore.sessionKey(recordings.get(0).segments.get(0).descriptor);
MeetingStore.Snapshot current = store.load(key); // null if never saved
long revision = current == null ? 0 : current.revision;
// reviewedTasks is the complete task list currently edited by the user.
MeetingStore.Snapshot saved = store.save(key, revision, transcript, notes, reviewedTasks);
MeetingStore.Inventory allSaved = store.list(); // works without a device connection
```

Call `save` only with the revision the user actually edited; a concurrent edit
fails without replacing saved content. If `recoveredFromBackup` is true, show
that an earlier version was restored and ask the user to review it before saving.
`unreadableFiles` tells the host that some content needs attention while other
meetings remain accessible. The store leaves recordings untouched and keeps one
previous text version. Private storage, backup retention and deletion policy are
owned by the host app; no cloud sync or automatic calendar delivery is provided.

`NativeCalendar.export` prepares a local iCalendar document for tasks the user
has reviewed. Invoke it on a worker thread; the host must present its preview and
offer an explicit share/import action. It neither changes a calendar nor creates
notifications. Dates must already be confirmed: use `YYYY-MM-DD` for an all-day
deadline or RFC 3339 with an explicit offset for a timed deadline. Completed
tasks are excluded. The returned `items` contain status and stable UIDs for the
same session key and saved task `id`, even after editing text or reordering. Use
the existing `MeetingStore.Task.id` as each task's `id`; it must be unique within
the session and remain unchanged on edits. For compatibility, tasks without an ID
still use position and text, so their UID changes if either changes. After preview, optional `reminders` and
`slots` can refer to these UIDs. An explicit slot requires start and end with
offsets. Cross-device identity and synchronization are not provided. Owner is
not inserted into the title automatically; include it in task text if needed.

```java
String request = "{\"sessionKey\":\"recording-key\",\"title\":\"会议\"," +
    "\"tasks\":[{\"id\":\"saved-task-id\",\"text\":\"确认报价\",\"completed\":false," +
    "\"due\":\"2026-11-02T14:00:00+08:00\"}],\"reminderMinutes\":30}";
String resultJson = NativeCalendar.export(request); // fields: calendar, items
```

For individual reminders, pass `reminders` such as
`[{"uid":"<preview uid>","reminder":{"kind":"before","minutes":30}}]`
or use `{"kind":"at","at":"2026-11-02T13:30:00+08:00"}`. Explicit execution
times can be supplied as `slots` with `uid` and a `slot` object containing
`start` and `end`. Use a JSON library to construct inputs from user data. Import
behavior and reminder delivery depend on the chosen calendar app and still need
real-phone acceptance.

`download` retains an interrupted partial file and resumes that exact segment on
the next attempt. It checks packet integrity, final SHA-256 and CRC before exposing
the complete local copy. If a completed partial fails the final integrity check,
it keeps that damaged file and retries the segment once from the device. A repeated
failure is returned to the caller, and both damaged copies are retained.
An existing verified local segment is reused on a repeat download. If that local
copy or a partial is damaged, it is retained separately while a new copy is fetched.
`RecordingLibrary` reports verified, partial and damaged
copies; verified means encoded bytes match the device descriptor, not that they
have been decoded or played. `sessions` groups segments by device, epoch and
session and reports whether the local set is complete, incomplete or damaged.
`NativeAudio.decode(session, output)` exposes the shared COP1/Opus decoder, with
the original segments retained and an existing output never overwritten. It can
also return an incomplete capture as such when all recovered segments are present.
The Android ARM64 native candidate is built using `build_android_native.py`; set
the Gradle property `companionAndroidJniLibs` to the resulting `jniLibs` directory
to package it. Build the matching library for each ABI the host app supports. The
ARM64 binary and Java sources have compiled, and the library has been assembled
with Android Gradle plugin 9.4.1. Actual phone execution remains unverified. It
does not provide a playback UI.
`package_android_candidate.py` can also assemble an ARM64 AAR for integration
experiments from the compiled library and an Android API jar. That manually
assembled archive has not yet been validated on a phone and must not be treated
as a release artifact.
`RecordingClient.close()` closes the connection and
can be used to interrupt a transfer; it does not stop device recording. No operation
here deletes or consumes recordings on the device.

`NativeTranscription.transcribe` explicitly sends a selected WAV and caller-supplied
credentials to Volcengine. The caller must make the provider, upload and possible
fees clear before invocation. The library does not start this automatically or
store credentials. The existing service adapter has passed local synthetic-network
fixtures; Android TLS and real-service operation remain unverified. Its TLS trust
uses bundled public roots; custom user-installed roots are not supported here.
Recordings longer than 45 seconds are sent sequentially in 30-second segments.
If a segment fails, the call fails without presenting incomplete text as the
full transcript; the original WAV is retained. Supply the optional app-private
cache directory to reuse successfully recognized segments when retrying. The
cache contains recognized text; the host owns its storage and removal. Cache writes
are best effort, so a retry can still repeat provider charges when storage fails.
A damaged cached chunk is replaced only after a new complete result is received;
the original recording is retained.

```java
Path privateCache = context.getFilesDir().toPath().resolve("companion-asr-cache");
String text = NativeTranscription.transcribe(wav, appId, accessToken, resourceId, privateCache);
```

The current scope is discovery, connection, V2 recording directory, encoded-segment
transfer, resume, local inventory, calendar export, and decoder/recognition candidates. Android
phone validation, playback UI, long-recording recognition qualification,
automatic note/task generation, start/stop controls, automatic sync, foreground service, iOS and
real-phone/device acceptance remain to be implemented or validated. Synthetic wire
tests are not a substitute for that acceptance. Errors should be surfaced to the
user so the user can retry; do not present an unfinished transfer as a recording.
