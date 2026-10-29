# Device capability compatibility

Current scope: Windows Type and the matching Companion firmware sources, 2026-10-29. This is a source contract, not proof that every device, Android client, migration or physical path has passed. The original CP01-03 three-client requirement remains open.

## Rules used by current Type

Firmware/build identifiers identify a delivery; they do not grant features. Read the relevant protected characteristic and validate its schema, length, properties and feature fields. Missing or malformed information is unknown/unsupported. Do not reinterpret an unknown revision as a legacy request or overwrite stored data to repair it. A connection check is not an operation receipt; controls recheck their own live status and ownership.

| Capability | Current wire evidence and compatibility | Unknown/missing behavior |
|---|---|---|
| Device identity | `DEVICE_STATUS`, schema1, at least20 bytes. Optional36-byte tail contains MCU UID and UI generation. | Identity fields remain unknown. A legacy20-byte status does not grant a UID or a resource generation. |
| IMU / speaker | Valid schema1 `IMU_STATUS` (26 bytes) / `SPEAKER_STATUS` (16 bytes) plus populated/online state. | Do not infer physical availability from firmware numbers or a discovered UUID. |
| Finding the pet | Supported speaker status, explicit byte9 bit0, then the existing owned start/stop receipts. | Older snapshots lacking the flag do not enable finding. |
| Recording capacity | WBA identity and validated `CCP1` / `CCQ2` tail, layout and allocation geometry. Discard requires its explicit flag. | No estimated geometry or guessed discard support. Existing recording preflight remains authoritative. |
| Recorder control / transfer | Existing `recording_wire` identity/status/ownership and payload contracts. | This change does not migrate or relax these lower-layer protocols. Their original qualification remains. |
| Pet caption | READ status and WRITE control; the exact PCS1 revisions below. | Reject before BEGIN; no fallback to an older command. The same parser also checks subsequent capability/visible/cancel receipts. |
| Host snapshot | `companion.host.v1` belongs to the matched Type frontend/backend artifact. | A TypeScript type is not a separate cross-version wire validation guarantee. Future host/Android migration still requires an explicit implemented adapter and preservation evidence. |

## PCS1 caption compatibility and migration

All supported revisions use exactly16 status bytes and the `PCS1` marker. Bytes8–11 and12–15 remain the owned request and visible tokens. The row count is bounded by13. Firmware sources establish these existing variants:

| Revision (byte7 high nibble) | Source reference | Accepted state / extension | Selected BEGIN |
|---|---|---|---|
| 0 | Firmware `902363a0`, `product_pet_chat.c` | State0–5; original reserved bytes5 and7 are zero | PCP1 op1 |
| 1 | Firmware `9375a25c` | State0–5; admission blocker byte5 and surface in byte7 bits0–1; bits2–3 zero | PCP1 op1 |
| 2 | Firmware `8ac9c8c0`, retained in current736 source `3770eba21bd882e800332ab4475165b68e70a569` | State0–6; same flags; state6 is bounded reservation | PCP1 op5 |
| 3–15, wrong marker/length, reserved bits, impossible state/row count | No supported adapter | Rejected, with a matching-update or unreadable-status message | None |

This is negotiation of an existing command, not an on-device data migration. Current firmware continues accepting legacy op1; Type uses op5 only after a valid revision2 report. Future revisions require an explicit parser/command mapping and compatibility evidence before support is enabled. Nothing here rewrites recordings, profiles, settings, ownership or the original source text.

Production enforcement: `apps/windows/src-tauri/src/backend/ble_bridge/pet_caption.rs` calls `pet_caption_protocol.rs` before any caption write. The same gate is used by the spoken-chat preflight before starting capture. Parser tests cover the full capability-byte space and malformed receipts; they do not simulate a real board, visible e-paper or successful speech processing.

## Remaining original work

The Windows source review above is not the whole three-client matrix. Android client feature mapping, persistent schema migrations and each cross-version device/host operation still follow their original owners and evidence. Preserve existing fail-closed recording/storage/OTA checks and lower-layer work; do not create a second capability protocol simply to replace this remaining task with a document.
