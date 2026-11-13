# Relative gyro remote adapter

Unchanged GamepadMotionHelpers `GamepadMotion.hpp` and MIT license, pinned to `f1a76007ec058122a4bb6f19c816c6c0c7b7f12a` (version10): https://github.com/JibbSmart/GamepadMotionHelpers/tree/f1a76007ec058122a4bb6f19c816c6c0c7b7f12a

Only its static `CalculatePlayerSpaceGyro` is called. The Companion C++ wrapper changes axes/units: our X-right/Y-Type-C-front/Z-up and proper acceleration UP become upstream X-right/Y-up/Z-back and gravity DOWN. No GamepadMotion AHRS, gyro calibration, matrix state or MCU library is added. Existing board Fusion supplies normalized gravity and corrected full XYZ gyro using the existing32B CIM3 format. Mode3/options40 combines that format with the existing reliable CIN physical controls; legacy8 (CIM4 aim) and24 (CIM5 raw) remain unchanged.

Rust response reuses the existing1-Euro formula with explicit8Hz/.05 derivative parameters, followed by JoyShockMapper's zero-cutoff recovery (recovery0.5deg/s). JSM source: `bb69784488937e0a5e21988b966eccd9f04d504e`, `JoyShockMapper/src/main.cpp`, block following `honour gyro_cutoff_speed`. Its main MIT notice is in `JSM-LICENSE.md`. No JSM application, HID, SDL, virtual controller, game configuration or unrelated dependency is imported.

After the Owner128 trial rejected horizontal feel, the recommended profile uses
JSM's LOCAL single-axis selection (`GyroSpace::LOCAL`, `MOUSE_X_FROM_GYRO_AXIS`)
at the same pin: board-Y roll drives horizontal movement and board-X pitch
remains unchanged. Positive board-Y lowers the right edge and moves right.
The prior gravity-based player-turn mapping remains an explicit separate
selection; roll and yaw are never automatically blended. Full XYZ CIM3 is
required for roll; projected CIM4 cannot supply that axis.

The relative profile preserves subpixel displacement between frames, uses the physically labelled Type-C pitch sign, freezes button-pressure movement until a180ms drag threshold, and clears its filter on release/pause/ordinary-mouse takeover. Body taps now use the existing LSM6DSO hardware single-tap/reliable CIN event as left clicks; retries cannot click twice and a tap clears its impact's remaining velocity. Two distinct taps remain two clicks. Recorder double-tap marking and the legacy profile are retained. The UI uses a new saved-profile key, preserving old laser/planar preferences. There is no absolute screen-center projection or planar acceleration integration in this profile. No MCU code, sample rate, memory or processing changes are needed for this repair.

This is an implementation candidate. Formula checks, source-labelled direction and synthetic responsiveness are separate from actual enclosure feel and physical click/drag acceptance.

The Owner130 return-to-grip feedback adds JSM's existing `GYRO_OFF` clutch
semantics (same pinned main.cpp, GyroButtonAssignment): an explicit held key
disengages motion, release resumes from the same cursor. It is a separate
key-role choice; the original click/drag role remains available. Shell taps
remain the click source with the regrip role. No reverse-motion suppression
classifier, new calibration estimator, or MCU code is introduced. Windows
clicks use a single documented SendInput array containing target/down/up,
with optional QA submission-count/target tracing, rather than separate calls.

Owner131 output tracing showed accepted native clicks could target positions
hundreds of pixels behind the visible cursor. Direct-relative shell taps now
use the current cursor; the original100ms historical compensation remains in
the laser profile. A queued relative click also follows a real ordinary-mouse
takeover before native output. The clutch disengages motion, not shell clicks,
so it can stabilize a tap as well as regrip. These are input/axis adapters,
not new IMU classifiers. Received-tap feedback is independent of readiness;
an early tap remains consumed without an uncalibrated click or later replay.
