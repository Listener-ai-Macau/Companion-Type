# Companion IMU pointer adaptation

Pinned sources and both MIT notices are included verbatim. The source revisions
are recorded in `upstream.json`; this directory contains no compiled upstream app.

| Upstream implementation | Companion integration |
| --- | --- |
| AirCursor `PointerMapper.axisSpeed`, `PointerSmoother` | Faithful Rust port in `packages/desktop-input/src/pointer.rs`, same 28 px/degree, bounded acceleration, exponential frame smoothing and 120 ms stale target |
| WatchPointer `OneEuroFilter`, laser projection | Same equations/constants in the same portable core; sensor time drives filtering, frame time drives interpolation |
| WatchPointer gravity-projected angular rate | Companion adapter substitutes low-pass accelerometer proper acceleration for Apple's fused gravity and subtracts a stationary measured gyro bias; this difference requires physical validation |
| WatchPointer short tap / 0.35 s hold drag, pre-press pointing history | Physical CIN1/CIM1 button levels, pre-press position, click/hold/release lifecycle |
| macOS cursor event APIs | Windows Enigo glue in `pointer/native.rs`, explicit UI activation, Esc exit |
| AirPods/Watch CoreMotion delivery | Existing LSM6DSO driver and encrypted CIN1 settings subscription; opt-in CIM1 integer stream, no second IMU driver or microphone stream |

The real FW66791 diagnostic channel was measured at about 1 Hz with the gyro
powered off, including presentation mode. It cannot drive the upstream pointer
effect directly. The new opt-in firmware mode keeps the existing sensor run
policy active and publishes the newest 32-byte six-axis sample up to about 26 Hz.
Its physical rate, board CPU cost, mounting axes and user feel are not qualified
by host tests or a successful build.

The portable core has cross-language CRC/unit fixtures, calibration, stale input,
button/drag, sequence and clock-wrap tests. `pointer_cpu` measures a synthetic
mapping workload only; it never moves the OS cursor and does not measure BLE,
OS event injection, board CPU or final user experience.

The Windows app exposes relative and laser modes in the connected-device area,
with calibration, pause, recenter and exit. Ordinary recording and hold-to-talk
remain separate device modes. Disconnect while holding a pointer button retains
the old key owner until release, so release cannot start a recording.

New firmware installation currently requires recovery from the deleted original
development signing key. New development credentials are stored outside caches.
Prepared replacement Boot/CUP artifacts do not mean board trust was changed or
that OTA/physical pointer acceptance passed. macOS integration remains untested.
