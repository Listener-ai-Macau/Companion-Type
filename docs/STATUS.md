# Readiness and experience boundaries

Updated 2026-10-04. This describes the **FW1.1.18 / UI36 and Type user-experience r2 development candidate**. This GitHub update publishes presentation documents and assets only; it does not publish the local engineering changes or installer. The current repository branch is not the complete source snapshot of that candidate.

| Experience | Implemented and checked | Still awaiting validation |
| --- | --- | --- |
| A little companion | Retained expressions, blinking, accessory clock, touch/motion reactions and four nonverbal pet sounds; software behavior checks | New-board display, touch feel, enclosure acoustics, loudness, wearability and battery life |
| Capture in the moment | Physical controls, preparing/recording/saving states, Opus/NOR storage, offset-based transfer recovery, CRC/SHA checks and exact reclaim acknowledgement | Real WBA capture and acoustics, concurrent storage/BLE behavior and recovery after an actual disconnection |
| Useful content afterward | Type playback, title/minutes edits, full-text search, transcription, both minutes modes in the completed online flow and file exports with action items in minutes; local candidate installed and regression-tested | Installed native GUI/audio/save dialogs; new board through real ASR and accurate final minutes in both modes |

## Software evidence

- Type: 223 Rust tests passed, zero failed, 11 ignored; core, four React suites and Windows/mobile builds passed. The mobile build is a fixture shell, not a released native mobile app.
- The formal MSI was installed; installed EXE/DLL matched its extracted payload. Installed read-only CLI checks accepted the matching FW/UI identities.
- The original official in-app browser preview works. Browser fixtures do not establish native GUI or hardware acceptance.
- FW1.1.18 / UI36 is unchanged by the latest UX work. Existing comparison evidence covers 9,493 UI states, with changes restricted to version text in 34 About states.

## Hardware blockers

- EPD_RES has no confirmed MCU control endpoint; display readiness remains blocked.
- A 68K:68K divider gives about 2.1V at a 4.2V battery, beyond the 1.8V ADC measurement range. Charger PG/STAT pull-ups remain unconfirmed.
- Display, touch, acoustics, battery life, power-loss update recovery and the full new-board meeting chain await hardware.

## Product limits

- The first version uses pet sounds; spoken conversation and a deliverable wake-word feature are not available.
- Record-first means transcribing after capture, not necessarily offline recognition. Cloud ASR receives audio and a cloud minutes service receives transcript text. Configure your own services; provider costs and quotas apply.
- Type's online capture flow has a 43-minute maximum. Device recording defaults to 30 minutes, with 15/30/60/no-timer options; device settings, free contiguous storage or errors can stop it earlier. No-timer remains capacity-limited. Gapless continuous segmentation is not available.
- USB-C supplies power only on this PCB. The six-pin connector is for first installation and maintenance, not routine use; plugging in USB does not establish a data connection.
- Hardware acceptance is pending. No claim of production availability, an out-of-box finished product or a measured battery-life figure is made.

## Image provenance

The pages reuse existing Companion screen/art previews without modifying the source PNG pixels. The surrounding frame is illustrative. These are not new-board photographs; clocks, battery and Bluetooth icons are sample state. See the [asset provenance](assets/companion/provenance.json).
