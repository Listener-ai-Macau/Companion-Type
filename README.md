# Companion Type

Companion Type is the standalone host app for Companion hardware.

It keeps Companion-specific controls out of Listener Type and shares one V1 protocol model across:

- `apps/windows`: Tauri Windows desktop shell.
- `apps/mobile`: reserved mobile shell. Native mobile framework is intentionally deferred until the team-provided framework lands.
- `packages/core`: Companion V1 GATT boundary, fixture state, control payloads, and tests.
- `packages/ui`: reusable Companion dashboard UI.

## Commands

```powershell
npm install
npm run test
npm run build
npm run build:windows
npm run build:mobile
cargo test --manifest-path apps/windows/src-tauri/Cargo.toml --lib --no-run
```

The V1 hardware backend is still gated by real board validation. Until BLE is connected, both shells use deterministic fixture state.
