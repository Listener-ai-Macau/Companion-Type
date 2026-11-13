# Relative gyro remote adapter

Unchanged GamepadMotionHelpers `GamepadMotion.hpp` and MIT license, pinned to `f1a76007ec058122a4bb6f19c816c6c0c7b7f12a` (version10): https://github.com/JibbSmart/GamepadMotionHelpers/tree/f1a76007ec058122a4bb6f19c816c6c0c7b7f12a

Only its static `CalculatePlayerSpaceGyro` is called. The Companion C++ wrapper changes axes/units: our X-right/Y-Type-C-front/Z-up and proper acceleration UP become upstream X-right/Y-up/Z-back and gravity DOWN. No GamepadMotion AHRS, gyro calibration, matrix state or MCU library is added. Existing board Fusion supplies normalized gravity and corrected full XYZ gyro using the existing32B CIM3 format. Mode3/options40 combines that format with the existing reliable CIN physical controls; legacy8 (CIM4 aim) and24 (CIM5 raw) remain unchanged.

Rust response reuses the existing1-Euro formula with explicit8Hz/.05 derivative parameters, followed by JoyShockMapper's zero-cutoff recovery (recovery0.5deg/s). JSM source: `bb69784488937e0a5e21988b966eccd9f04d504e`, `JoyShockMapper/src/main.cpp`, block following `honour gyro_cutoff_speed`. Its main MIT notice is in `JSM-LICENSE.md`. No JSM application, HID, SDL, virtual controller, game configuration or unrelated dependency is imported.

The relative profile preserves subpixel displacement between frames, uses the physically labelled Type-C pitch sign, freezes button-pressure movement until a180ms drag threshold, and clears its filter on release/pause/ordinary-mouse takeover. Body tap click is off by default in this profile; recorder double-tap marking and the legacy profile are retained. The UI uses a new saved-profile key, preserving old laser/planar preferences. There is no absolute screen-center projection or planar acceleration integration in this profile.

This is an implementation candidate. Formula checks, source-labelled direction and synthetic responsiveness are separate from actual enclosure feel and physical click/drag acceptance.
