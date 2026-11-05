# Companion Android recording backend — integration candidate

This library is the first Android backend for a future mobile UI. It follows the
Listener local-first approach: the selected Companion is accessed over Bluetooth,
and encoded recording segments are saved in the app's private storage. No official
server account or shared credential is included; the caller can configure its own
recognition service. This is an engineering
candidate, not a released mobile app or a claim of phone/device acceptance.

The target workflow is local-first: receive and retain the encoded recording,
decode it on the phone, and offer local speech-to-text. Send the resulting text
to the configured AI service for a summary and action-item drafts when the user
chooses to organize it. Cloud transcription through Volcengine is an alternative:
it sends audio to that service. AI organization sends transcript text to the
configured DeepSeek-compatible service. The host app must connect the steps and
explain network use and any charges. These APIs do not automatically run or create
confirmed tasks; `NativeMemo` is only a limited offline draft, not AI analysis.

Local transcription is an **experimental integration candidate** and has not
been validated on an Android phone or for a real two-hour device recording. The
phone app must handle model preparation, storage, progress and failures; do not
claim local recognition is production-ready until device acceptance is complete.
The backend provides an **experimental** `NativeLocalTranscription.transcribe`
API for offline Chinese transcription of an already decoded WAV. The three-argument
form accepts the WAV, model root and per-recording app-private cache directory;
it loads the pinned runtime packaged with the APK, including when its native
libraries are not extracted. The four-argument form accepts and verifies a
separate runtime directory. Invoke either form on a worker. The preparation API
downloads the publisher's pinned Chinese Paraformer-large model; previously
prepared SenseVoice and Paraformer zh-small models remain supported:

```java
Path modelRoot = context.getFilesDir().toPath().resolve("companion-models");
LocalModelPreparation.prepare(modelRoot, (downloaded, total) -> {
    // Report progress to the UI on the UI thread.
});
boolean ready = LocalModelPreparation.isPrepared(modelRoot);
String text = NativeLocalTranscription.transcribe(wav, modelRoot, privateCache);
// Optional: the same text plus approximate recording positions for playback.
String detailedJson = NativeLocalTranscription.transcribeDetailed(wav, modelRoot, privateCache);
```

`transcribeDetailed` uses the same models, cache and offline processing as
`transcribe`. It returns JSON with `schema: 1`, `text`, `provider`, `durationMs`,
ordered `segments`, and `unrecognized` ranges. Each segment contains `text`, `startMs`, `endMs`, and
`approximateTiming: true`. These positions describe the audio window sent to
the model; they are useful for seeking nearby, not word-level timestamps. The
backend can persist these positions alongside the meeting:

An `unrecognized` range contains `startMs` and `endMs` for nonzero audio where
the model returned no text. This can be quiet background or missed speech; it is
not proof of either. Show a brief indication and let the user play that range,
including when displaying AI minutes generated from the partial transcript.
The plain `transcribe` API only returns text; use the detailed API for this feature.

For an explicit retry of one range, `RecordingAudioRange.withRange` reads only
that interval from the verified decoded part set and gives the chosen processor
a private temporary WAV. It does not change the recording or stored transcript.
For example, on a worker thread:

```java
RecordingAudioRange.Result<String> retry = RecordingAudioRange.withRange(
    session, decodedPartsDirectory, appPrivateTemporaryDirectory, startMs, endMs,
    wav -> NativeLocalTranscription.transcribeDetailed(wav, modelDirectory, asrCacheDirectory));
// retry.value is the detailed JSON. Its positions are relative to startMs.
// If retry.retainedTemporary != null, retry deletion of that exact private file.
```

The user may also select a range directly from the saved recording when the
initial transcription returned no text and therefore produced no gap markers.
Bind the selection to the displayed recording; when retrying a listed gap, also
verify that the gap still belongs to the displayed transcript. Let the user
review the result, label it as a partial reference, and preserve the original
recording and any existing text. A single recovered excerpt is not a complete
transcript of the meeting.
For a cloud retry the processor may instead call the existing
`NativeTranscription.transcribe`; disclose the provider and that the selected
audio is sent and may incur charges. A repeated local retry with the same model
and unchanged audio may give the same result. Temporary WAV cleanup runs on
success and failure; a process crash can leave a `companion-asr-range-*.wav`
file in the dedicated app-private temporary directory. The host should clean
only these files on startup when no range operation is active. The existing ASR
cache has its own per-recording retention rules.

```java
// Worker thread. expectedTranscript is the text observed before recognition,
// or null if there was no saved meeting. Parse detailedJson with Android org.json.
org.json.JSONObject detail = new org.json.JSONObject(detailedJson);
if (detail.getInt("schema") != 1) throw new IllegalArgumentException("Unknown transcription format");
String recognizedText = detail.getString("text");
java.util.List<MeetingStore.TranscriptWindow> windows = new java.util.ArrayList<>();
org.json.JSONArray segments = detail.getJSONArray("segments");
for (int i = 0; i < segments.length(); i++) {
    org.json.JSONObject segment = segments.getJSONObject(i);
    windows.add(new MeetingStore.TranscriptWindow(segment.getString("text"),
        segment.getLong("startMs"), segment.getLong("endMs")));
}
java.util.List<MeetingStore.UnrecognizedRange> gaps = new java.util.ArrayList<>();
org.json.JSONArray unrecognized = detail.getJSONArray("unrecognized");
for (int i = 0; i < unrecognized.length(); i++) {
    org.json.JSONObject gap = unrecognized.getJSONObject(i);
    gaps.add(new MeetingStore.UnrecognizedRange(gap.getLong("startMs"), gap.getLong("endMs")));
}
store.saveTranscription(sessionKey, expectedTranscript, recognizedText);
store.saveTranscriptTiming(sessionKey, recognizedText, wav, detail.getLong("durationMs"), windows, gaps);
// Later, using the same unchanged WAV:
MeetingStore.TranscriptTiming savedPositions = store.loadTranscriptTiming(sessionKey, wav);
```

Use the exact WAV passed to recognition, kept unchanged. The store binds positions
to the audio content and saved transcript; if either changes or the audio is gone,
loading returns null and the text remains available without seek positions. Hashing
reads the file, so save/load must run on a worker thread. Saving text and positions
are separate: on interruption or edit conflict, keep the text and retry positions
only for the same source. On user deletion, also call `deleteTranscriptTiming`.
`savedPositions.unrecognized` is null when this metadata is unavailable (including
legacy saves), or a possibly empty list when it was saved. It is not safe to treat
missing metadata as proof that the entire recording was recognized. The positions
and ranges remain available after restart and are included in normal library backup.
The frontend still needs to wire these methods to playback; no Android device
acceptance is implied by the backend API.

For recoverable playback and transcription, prepare the audio parts on a worker
using an app-private cache directory reserved for this backend. This reopens an
already verified set or decodes the retained original. After an interrupted
preparation, the next call cleans only its own incomplete attempt and retries;
a damaged completed copy and unrelated files are retained. `parts.directory` is
the directory to pass to transcription, playback and timing calls. The app can
call `prepare` again after restart without remembering a temporary attempt name:

```java
Path audioCache = context.getFilesDir().toPath().resolve("companion-decoded-audio");
NativeAudio.PartsResult parts = ManagedAudioParts.prepare(recordingSession, audioCache);
Path partsDirectory = parts.directory;
```

When the user explicitly chooses to free this recording's decoded cache, stop
playback/transcription first, then call `ManagedAudioParts.clear(recordingSession,
audioCache)` on a worker. It removes only this session's owned decoded attempts,
including damaged copies; the original device and received recording, saved text,
minutes and other sessions are untouched. If `retainedAttempts` is nonzero,
some entries contained unknown files or could not be removed: report incomplete
cleanup and permit retry. Calling `prepare` later can recreate the decoded audio
from the retained original. ASR and minutes caches are separate app-owned data;
manage those according to the user's chosen deletion scope. Caches created by
this version are associated with the recording identity across source updates.
If the source metadata is no longer available, call
`clearBySessionKey(savedSessionKey, audioCache)` to clear v2 cache copies using
the stable `MeetingStore.sessionKey` retained by the app. A damaged source does
not prevent `clear(session, audioCache)`. Key-only cleanup cannot identify v1
markers, which do not include the stable session identity.
The earlier candidate's v1 cache marker only identifies an exact source version;
if the source changed before upgrading, clear that older cache using its original
session or clear the app's entire dedicated decoded-cache directory explicitly.

For a recording decoded into multiple WAV parts, use the corresponding complete
part set for both recognition and saved positions. The source session and all
parts are checked when positions are reopened; a changed or missing part cannot
silently point to a different time. These calls also belong on a worker thread:

```java
String detailedPartsJson = NativeLocalTranscription.transcribeDetailedParts(
    recordingSession, partsDirectory, modelRoot, privateCache);
// Parse text, durationMs, windows and gaps from detailedPartsJson as shown above.
store.saveTranscription(sessionKey, expectedTranscript, recognizedText);
store.saveTranscriptTimingParts(sessionKey, recognizedText, recordingSession,
    partsDirectory, durationMs, windows, gaps);
// Later, reopen the same session and its verified parts:
MeetingStore.TranscriptTiming savedPositions = store.loadTranscriptTimingParts(
    sessionKey, recordingSession, partsDirectory);
```

For long local transcription, the host can show processed audio duration and
let the user stop without discarding the source; successfully cached windows can
be reused:

```java
java.util.concurrent.atomic.AtomicBoolean cancel = new java.util.concurrent.atomic.AtomicBoolean(false);
try {
    String detailed = NativeLocalTranscription.transcribeDetailedPartsWithProgress(
        recordingSession, partsDirectory, modelRoot, privateCache, (processedMs, totalMs) -> {
            // Post processedMs / totalMs to the UI; this callback runs on the worker.
            return !cancel.get();
        });
    // Save the completed result as above.
} catch (java.util.concurrent.CancellationException stopped) {
    // The source remains. Call again to reuse windows successfully saved to cache.
}
// Set cancel to true from the UI when the user asks to stop.
```

`transcribeDetailedWithProgress` provides the same behavior for one WAV; both
forms also accept an explicit runtime directory. Progress describes audio
processed, including silence, not estimated time remaining. Cancellation takes
effect between model windows, not in the middle of model inference. Caching is
best effort: if a cache write fails, that window is processed again on retry.
Callback exceptions propagate to the caller. The existing APIs remain available.

### Optional minutes template

For a user-selected view, add `template` to the existing minutes request. Built-in
IDs are `meeting`, `interview`, and `lecture`; the backend supplies their names and
instructions. For a reusable custom template, the mobile UI can persist a name and
instructions and pass `{"id":"custom","name":"项目复盘","instructions":"关注风险及原因"}`.
Omit `template` to retain the prior behavior. The selected view is applied to every
long-meeting chapter and is part of the cache identity, so different views do not
reuse each other's generated chapters. The returned result includes the normalized
`template` object and a view label in `markdown`. Save the complete returned JSON
using `MeetingStore.saveMinutes`; the store keeps prior saved results in its existing
history and can restore them. If a template request fails or produces an incomplete
draft, the call reports an error and does not save a replacement; completed chapter
cache may be reused when the same request is retried. If question classification
is missing, an otherwise usable template result retains exact question-marked
source sentences and includes a notice; unpunctuated questions may be missed.
Model outputs still need review.

To include user-confirmed corrections or notes, the host may add a `supplements`
array of nonempty strings to the explicitly requested minutes JSON. These strings
are sent to the configured AI service alongside the transcript; display that
choice before the request. Long meetings are processed in chapters and then
combined with the supplements, including changes or cancellations. The returned
`sourceSupplements` records the exact selected strings, including an empty array
when no supplement was selected. Persist the complete result with `MeetingStore`.
Before showing it as current, call `NativeMinutes.supplementStatus(saved.json,
currentSelectedSupplements)`: `CURRENT` means the exact selected list matches,
`CHANGED` means it differs, and `UNKNOWN` means an older or unreadable result did
not record a usable source. The comparison is local and does not call the service.
Pass an empty list when the user currently wants original-only minutes; when a
saved note is selected, pass its current text. `MeetingStore.Minutes.sourceChanged`
tracks the transcript separately and does not by itself detect changed notes.
Status only compares sources, not AI accuracy or whether a draft is final.
Notes are not represented as original speech. The caller owns note storage,
user choice, and retry; the backend does not automatically resend them. Incomplete
combined results stay drafts with a reason; do not present them as final tasks.

```java
MeetingStore.Minutes saved = store.loadMinutes(sessionKey);
MeetingStore.Snapshot current = store.load(sessionKey);
if (saved != null && current != null) {
    // The host chooses the same sources it currently wants included.
    java.util.List<String> selectedNotes = current.notes.isEmpty()
        ? java.util.Collections.emptyList()
        : java.util.Collections.singletonList(current.notes);
    NativeMinutes.SupplementStatus noteStatus =
        NativeMinutes.supplementStatus(saved.json, selectedNotes);
    // sourceChanged covers transcript changes; noteStatus covers selected notes.
    // CHANGED can be offered for regeneration; UNKNOWN needs source review.
}
// If current is null, saved.sourceMissing already identifies an unavailable source.
```

`NativeMinutes.generateWithProgress` reports processed UTF-8 source bytes
and lets the caller return false to stop. A service request already sent cannot
be recalled; after it returns no later chapter or optional review is sent. Use
the same request and private cache on retry to reuse durable chapters. Progress
reaching the total means chapters are saved; the final review or supplement merge may still
be running, so wait for the method to return before presenting a final result.

Cloud transcription also exposes `NativeTranscription.transcribeWithProgress`
and `transcribePartsWithProgress` with a `Progress` callback. Invoke on a worker;
the callback receives processed and total audio milliseconds and can return
false to stop. The current cloud request may finish and cannot be recalled;
no later chunk is sent after cancellation. Supply the same private cache on
retry to reuse completed windows where their cache writes succeeded. The
caller still handles the existing service credentials, user-visible cloud use,
errors, and saving the returned text; no new service or frontend is included.
The local and cloud transcription caches are optional: if a private cache
directory cannot be prepared, recognition continues without cached windows.
Retrying may then repeat recognition (including chargeable cloud requests), and
the caller must still save the completed transcript normally.

Single-WAV timing remains compatible with `saveTranscriptTiming` and
`loadTranscriptTiming`; a single WAV is never treated as a complete part set.

Preparation is explicit, downloads approximately 240 MB, and can resume an
interrupted download when the server supports it. Let the user choose when to
download, particularly on mobile data. It downloads only model files and sends
no recording. It validates both files before publishing readiness, retains an
interrupted download for retry, and leaves a previously verified model in place
until its replacement is verified. `isPrepared` verifies a supported model;
run it on a worker thread. If the new download fails, a verified existing model
can remain usable. Progress may stop before the download total in that case.
Cancellation still interrupts preparation. The backend prefers the new model,
then a verified SenseVoice or legacy Paraformer if it cannot load; each model has
a separate cache. The new weights are from `funasr/Paraformer-large`, revision
`6843c899b177f325d4bbdad8c08d85d5b1321f00`. Metadata derived from that same
revision is appended for sherpa-onnx; the graph and weights are unchanged.
The AAR includes `assets/companion-local-model-notices.txt` for the integrating
app to display with its other third-party notices, including the optional legacy
Paraformer source and the pinned model and token identities.
For the standard ARM64 bridge, also make `assets/companion-android-native-notices.txt`
available to users alongside the other notices. It contains the original Opus
license and notices for the locked Rust dependency input set; the adjacent
`companion-android-native-components.json` records versions, sources and hashes.
The input list is conservative, not a claim that every item is present in the
linked binary. `python apps/android-backend/verify_android_native_notices.py`
checks that these materials still match the ARM64 native build inputs. A different
ABI, feature set or supplied bridge requires its own matching attribution review.
The model weights are not included and their distribution terms remain to be
confirmed for release. The standard ARM64 AAR includes the pinned `libonnxruntime.so` and
`libsherpa-onnx-c-api.so` beside the bridge, and includes their source/license
notices in `assets/companion-asr-runtime-notices.txt` and the adjacent directory.
The model is separately provisioned and not included. If the host already owns
these runtimes, the packager supports `--external-asr-runtime` instead; the host
must package the exact matching pair and their notices, avoiding duplicate ABI
libraries. An explicitly supplied runtime directory must contain that same pair. This API makes
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
Keep a connection and transfer in an appropriate user-visible foreground lifetime.
For user-started long-session reception, the optional foreground service below
manages the same-device connection; it does not schedule unattended starts.

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
device confirmation that was not received. If a different session has an unresolved
receipt, do not silently consume it while syncing the new selection. Call
`RecordingLibrary.pendingConfirmation(directory)` to get its original descriptor,
and offer to resume that exact session first. `RecordingSyncService.start` checks
this before replacing the previous saved task, so `resume` can still use the
previous device address. This also works if the corresponding
device segment no longer appears in the device list. Afterwards continue the new
selection. The device retains only a small recent receipt history, so do not start
other consumers in parallel while this confirmation is unresolved. The host must use one stable private
recording directory for the selected device and serialize consumers across
connections, including desktop handoff: the device remembers only its latest
four physical receipts. This is a software candidate and
requires real Android/device acceptance, including Android storage durability.

For an unresolved receipt, the host can show its `uid`, epoch, and session ID
from `RecordingLibrary.pendingConfirmation(directory.toPath())`. With the
matching paired device, call `RecordingSyncService.resumePending(context,
device, directory)` from a visible activity. The normal device identity checks
still run when the connection is made. Do not offer an old selection as the new
one or imply that a device copy still exists after physical reclamation.

If an old confirmation cannot be resolved, the user may explicitly choose to
continue with other recordings while leaving it unresolved. Call
`RecordingLibrary.deferPendingConfirmation(directory, pendingDescriptor)` on a
worker. This preserves existing local files and the exact pending identity,
sends no command to the device, and does not claim the card confirmed deletion.
Deferral also works if the old local audio is missing or damaged, so unrelated
recordings can continue; it does not claim that the old audio is intact.
Show deferred items from `RecordingLibrary.deferredConfirmations(directory)`;
to retry one, first call `restoreDeferredConfirmation(directory, item.token,
item.descriptor)`, then use `resumePending` with the original paired device.
Restoring requires the original local prefix to be verified. If it is missing
or damaged, first recover the original audio without issuing a consume receipt
(for example with `RecordingClient.receiveSession` if it still exists on the
card); if recovery is unavailable, keep the deferred identity and report the
problem. Only restore when no other confirmation is active. Because the card keeps a
limited recent confirmation history, a deferred confirmation may no longer be
resolvable; keep any remaining local files available. Explain this
choice to the user instead of silently postponing the confirmation.

If `pendingConfirmation` reports that its saved record cannot be read, the host
may offer `deferUnreadablePendingConfirmation(directory)`. It moves the original
bytes aside without any device command, so other recordings can continue; it
does not know the damaged record's identity or establish whether its audio was
saved. `unreadableConfirmations(directory)` lists these preserved records after
reopening the app for support or recovery. A readable confirmation is not moved by
this operation and must use the ordinary explicit deferral path above.

`client.followSessionAndReclaim(selectedSegment, directory, progress)` repeats
that operation without a preset recording duration until the same session has a
terminal segment. Obtain `selectedSegment` from the first sealed segment of the
desired session; until one exists, the host can wait and read the directory again.
Run it on a worker within a user-visible foreground lifetime;
the host controls reconnect, cancellation and service scheduling. It releases the
client lock between polls so recording control remains available. The returned
session can still be incomplete if the device reports an interrupted capture.

### User-started background reception (candidate)

`RecordingSyncService` keeps one selected session receiving while the host app
is backgrounded. Start it from a visible activity after the user has selected an
already bonded device, granted Bluetooth permission, and explicitly chosen the
session and reception with device-space reclamation. Close the original listing
connection before the service connects. It requires at least the first sealed
segment and the same stable private recording directory as above:

```java
File directory = new File(context.getFilesDir(), "companion-recordings");
if (!directory.isDirectory() && !directory.mkdir()) throw new IOException("Cannot create recording directory");
RecordingSyncService.start(context, selectedDevice, selectedSegment, directory);
// Render the current status when the UI is visible:
RecordingSyncStatus status = RecordingSyncService.status(context);
// Render status.state and status.detail. If state is "interrupted", "error",
// or "stopped" and status.hasSavedTask is true, offer to continue that task.
// User stops reception only; recording on the card is not stopped.
RecordingSyncService.stop(context);
// Later, from a visible activity and after checking permissions:
RecordingSyncService.resume(context);
```

The service has a user-visible foreground notification with a stop-reception
action. The newly selected device, recording and directory are saved before
Android is asked to launch the service. If launch fails or the process exits
before reception begins, the saved selection can be resumed; an older service
redelivery does not replace it. After a temporary link loss, it keeps retrying the same bonded device at
increasing intervals, up to one attempt every 30 seconds, until it reconnects or
the user stops reception. Recoverable GATT operation failures also close the old
connection before retrying. If phone Bluetooth is off, the service asks for it to
be enabled and resumes automatically; a revoked permission instead reports an
actionable error. It then resumes the same verified segment and resolves
any outstanding exact receipt. A missing Bluetooth permission or removed pairing
instead reports an actionable error; the host should let the user fix it and
resume. Local storage or integrity errors also stop rather than being retried as
a Bluetooth loss. If a device connects but its recording protocol or identity is
invalid, the service reports an error instead of reconnecting forever; Bluetooth
link failures, capability startup delays and negotiation timeouts remain retryable. If a GATT operation or notification times out before Android
reports a disconnect, the service also closes that stalled connection and resumes
through a new connection, including reconciliation of a pending device receipt.
It does not start a recording, transcribe, upload or delete local audio. It uses
`syncAvailableAndReclaim`, which frees only the selected session's device segments
after verified durable storage, so the host must describe that behavior before
starting and must not run another consumer for that device simultaneously.
Reception checks the selected session independently: damaged metadata belonging
to a different session does not stop this transfer. Damaged metadata for the
selected session still stops reclamation and leaves the device copy in place.
The strict `RecordingLibrary.list`/`sessions` calls still report malformed
metadata as an error. For the user-facing library use `inspect` on a worker:

```java
RecordingLibrary.Inventory inventory = RecordingLibrary.inspect(directory.toPath());
// Display inventory.sessions, including INCOMPLETE or DAMAGED sessions.
// Also show inventory.problems: each entry identifies an unreadable metadata file.
```

`inspect` retains healthy sessions even if another metadata file cannot be read;
it marks a matching session DAMAGED and never deletes or changes the affected
files. The host must show the reported problems instead of silently hiding them.
For a different recording, stop the existing reception first. The service reports
`connecting`, `syncing`, `following`, `reconnecting`, `waiting_bluetooth`, `complete`, `incomplete`,
`stopped`, or `error`. Prefer `status(context)` when displaying the result:
if a formerly active task no longer has a running service in this process it
returns `interrupted`, with a message and `hasSavedTask`. That flag indicates
that a task identity was saved; it does not guarantee Bluetooth permission,
the device connection, or successful recovery. When the user chooses to
continue, call `resume` from a visible activity as above. Android may also
redeliver the existing intent and restart the service. The older `state()`,
`detail()` and `isRunning()` methods remain available; `state()` and `detail()`
still return the last saved values and must be considered with `isRunning()`.
Show the `detail()` text for `error`: a local storage or recording-integrity
failure remains actionable even if Bluetooth disconnects at the same time.
Ordinary classified link loss and notification timeouts still reconnect the
same recording automatically. A negotiated MTU too small for the recording
directory reports an error rather than retrying indefinitely; the user can
reconnect or try a compatible phone, and existing recordings are retained.
`resume()` explicitly continues the saved session from a visible app after a stop,
force-stop or a restart that Android does not automatically redeliver. Android may
redeliver a service intent after an ordinary system process kill, but that is not
a guarantee of continuous reception, and the Android task-manager stop is honored.
The same process can issue recording controls without a second BLE connection:

```java
// Worker thread; control of the current recording uses the same connection.
String result = RecordingSyncService.control(controlDir, hostSession,
    NativeRecordingControl.Action.STOP, 0);
```

The control method supports QUERY, PAUSE, RESUME and STOP of the existing session
while receiving. Start a new recording after reception is stopped. It uses the
existing session identity and can report an unconfirmed command; follow the
original control recovery rules rather than claiming a stop.
It is unavailable during reconnection. The host still owns permissions, UI, the
Android notification-permission experience and all user decisions. The library
manifest declares the `connectedDevice` foreground-service type and permissions;
Android restricts background starts, so the host must initiate start/resume while
visible unless it has a documented system exemption. Test lock screen, task-manager
stop, process termination and two-hour device operation on actual supported phones;
JVM simulation and an AAR build do not establish those results.

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
long meeting, offer retry and do not display it as complete. For a short meeting,
`markdown` may include an optional “原话核对” section from the same AI request;
its quotations are checked against the submitted transcript, but the AI's
association and the transcription may be wrong. Show that label and the quotes,
keep the original transcript, and do not infer that missing quotes mean failure.
When a short meeting has many detailed points, `markdown` may begin with an
optional “会议概览” produced in that same request. The complete `summary`,
decisions, action items and transcript remain available. The frontend may show
the overview first and let users expand the detailed summary; it should keep
decisions and action items accessible. Missing overview is not an error and does
not require another AI request.
A long-meeting result may be a draft when an AI chapter could not be linked to
source quotes. Its `markdown` can include a clearly labeled unverified reference
section containing the provider's text; display that label and keep the section
separate from confirmed tasks. Its suggested actions are not `actionItems` and
must not be silently imported into a checklist or calendar.
Even a complete result needs user review for recognition and factual accuracy. Never auto-save
generated tasks as confirmed or auto-import them into a calendar. Android network
permission, real TLS, service response quality and phone execution remain unverified.

`NativeMeetingQa.ask` answers a question against explicitly selected transcript
texts. Call it on a worker thread, after the user chooses which meetings to use.
It sends those texts and the question to the configured AI service; it does not
send audio, save the answer, or alter the stored meetings. This may incur service
charges. Build JSON with `question`, `documents` (an array of `{id, title, text}`),
`endpoint` (the full HTTPS chat-completions URL), and `model`; pass the service
key separately. The response contains `items`, each with `text` and `citation`
(`sessionId`, `title`, `quote`), plus `totalChunks`, `completedChunks` and
`incomplete` and `cancelled`. When a service-wide failure stops later segments,
optional `stopReason` explains the failure; preserve and display any returned
answers and their citations. If the first request fails, `ask` reports the error.
Show the cited text and original meeting; if `incomplete` is true,
tell the user that some parts were not processed and offer another attempt. A
literal source quote identifies supporting text, but does not guarantee that the
recognition or the interpretation is correct. If a source was edited while the
request ran, identify the answer as based on the earlier text. The host owns the
UI, credentials, network permission and any answer persistence. Long transcripts
are processed in segments and can take several minutes. Android execution and
real phone/card integration remain unverified.

If an incomplete result includes `resume`, the host can continue without repeating
completed segments: make the same request with `resume` containing `identity`
and `completed` from that result, plus `items` from the result. Keep the same
question, document order, titles and text, endpoint and model; discard the
checkpoint and query afresh after any such change. Credentials can be refreshed.
The returned items retain prior answers and citations. The host owns the
checkpoint; it is not automatically persisted across app closure. Continued
requests send only unfinished text segments, not audio.

For optional cancellation, include a unique nonempty `jobId` in the request and
call `NativeMeetingQa.cancel(jobId)` from another thread. A true result means the
running request will stop before the next segment; the active network request
may finish first. A false result means no job with that ID was running. Preserve
and label any returned partial answers and offer a retry. The API does not delete
audio or transcripts; the host may save a chosen answer as an explicitly marked
AI-generated note in the cited meeting using its existing meeting store.

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
service again. Each save also retains earlier results in app-private history;
`MeetingStore.MinutesHistory history = store.listMinutesHistory(meetingKey)`
returns newest first, with each version's `sourceChanged` and `sourceMissing`
flags. `unreadableFiles` reports damaged versions without hiding valid ones. The
host can show the saved JSON as an earlier version, separate from the current
result. To switch back, obtain the current meeting and minutes revisions and call
`store.restoreMinutesHistory(meetingKey, meeting.revision, current.revision,
history.versions.get(index).historyId)` on a worker. This saves the current result
to history before switching and retains the selected version's original transcript
identity. Check `sourceChanged` after restore and show it if the transcript has
changed. A revision conflict leaves the current result untouched; reload first.
Existing current meeting files remain readable by the previous backend,
but older backends cannot list or delete the new history files; use this version
when deleting results. `deleteMinutes(meetingKey)` explicitly removes the current
result, its history and backups, leaving its
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
experiments from the compiled library and an Android API jar. Put the compiled
`libcompanion_mobile_audio.so` and the matching pinned `libonnxruntime.so` and
`libsherpa-onnx-c-api.so` in `--jni-libs/arm64-v8a`; all three are included by
default. `--external-asr-runtime` keeps only the bridge for hosts that explicitly
provide compatible runtimes and notices themselves. That manually
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


### Export saved meeting documents (worker thread)

The backend can produce editable Word documents and FreeMind-compatible `.mm`
mind maps from a **saved** AI minutes result. No audio, transcript, or document
is uploaded by these calls; the host application owns the user's Save As or
share action. The optional `meeting` snapshot contributes saved notes and the
current task list, and a changed/missing transcript is explicitly marked.
Use a snapshot and minutes loaded from the same recording session.

```java
MeetingStore.Snapshot meeting = store.load(sessionKey);
MeetingStore.Minutes minutes = store.loadMinutes(sessionKey);
byte[] docx = NativeMeetingDocuments.word(title, minutes, meeting);
byte[] mindMap = NativeMeetingDocuments.mindmap(title, minutes, meeting);
// On explicit user choice, write the bytes to a user-selected destination.
```

The Android host can also write a local PDF from explicitly chosen saved content:

```java
MeetingPdf.Sections sections = new MeetingPdf.Sections(true, true, true);
// Open the stream from the user's selected destination and close it in the host.
MeetingPdf.write(title, minutes, meeting, sections, outputStream);
// After the user explicitly chooses sharing, create a content URI with the host's
// FileProvider or another appropriate provider, then show the system chooser:
Intent send = MeetingShare.file(contentUri, "application/pdf");
activity.startActivity(Intent.createChooser(send, "分享会议"));
```

PDF sections can independently include saved minutes, transcript, and user notes /
tasks. The transcript-only path does not require saved minutes. The stream remains
owned by the host; an error may leave a partial destination, so the host should
not present that file as complete. A changed/missing source or partial minutes is
labelled in the document. `MeetingShare.file` accepts a `content://` URI that the
host is entitled to grant; it neither creates a provider nor sends anything itself.
The host is responsible for the URI lifetime and user-selected destination.

Word MIME type is `application/vnd.openxmlformats-officedocument.wordprocessingml.document`;
`.mm` is FreeMind-compatible XML and requires a compatible mind-map application.
The backend does not include a document viewer, share UI, or mobile frontend.
Retain and present `assets/companion-document-export-notices.txt` with the host's
third-party notices. PDF rendering and sharing still require Android device testing.

### Portable local library backup (worker thread)

The host can back up its dedicated recording, meeting and control directories
as one local archive and restore it on another installation. Stop recording,
background reception, recognition, minutes generation and editing while making
the archive; resume them after the call. Include only the dedicated directories,
not the app's parent directory or credentials. Create the dedicated recording
and meeting directories before backup; pass null for an unused control directory.
The archive contains private
recordings and text and is **not encrypted**; let the user choose a private
location. Model downloads and decoded caches can be recreated and are not included.

```java
// Open with Android's document picker/content resolver on a worker thread.
// Discard a partial output document if write throws.
try (OutputStream out = context.getContentResolver().openOutputStream(backupUri)) {
    LibraryBackup.write(out, recordingsDir, meetingsDir, controlDir);
}
// Restore to a new, nonexistent private directory with an existing parent.
Path restored = context.getFilesDir().toPath().resolve("companion-restored-library");
try (InputStream in = context.getContentResolver().openInputStream(backupUri)) {
    LibraryBackup.restore(in, restored);
}
Path restoredRecordings = restored.resolve("recordings");
Path restoredMeetings = restored.resolve("meetings");
Path restoredControl = restored.resolve("control");
// Only after success should the host explicitly switch its directory configuration.
// Stop users of the old library before switching; retain the old library.
```

Callers own and close streams. Export reads source data multiple times to detect
changes; keeping all library writers stopped is still required, since this is
not a transaction across independent app components. A successful restore checks
the stored file hashes and publishes a new directory. Failure leaves existing
libraries unchanged. This API does not merge into an existing library, sync
with Windows, or configure Android UI. The caller must retain and activate the
three returned directories together. A control record is saved as data only;
the normal same-device reconciliation rules still apply before any device action.
The integrity check detects accidental corruption, not a maliciously forged archive.
Actual Android storage-picker, new-phone migration, and recording-card checks
remain to be verified on a phone.


### Background conversation review for long meetings

During AI minutes generation, the configured AI service may receive each task's source quotation and nearby transcript context. A task labelled as possibly background remains available for user review; this does not identify speakers or guarantee correct attribution. A mixed summary paragraph remains in place with a review notice; the structured summary and original transcript stay unchanged. No audio is sent by the minutes request. The host should preserve and display the original and the review label.
