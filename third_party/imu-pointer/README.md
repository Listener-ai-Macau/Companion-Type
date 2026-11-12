# Companion IMU pointer adaptation

Pinned sources and both MIT notices are included verbatim. The source revisions
are recorded in `upstream.json`; this directory contains no compiled upstream app.

| Upstream implementation | Companion integration |
| --- | --- |
| AirCursor `PointerMapper.axisSpeed`, `PointerSmoother` | Faithful Rust port in `packages/desktop-input/src/pointer.rs`, same 28 px/degree, bounded acceleration, exponential frame smoothing and 120 ms stale target |
| WatchPointer `OneEuroFilter`, laser projection | Same equations/constants in the same portable core; sensor time drives filtering, frame time drives interpolation |
| WatchPointer gravity-projected angular rate | CIM1 schema2 carries MCU-computed Fusion AHRS gravity and bias-corrected gyro; old schema1 raw sensors use the same pinned Fusion on desktop. Do not fuse schema2 twice; mounting/user feel still require physical validation |
| WatchPointer reliable short tap / 0.35 s hold drag, pre-press pointing history | Negotiated CIN1 pointer controls retain ordered DOWN/UP/click timestamps until host ACK; legacy CIM3 level/tap-serial fallback remains |
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


The next sensor adapter uses CIM1 schema3: Q14 unit gravity, corrected gyro,
and device-calibration readiness in bit1. A continuous measured stationary
second seeds upstream FusionBias; the host does not subtract another fixed
bias from an already adapting corrected rate. Only upstream FusionAhrsUpdate
with a zero magnetometer is used: consumer gravity is invariant to the
NoMagnetometer helper's startup yaw-zeroing. The real C test compares both
gravity outputs over5000 updates. No upstream vendor file is modified.
The mapping/filter equations were ported, but this did not establish end-to-end parity. The original v4 physical trial was rejected by Owner;1095 samples had85 gaps/2759 missing sequences and a disconnect. Earlier claims of unchanged click semantics did not cover the unreliable motion-only transport.


The next adapter explicitly negotiates pointer option8 and CIM1 schema4.
The MCU integrates heading at each sensor update BEFORE publication, using the
original Watch vertical angular-rate dot product and50ms integration clamp.
Failed aim delivery is superseded by the next absolute heading. The fixed32B
packet carries heading centidegrees, Q14 gravity, yaw/pitch rates and readiness;
the same original laser/1-Euro/frame-follow equations remain on the computer.

CIN1 CLICK512/DOWN1024/UP2048 are independent controls, with original device
timestamps and monotonically increasing sequence. Eight12B entries retain
ordered edges until a UID/epoch-verified CIN1 operation2 ACK naming the head.
Only the head is retried every40ms; a later ACK cannot consume an earlier edge.
Overflow4096 explicitly ends the host pointer session and releases any drag;
it cannot silently turn a lost release into a stuck mouse button.
Mode0/1 and legacy pointer option0 keep their prior wire behavior. The new
receiver negotiates option8, falls back to option0 with old firmware, drains
CIM4 motion bursts to their latest pose, and sends control ACKs concurrently
rather than blocking motion receipt for a GATT round trip.

This is a platform adaptation of the original architecture, not an assertion
of identical CoreMotion sensor accuracy or radio latency. Packet-loss replay
verifies recovered orientation and exactly-once physical controls; physical
feel and the separate long receive stalls remain unqualified until actual use.
