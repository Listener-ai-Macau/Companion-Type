# Companion IMU pointer adaptation

Pinned sources and both MIT notices are included verbatim. The source revisions
are recorded in `upstream.json`; this directory contains no compiled upstream app.

| Upstream implementation | Companion integration |
| --- | --- |
| AirCursor `PointerMapper.axisSpeed`, `PointerSmoother` | Faithful Rust port in `packages/desktop-input/src/pointer.rs`, same 28 px/degree, bounded acceleration, exponential frame smoothing and 120 ms stale target |
| WatchPointer `OneEuroFilter`, laser projection | Same equations/constants in the same portable core; sensor time drives filtering, frame time drives interpolation |
| WatchPointer gravity-projected angular rate | CIM1 schema2 carries MCU-computed Fusion AHRS gravity and bias-corrected gyro; old schema1 raw sensors use the same pinned Fusion on desktop. Do not fuse schema2 twice; mounting/user feel still require physical validation |
| WatchPointer short tap / 0.35 s hold drag, pre-press pointing history | Physical CIN1/CIM1 button levels plus hardware double-tap serial; pre-press position, click/hold/release lifecycle |
| macOS cursor event APIs | Windows Enigo glue in `pointer/native.rs`, explicit UI activation, Esc exit |
| AirPods/Watch CoreMotion delivery | Existing LSM6DSO driver and encrypted CIN1 settings subscription; opt-in CIM1 integer stream, no second IMU driver or microphone stream |

The real FW66791 diagnostic channel was measured at about 1 Hz with the gyro
powered off, including presentation mode. It cannot drive the upstream pointer
effect directly. The new opt-in firmware mode keeps the existing sensor run
policy active and publishes each new32-byte sample near100Hz (104Hz gyro/417Hz tap accel in pointer only). Original794 capped this at26Hz and delivered62ms median gaps. The revised firmware uses the existing low-latency interval hint; actual revised latency is pending.
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

The authorized development-key recovery installed794 without deleting original
recordings/pairing metadata. A real1104-frame pointer trial moved the cursor but
Owner rejected drift/feel and no body-tap click. The revised100Hz/Fusion/tap batch
is not physically accepted. macOS integration remains untested.

Pinned xioTechnologies/Fusion MIT C is unchanged in fusion/. The MCU M33/FPU
RAM microbenchmark at61.43982MHz measured14–17us mean,23.24us maximum across
four synthetic phases, state160B, stack356B; this is not Flash execution, BLE,
recording/Opus concurrency or energy qualification. The product wrapper adds
timestamp/lifecycle bookkeeping (total168B). Source and raw result are in the
project IMU receipt. Fusion is active only in explicit pointer mode.
