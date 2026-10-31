# Companion Android recording backend — integration candidate

This library is the first Android backend for a future mobile UI. It follows the
Listener local-first approach: the selected Companion is accessed over Bluetooth,
and encoded recording segments are saved in the app's private storage. No official
server account or shared credential is included; the caller can configure its own
recognition service. This is an engineering
candidate, not a released mobile app or a claim of phone/device acceptance.

The intended normal processing path is the existing cloud workflow: receive the
recording, decode it, use Volcengine for speech-to-text, then send the transcript
to the configured DeepSeek-compatible service for the summary and action items.
The APIs below expose those steps separately; the host app must connect them and
make uploads and any charges clear before starting. They do not automatically
run or create confirmed tasks. `NativeMemo` is only a limited offline draft option,
not the primary AI workflow and not a replacement for either cloud service.

The source also contains an **experimental** `NativeLocalTranscription.transcribe`
API for offline Chinese transcription of an already decoded WAV. The three-argument
form accepts the WAV, model root and per-recording app-private cache directory;
it loads the pinned runtime packaged with the APK, including when its native
libraries are not extracted. The four-argument form accepts and verifies a
separate runtime directory. Invoke either form on a worker. The candidate expects
the Paraformer zh-small int8 model and tokens under
`sherpa-onnx-paraformer-zh-small-2024-03-09/` in the model root. Alternatively,
the pinned SenseVoice int8 model and tokens can be prepared on a worker thread:

```java
Path modelRoot = context.getFilesDir().toPath().resolve("companion-models");
LocalModelPreparation.prepare(modelRoot, (downloaded, total) -> {
    // Report progress to the UI on the UI thread.
});
boolean ready = LocalModelPreparation.isPrepared(modelRoot);
String text = NativeLocalTranscription.transcribe(wav, modelRoot, privateCache);
```

Preparation is explicit, downloads approximately 240 MB, and can resume an
interrupted download when the server supports it. Let the user choose when to
download, particularly on mobile data. It downloads only model files and sends
no recording. It validates both files before publishing readiness, retains an
interrupted download for retry, and leaves a previously verified model in place
until its replacement is verified. `isPrepared` also verifies the files; run it
on a worker thread. The backend validates both file hashes when loading,
prefers a completed SenseVoice directory and keeps its cache separate from
Paraformer. The converted weights are from
`csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17`, revision
`2365baeacb507f821a0c8120fcee3d484dba7a07`, based on FunAudioLLM SenseVoice.
The model weights are not included and their distribution terms remain to be
confirmed for release. The arm64 runtime
directory must contain the matching `libonnxruntime.so` and
`libsherpa-onnx-c-api.so`. The model is separately provisioned and not included.
The host APK must include the matching arm64 native libraries. This API makes
no cloud request and does not add punctuation,
word timestamps, or speaker labels. Use the resulting text with `NativeMinutes`
only when the user has selected the configured cloud analysis. The model's weight
redistribution terms, Android runtime loading, physical-phone performance and
two-hour real-meeting accuracy are not yet qualified. This is not a release-ready
feature or an iOS implementation.

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

For a selected recording, `client.receiveSession(selectedSegment, directory, progress)`
reads a fresh device directory and receives all currently sealed segments of the
same session. After reconnecting to the same device, call it again with the same
selected descriptor and private directory: saved segments are reused and partial
segments resume. The result is `COMPLETE`, `INCOMPLETE`, or `DAMAGED`; a still
recording or missing terminal segment is not presented as complete. The caller
owns reconnection and foreground lifetime; this API does not schedule an Android
background service or delete recordings from the device.

For a long meeting, `client.syncAvailableAndReclaim(selectedSegment, directory,
progress)` is the explicit alternative: it receives currently sealed segments of
that selected session, verifies the contiguous saved audio and device-authored
timeline, syncs the local files and their Android directories, and only then sends an exact receipt for
each saved segment to free its device space. It retains the original local files.
Use an immediate child of the existing app-private files directory, as in the
example above, so the recording directory and its parent can both be synced.
It does not touch other sessions. A lost device reply remains pending on the
phone; reconnecting to the same device and calling it again resolves the same
receipt before processing later segments. Keep the recording directory and its
`.receipt` / `.consume-pending` files together. On an error show the user the
saved recording and allow retry; do not delete the private copies or claim a
device confirmation that was not received. The host must use one stable private
recording directory for the selected device and serialize consumers across
connections, including desktop handoff: the device remembers only its latest
four physical receipts. This is a software candidate and
requires real Android/device acceptance, including Android storage durability.

`client.followSessionAndReclaim(selectedSegment, directory, progress)` repeats
that operation without a preset recording duration until the same session has a
terminal segment. Obtain `selectedSegment` from the first sealed segment of the
desired session; until one exists, the host can wait and read the directory again.
Run it on a worker within a user-visible foreground lifetime;
the host controls reconnect, cancellation and service scheduling. It releases the
client lock between polls so recording control remains available. The returned
session can still be incomplete if the device reports an interrupted capture.

The same selected, paired connection can control a recording started by this
mobile backend. Create a host session ID once, keep it for retries, and use an
app-private directory for control records:

```java
Path controlDir = context.getFilesDir().toPath().resolve("companion-control");
String hostSession = NativeRecordingControl.newSessionId();
String started = client.control(controlDir, hostSession, NativeRecordingControl.Action.START, 0);
String paused = client.control(controlDir, hostSession, NativeRecordingControl.Action.PAUSE, 0);
String resumed = client.control(controlDir, hostSession, NativeRecordingControl.Action.RESUME, 0);
String stopped = client.control(controlDir, hostSession, NativeRecordingControl.Action.STOP, 0);
```

For a device that reports the WBA FW801-or-later unlimited-recording contract,
pass `0` for `START` to record until the user stops or the device fills. The
backend verifies the actual connected device and at least one available segment
before sending; older or unrecognized firmware rejects that request instead of
silently using its saved limit. This new contract is a software candidate until the
matching firmware and phone have been tested together.

Each result is JSON with `hostSession`, `state`, `recordingKey`, `anchor`,
`durationMs`, `finishedLocally`, `confirmedByCatalogue` and `captureIncomplete`. A control error or lost connection is not a
stop confirmation; reconnect to the same device and use `controlSessions` to
find saved session IDs and pending commands, then `QUERY` to check that exact
session. For an unconfirmed start, an explicit `START` retry with the original
duration resends the same saved command when appropriate; querying never creates
a new recording. The backend checks capacity and existing control records before
starting, including the device's fragmented-capacity snapshot where available.
It does not consume or delete device recordings. `client.adoptLocalControl(controlDir)`
can bind a currently running or paused recording started with the device button;
it reads verified device status and never sends START. Use its returned `hostSession`
for later control, and `controlSessions` to find it again. The original status must
explicitly identify a stable device-local recording; an unrelated or incomplete
status is not adopted. If a reboot replaces the original live status, call
`client.reconcileControlFromDirectory(controlDir, hostSession)` while connected
to the same device. It checks a complete sealed directory between matching idle
status reads, keeps the original command history and never sends STOP or deletes
audio. The result reports whether the capture was incomplete; an incomplete or
unavailable directory leaves the control session unresolved. This candidate has
not yet been verified with a physical phone and recording card. The app owns foreground
lifetime and must show errors rather than guessing the recording state.

When segments were already received locally, pass their private recording
directory as the third argument to `reconcileControlFromDirectory`. The backend
checks the saved bytes and combines matching originals with the device directory;
it leaves conflicts and missing segments unresolved and never consumes audio.

`client.readDeviceStatus()` returns the device's current `faultBitmap` and
`previousRecordingDamageReported`. If this flag is true, tell the user that a
previous recording segment may be unavailable and retain available recordings.
This is a device observation, not a repair result. A false flag does not prove
old recordings are intact: older firmware may not report this condition. The
firmware implementation is a candidate and has not been tested on a real device.

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
The meeting body remains readable by the preceding mobile backend; calendar
choices are retained separately in the same private directory. Keep the meeting,
backup and calendar files together during backup or deletion. If several edits
were made in an older backend, recovered choices can require explicit review;
check `calendarNeedsReview()` before reusing or exporting them.

`NativeMemo.extract(transcript, durationMillis)` can identify some literal task
candidates in a short personal voice memo without network access. It reuses the
desktop short-memo rules and returns JSON with `quality: "draft"`,
`complete: false`, `eligible`, `fullPlanRecognized` and `actionItems`. It does not
summarize a meeting, resolve dates or owners, or guarantee every task is found.
An empty candidate list is not evidence that there are no tasks. The host must
keep the full transcript, display the candidates for review, and save only what
the user accepts. Use the actual recording duration; this rule supports at most
120 seconds and 280 characters. The host chooses stable IDs for accepted tasks.
For example, “今天下午三点开会，记得带蓝色文件夹” produces two literal
draft candidates. This is a narrow rule and does not resolve the date or make
a calendar event; unfamiliar wording can still be missed.

```java
String candidatesJson = NativeMemo.extract(transcript, decoded.samples / 16);
```

`NativeMinutes.generate` runs the shared desktop service-backed minutes engine
for a selected transcript, including its source checks and resumable long-meeting
chunks. This explicitly sends the transcript to the supplied service and may
incur charges. The host must identify the service, obtain the user's consent,
and invoke it only after the user chooses to organize the recording. Keep the
original transcript in `MeetingStore`; this method does not save or replace it.
The app supplies its own service key and an app-private cache directory. The key
is not written into the cache; the cache contains meeting text and must be handled
as private data by the host. Supply a stable session key and the same effective
service settings on retry to resume completed long-meeting chunks.

Build the JSON with a library and provide `sessionKey`, `title`, `transcript`,
`durationMillis`, `endpoint` (complete HTTPS chat-completions URL), and `model`.
Pass the API key separately to `generate`. The response has desktop-compatible
`source`, `quality`, `summary`, `decisions`, `actionItems`, `questions`,
`markdown`, `llmNote`, and optionally `processing` with chunk counts and
`complete`. Show a draft and its `llmNote` on provider failure; for a partial
long meeting, offer retry and do not display it as complete. Even a complete
result needs user review for recognition and factual accuracy. Never auto-save
generated tasks as confirmed or auto-import them into a calendar. Android network
permission, real TLS, service response quality and phone execution remain unverified.

The normal cloud path can be connected on a worker thread as follows. `session`
is the selected local recording, the caller supplies the configured service
values, and `wav` is a new private output path. Save the transcript in
`MeetingStore` first, then capture the meeting and minutes revisions before
starting the potentially long AI request:

```java
NativeAudio.Result audio = NativeAudio.decode(session, wav);
String meetingKey = MeetingStore.sessionKey(session.segments.get(0).descriptor);
MeetingStore.Snapshot beforeRecognition = store.load(meetingKey);
String expectedText = beforeRecognition == null ? null : beforeRecognition.transcript;
String transcript = NativeTranscription.transcribe(wav, appId, accessToken, resourceId, asrCache);
MeetingStore.Snapshot savedSource = store.saveTranscription(meetingKey, expectedText, transcript);
MeetingStore.Minutes previousMinutes = store.loadMinutes(meetingKey);
long minutesRevision = previousMinutes == null ? 0 : previousMinutes.revision;
org.json.JSONObject request = new org.json.JSONObject()
    .put("sessionKey", meetingKey)
    .put("title", title).put("transcript", savedSource.transcript).put("durationMillis", audio.samples / 16)
    .put("endpoint", minutesEndpoint).put("model", minutesModel);
String minutesJson = NativeMinutes.generate(request.toString(), minutesApiKey, minutesCache);
MeetingStore.Minutes savedMinutes = store.saveMinutes(meetingKey, savedSource.revision,
    minutesRevision, savedSource.transcript, minutesJson);
```

When a meeting already has text, let the user choose whether to replace it with
the new recognition result. `saveTranscription` preserves the meeting's current
notes, confirmed tasks and calendar choices. It checks the text observed before
recognition and rejects a conflicting edit; retain the returned `transcript` in
the caller so it can be reviewed or retried without repeating recognition. A
concurrent save can also require retry. Passing null as the expected text means
the meeting did not exist when recognition started. The same saved text is an
idempotent retry. The same method works with `NativeLocalTranscription.transcribe`.
Offer retry if the second service fails; the summary result may contain an
explicitly marked draft on service failure. The backend does not store the
supplied service credentials.

`loadMinutes(meetingKey)` reopens the result independently of user notes and
confirmed tasks. Its `json` is the saved `NativeMinutes` response, including any
draft or partial status. If `sourceChanged` is true, show that the transcript
has changed and the result needs review; `sourceMissing` means the source meeting
could not be read. If `recoveredFromBackup` is true, an earlier result was
recovered and should be shown as such. A revision or transcript conflict during
`saveMinutes` preserves both versions: reload and reuse the already generated
JSON only if it still matches the transcript, without automatically calling the
service again. The result and one prior version are app-private files; existing
meeting files remain readable by the previous backend. `deleteMinutes(meetingKey)`
explicitly removes only that meeting's stored results and backups, leaving its
recording, transcript, notes and tasks intact. The app also owns any separate
minutes cache and must clear it according to its data-deletion policy. Phone
storage behavior during an actual power interruption still requires device tests.

```java
Path cache = context.getFilesDir().toPath().resolve("companion-minutes-cache");
String minutesJson = NativeMinutes.generate(requestJson, apiKey, cache);
```

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

For saved meetings, `MeetingStore.Task` can also store a `CalendarSettings`
containing a reminder and/or execution slot. The five-argument Task constructor
retains previously saved choices for the same task ID; the six-argument version
explicitly replaces them, and a null setting clears them. Check
`task.calendarNeedsReview()` after a due date changes. `NativeCalendar.exportSaved`
uses the saved choices and stable task IDs; it requests review of changed dates
unless `reviewedChangedDates` is true. Saving explicitly reviewed choices against
the new date clears the review flag. Completed tasks stay out of the export.
The store reads existing CMW1 meetings and writes CMW2 when next saved; older
backend versions cannot read CMW2, so do not roll back to them after saving new
data. Import and reminder delivery still require real-phone verification.

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
The matching Java/native backend also returns `audio.bookmarks`: verified
device-authored marks from the same original recording. Each mark has its device
`sequence`, `sourceSamples`, `playbackSamples` and `elapsedMillis`; the sample
values are at 16 kHz, so `playbackSamples / 16` is the position in the decoded
WAV in milliseconds. The captured/playback position excludes paused time, while
`elapsedMillis` retains the device's elapsed-time observation. The host can save
and reopen these device-created positions without decoding again:

```java
DeviceBookmarkCache markCache = new DeviceBookmarkCache(
    context.getFilesDir().toPath().resolve("companion-device-marks"));
markCache.save(session, audio); // audio is the NativeAudio.decode result for session
DeviceBookmarkCache.Saved savedMarks = markCache.load(session);
```

Use a fresh `RecordingLibrary.sessions` result when reopening. The index binds
the device, session and verified segment identities and accepts an unchanged
recording after its receipt status changes. A missing, damaged or mismatched
index returns null; decode the retained original again to rebuild it. The index
is only a cache of device-created positions: user-created notes or edits must
still be persisted separately. It does not save, consume or delete the original
recording. The mark path has only host-side synthetic JNI tests, not phone/device
acceptance.
While a meeting is still recording, `NativeAudio.inspectPrefix(session)` can
validate a contiguous, fully received local prefix and return device marks on
their original source-sample axis. `encodedSamples` counts encoded 16 kHz
samples and can include codec boundary padding; it is not the final playback
duration. `captureComplete` is false until a non-recovered terminal segment is
present. The final playback positions are supplied by `decode` after recording
ends. Prefix inspection does not communicate with the device or reclaim space.
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
can be used to interrupt a transfer; it does not stop device recording. Only the
explicit `...AndReclaim` operations above consume saved device segments.

`NativeTranscription.transcribe` explicitly sends a selected WAV and caller-supplied
credentials to Volcengine. The caller must make the provider, upload and possible
fees clear before invocation. The library does not start this automatically or
store credentials. The existing service adapter has passed local synthetic-network
fixtures; Android TLS and real-service operation remain unverified. Its TLS trust
uses bundled public roots; custom user-installed roots are not supported here.
Recordings longer than 45 seconds are sent sequentially in 30-second segments.
If the service explicitly rejects the initial connection with a temporary HTTP
429/500/502/503/504 response, the backend retries that connection once before
any audio is sent. Authentication errors and uncertain failures after a
possible upload return immediately for the caller to handle.
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
real phone/device control and receipt acceptance, automatic sync, foreground service, iOS and
real-phone/device acceptance remain to be implemented or validated. Synthetic wire
tests are not a substitute for that acceptance. Errors should be surfaced to the
user so the user can retry; do not present an unfinished transfer as a recording.
