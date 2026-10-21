use super::{diagnostics, CompletedPull};

fn actual_board_22() -> CompletedPull {
    CompletedPull {
        codec: 3, directory_duration_ms: 301_000, payload_bytes: 632_112,
        received_payload_bytes: 632_112, wire_bytes: 632_112, packets: 3293,
        elapsed_s: 43.863, transport_ima: false, dual_lane: true,
        settle_ms: 800, live_prefix: false,
        receive_store_us: 275_000, receive_store_peak_us: 32_000,
        receive_store_queue_wait_us: 11_000, receive_store_drain_us: 7_000,
    }
}

#[test]
fn actual_five_minute_cop1_is_not_twenty_seconds_of_pcm() {
    let lines = diagnostics(actual_board_22());
    assert!(lines[1].contains("audio_duration_ms=301000 duration_source=catalog"));
    assert!(lines[1].contains("wire_kb_s=14.07"));
    assert!(lines[1].contains("actual_received_kib_s=14.07 rate_basis=new_transport_payload_bytes"));
    assert!(lines[1].contains("compression_multiplier=none receive_store_ms=275.000 receive_store_peak_ms=32.000"));
    assert!(lines[1].contains("receive_store_queue_wait_ms=11.000 receive_store_drain_ms=7.000"));
    assert!(lines[1].contains("payload_kind=opus16_cop1"));
    assert!(!lines[1].contains(" pcm_bytes="));
    assert!(lines[2].contains("audio_content=5.017 min"));
    assert!(lines[2].contains("project_10min_same_encoding_estimate_s=87.435"));
    assert!(lines[2].contains("estimate=true excludes_setup=true"));
    assert!(!lines.join("\n").contains("10min_raw_pcm"));
}

#[test]
fn cached_half_prefix_does_not_double_reported_throughput() {
    let mut pull = actual_board_22();
    pull.received_payload_bytes = 316_056;
    pull.wire_bytes = 316_056;
    pull.elapsed_s = 21.9315;
    let lines = diagnostics(pull);
    assert!(lines[1].contains("effective_kb_s=14.07"));
    assert!(lines[1].contains("actual_received_kib_s=14.07"));
    assert!(lines[0].contains("ratio=1.00x"));
    assert!(lines[2].contains("project_10min_same_encoding_estimate_s=87.435"));
}

#[test]
fn catalog_time_preserves_legacy_half_rate_pcm_and_stored_ima() {
    for codec in [1, 2] {
        let mut pull = actual_board_22();
        pull.codec = codec;
        pull.directory_duration_ms = 1000;
        pull.payload_bytes = 16_000;
        pull.received_payload_bytes = 16_000;
        pull.wire_bytes = 4_000;
        pull.elapsed_s = 1.0;
        pull.transport_ima = true;
        let lines = diagnostics(pull);
        assert!(lines[1].contains("audio_duration_ms=1000"));
        assert_eq!(lines[1].contains(" pcm_bytes="), codec == 1);
        assert!(lines[2].contains("project_10min_same_encoding_estimate_s=600.000"));
    }
}

#[test]
fn incomplete_or_unknown_duration_has_no_ten_minute_claim() {
    for case in 0..6 {
        let mut pull = actual_board_22();
        match case {
            0 => pull.directory_duration_ms = 0,
            1 => pull.codec = 255,
            2 => pull.live_prefix = true,
            3 => pull.received_payload_bytes = 0,
            4 => pull.elapsed_s = f64::NAN,
            _ => pull.received_payload_bytes = 700_000,
        }
        let lines = diagnostics(pull);
        assert_eq!(lines.len(), 3);
        assert!(!lines.join("\n").contains("NaN"));
        assert!(lines.last().unwrap().contains("qm11_payload=not_evaluated"));
    }
}

#[test]
fn qm11_uses_new_payload_instead_of_wire_bytes_and_versioned_targets() {
    let mut pull = actual_board_22();
    pull.payload_bytes = 614_400;
    pull.received_payload_bytes = 614_400;
    pull.wire_bytes = 1_228_800;
    pull.elapsed_s = 10.0;
    let lines = diagnostics(pull);
    assert!(lines[1].contains("wire_kb_s=120.00"));
    assert!(lines[1].contains("actual_received_kib_s=60.00 rate_basis=new_transport_payload_bytes"));
    let target = lines.last().unwrap();
    assert!(target.contains(super::targets::VERSION));
    assert!(target.contains("effective_kib_s=60.00 delivery_kib_s=100 stretch_kib_s=100 explore_kib_s=120"));
    assert!(target.contains("qm11_payload=not_met qm11_payload_stretch=not_met"));
    assert!(target.contains("scope=payload_rate_only full_chain_acceptance=false"));

    let mut pull = actual_board_22();
    pull.elapsed_s = 20.0;
    pull.wire_bytes = 2_457_600;
    let lines = diagnostics(pull);
    assert!(lines.last().unwrap().contains("qm11_payload=not_met"));
}

#[test]
fn short_or_cached_receives_cannot_claim_sustained_payload_target() {
    for live in [false, true] {
        let mut pull = actual_board_22();
        pull.live_prefix = live;
        pull.received_payload_bytes = 1024;
        pull.elapsed_s = 0.001;
        let lines = diagnostics(pull);
        assert!(lines.last().unwrap().contains("qm11_payload=not_evaluated"));
    }
}

#[test]
fn owner_inclusive_100_gate_uses_unrounded_new_payload_wall_rate() {
    let mut pull = actual_board_22();
    pull.payload_bytes = 614_400;
    pull.received_payload_bytes = 614_400;
    pull.wire_bytes = 1_228_800;
    pull.elapsed_s = 6.0;
    assert!(!super::targets::PAYLOAD_DELIVERY_STRICT);
    assert_eq!(super::targets::PAYLOAD_DELIVERY_KIB_S,100.0);
    assert!(diagnostics(pull).last().unwrap().contains("qm11_payload=met "));
    let mut below = actual_board_22();
    below.payload_bytes = 614_400;
    below.received_payload_bytes = 614_400;
    below.wire_bytes = 1_228_800;
    below.elapsed_s = 6.00001;
    let lines = diagnostics(below);
    assert!(lines.last().unwrap().contains("effective_kib_s=100.00"));
    assert!(lines.last().unwrap().contains("qm11_payload=not_met "));
}
