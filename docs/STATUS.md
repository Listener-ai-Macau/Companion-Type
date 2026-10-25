# Readiness and Experience Boundaries

Updated 25 October 2026. The current local development delivery is **FW662 / UI84 / Boot575 with the Windows Type P575 joint release**, including the current recording-protocol handshake fixes. This is not a public release or whole-product acceptance claim. Later versions follow their actual delivery packages.

[User guide](USER_GUIDE.md) · [Product introduction](../README.md) · [简体中文](STATUS.zh-CN.md)

| Experience | Available now | Confirmed separately |
| --- | --- | --- |
| Pet and menus | Original expressions and accessories, gaze/emotion transitions, touch/motion response software, menus, quiet modes and status feedback remain. | Physical touch, assembled IMU axes, sound, optical fading/lines and long-term feel. |
| Personality and memory | Names, sixteen creative personalities and owner-confirmed deletable memories; explicit short-turn chat with a computer and bottom-line screen replies. | General low-volume recognition, long-term character and actual language experience. Wake-word entry is not connected. |
| Recording and sync | Device audio capture, Type reception/local save, grouped segments, integrity checks and protected reclaim; real recordings and daily-use audio material exist. | Actual capacity, long recordings, concurrency, reconnect recovery and content quality follow their own qualifications. Fragments are not a complete session. |
| Find and use content | My recordings offers direct text reading, optional playback, title/text/action edits, separate notes, search and multiple export formats. | Recognition and organization can be wrong; check important facts. A checklist does not send timed notifications. |
| Continue after a save failure | Actionable public error messages retain specific guards. A real occupied-file case retained input and allowed explicit retry after opening/closing help. | Other real faults, every platform and screen-reader behavior are not inferred from this single recovery route. |
| Updates | Windows software updates and complete matching pet packages are separate. Transfer completion and successful new application startup are distinct. | Release channels, physical recovery, performance and power conditions follow their deliveries. |
| Battery and other platforms | Battery level is an estimate; Windows is the current desktop usage path. | No verified battery-life duration is promised. Native macOS, iOS, Android and Linux products and formal account entitlements are separate; a phone diagnostic app is not a phone product. |

The speaker provides ordinary short prompts, not spoken chat replies. Closed eyes do not establish a qualified lowest-power state. A browser uses source-matched upper software and original resources with simulated peripherals; it cannot verify physical display, touch, motion, capture or power.

Capture, reception and local playback do not require cloud configuration first. Cloud transcription, organization and chat use the selected content with existing services. Formal accounts, fees, quotas, public downloads and support follow the actual release notice.

The local Windows software checkpoint is `a850d0fad2140e0e3b07a53989745aa5753792e5`. Screenshots show its retained P575 interface. Earlier notes below are historical, not current limits.

<details>
<summary>Earlier candidate records</summary>

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


</details>
