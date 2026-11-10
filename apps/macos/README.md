# Companion Mac candidate

Native macOS14+ receiver for the Companion WBA shared recorder core. This is a
development candidate, not a claim of real Mac/BLE/accessibility qualification.
Windows/Android daily installations are unchanged. Firmware needs CIN1 (787+).

The app connects through CoreBluetooth, explicitly selects recorder or desktop
dictation mode, receives only the current dictation's sealed logical session,
verifies exact segment CRC/SHA and contiguous sample identities, retains raw
COP1 originals, decodes once across segments and saves a local note. The decoder
directly imports the existing product COP1 parser and sample window; it does not
fork those formats. A completed durable local copy can precisely confirm its
own physical segments for reclamation. Old recordings are never auto-collected.

Hold the card key in desktop mode to speak, release to save and transcribe. Set
your own compatible transcription endpoint/model/key in Settings. Keys use the
macOS Keychain. There is no Companion account or subscription check. A configured
remote provider receives the audio you ask it to transcribe; local endpoints are
also supported. Original export remains available without transcription.

Text targets the editor focused at the beginning of dictation. Results stay in
the library when that target changes. Double-tap undo is scoped to the last
inserted span; an unsupported editor gets an explicit message instead of a
blind Undo. Optional shake/flick gestures need real enclosure qualification.
Physical microphone kill requires a hardware revision; this app does not claim it.

On a Mac with Xcode Command Line Tools, Rust and Homebrew Opus:

```sh
brew install opus
./script/build_and_run.sh
```

The same entry supports `--build`, `--verify`, `--debug`, `--logs` and
`--telemetry`. Build output is `dist/CompanionMac.app`; local adhoc signing is
for engineering only. Distribution signing and notarization are not done.
`swift test` validates current C-produced CIN1 and existing recording-wire
fixtures, packet CRC/resume/terminal SHA and local original export.

The bundled `Contents/MacOS/companion-mcp` is a local stdio MCP server. Configure
it as a command in your own Claude/Cursor client; optional `--library PATH`
selects a library. It offers `search_notes`, `read_note`, resource listing and
reading, with raw recording identities and highlight timestamps. It has no cloud
client, API keys, erase or device-control tools. The configured AI client decides
which returned notes it includes in its own context.

Remaining actual qualification: complete macOS build, real card pairing and
held recording/release/receive, first-word audio, editor insertion/undo, OS
permissions, disconnect/resume/reclamation and actual gesture sensitivity.
The independent firmware encoder timing and final long-recording gates remain
open in the original project backlog.
