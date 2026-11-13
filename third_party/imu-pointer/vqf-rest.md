# VQF rest detector adaptation

Upstream: https://github.com/dlaidig/vqf

Pinned revision: `86ba56bdd3158b9b05f9f9fe5596866ba326438c`.

Reference: [pyvqf.py](https://github.com/dlaidig/vqf/blob/86ba56bdd3158b9b05f9f9fe5596866ba326438c/vqf/pyvqf.py), the rest-detection portions of `updateGyr` / `updateAcc`, and `filterCoeffs`, `filterInitialState`, `filterStep`, `filterVec`. MIT copyright and permission are preserved in [VQF-MIT.txt](VQF-MIT.txt).

`packages/desktop-input/src/pointer/rest.rs` ports only those raw-signal deviation tests and their second-order Butterworth filter to Rust. No VQF attitude, Kalman bias estimator, magnetometer, matrix operations, or extra MCU algorithm is added. Gyro input uses degrees/second consistently for both observations and thresholds; acceleration uses m/s². Stream gaps reset the classifier. The adapter targets the actual100Hz CIM5 stream.

Device interaction parameters differ from upstream's general orientation defaults: `restFilterTau=0.1s`, `restMinT=0.12s`, `restThAcc=0.1m/s²`. The upstream gyro deviation threshold and absolute low-pass gyro limit remain2deg/s. These are explicit short-stroke pointer adaptation choices, not claimed upstream defaults or physical rest truth. They must be checked against unchanged upstream calculations and the saved failed capture before further hardware trials.

The classifier is independent of estimated gravity and velocity. Confirmed quiet input clears coarse mouse velocity/tail and updates its residual acceleration baseline, so a frozen AHRS error cannot sustain false motion. The old reference `Desktop::default()` still exposes the previous inertial integration for analysis; `Desktop::coarse_gestures()` is the experimental pointer path.

This has a real limitation: a six-axis IMU cannot distinguish prolonged smooth constant-speed translation from physical rest. The coarse pointer deliberately favors stopping over preserving unlimited coasting. This is not an optical mouse, metric position tracker, or a port of AirCursor/WatchPointer translation. Real feel, clicks and dragging remain unqualified until actual complete use; an offline reduction of drift is insufficient to declare sale readiness.
