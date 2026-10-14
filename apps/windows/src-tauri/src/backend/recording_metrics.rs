//! Transfer diagnostics describe stored payloads separately from audio time.
//! A catalog duration also handles legacy 8 kHz PCM and opaque COP1/IMA bytes.

pub(super) mod targets;

pub(super) struct CompletedPull {
    pub codec: u8,
    pub directory_duration_ms: u32,
    pub payload_bytes: usize,
    pub received_payload_bytes: u32,
    pub wire_bytes: u64,
    pub packets: u64,
    pub elapsed_s: f64,
    pub transport_ima: bool,
    pub dual_lane: bool,
    pub settle_ms: u64,
    pub live_prefix: bool,
    // Worker append/checkpoint work overlaps reception; never subtract its
    // duration from receive wall time. Queue wait blocks receive; final drain
    // and durable commit are measured after the last-packet timestamp.
    pub receive_store_us: u64,
    pub receive_store_peak_us: u64,
    pub receive_store_queue_wait_us: u64,
    pub receive_store_drain_us: u64,
}

pub(super) fn diagnostics(pull: CompletedPull) -> Vec<String> {
    let kind = match pull.codec {
        1 => "pcm16",
        2 => "stored_half_ima",
        3 => "opus16_cop1",
        _ => "unknown",
    };
    let valid_time = pull.elapsed_s.is_finite() && pull.elapsed_s > 0.0;
    let wire_rate = if valid_time { pull.wire_bytes as f64 / 1024.0 / pull.elapsed_s } else { 0.0 };
    // A resumed prefix was cached before this attempt, not transferred again.
    let payload_rate = if valid_time { f64::from(pull.received_payload_bytes) / 1024.0 / pull.elapsed_s } else { 0.0 };
    let ratio = if pull.wire_bytes > 0 { f64::from(pull.received_payload_bytes) / pull.wire_bytes as f64 } else { 0.0 };
    let duration_ms = if kind != "unknown" && pull.payload_bytes > 0 { pull.directory_duration_ms } else { 0 };
    let duration_source = if duration_ms > 0 { "catalog" } else { "unknown" };
    let pcm_metric = if pull.codec == 1 { format!(" pcm_bytes={}", pull.payload_bytes) } else { String::new() };
    // Compatibility labels for older diagnostic scripts; QM11 is evaluated
    // separately against the generated product targets and sustained sample.
    let p1_wire_50 = wire_rate >= 50.0 && pull.wire_bytes >= 102_400 && !pull.transport_ima;
    let p1_product_50 = payload_rate >= 50.0 && pull.received_payload_bytes >= 102_400;
    let mut lines = vec![
        format!(
            "recording pull done payload={} received_payload={} codec={} payload_kind={} wire={} packets={} wire_rate={:.1} KiB/s effective_payload_rate={:.1} KiB/s ratio={:.2}x elapsed={:.3}s transport_ima={} dual={} hit97={} hit97_cruise={} hit100={} hit100_cruise={} p1_wire_50={} p1_product_50={}",
            pull.payload_bytes, pull.received_payload_bytes, pull.codec, kind,
            pull.wire_bytes, pull.packets, wire_rate, payload_rate, ratio,
            if valid_time { pull.elapsed_s } else { 0.0 }, pull.transport_ima, pull.dual_lane,
            wire_rate >= 97.0, wire_rate >= 97.0, wire_rate >= 100.0, wire_rate >= 100.0,
            p1_wire_50, p1_product_50,
        ),
        format!(
            "recording_pull_metrics wire_kb_s={:.2} cruise_kb_s={:.2} effective_kb_s={:.2} dual_lane={} settle_ms={} wire_bytes={} payload_bytes={} received_payload_bytes={}{} elapsed_s={:.3} compress={} codec={} payload_kind={} audio_duration_ms={} duration_source={} live_prefix={} actual_received_kib_s={:.2} rate_basis=new_transport_payload_bytes timing_basis=host_first_to_last_packet compression_multiplier=none receive_store_ms={:.3} receive_store_peak_ms={:.3} receive_store_queue_wait_ms={:.3} receive_store_drain_ms={:.3}",
            wire_rate, wire_rate, payload_rate, pull.dual_lane, pull.settle_ms,
            pull.wire_bytes, pull.payload_bytes, pull.received_payload_bytes, pcm_metric,
            if valid_time { pull.elapsed_s } else { 0.0 }, pull.transport_ima, pull.codec,
            kind, duration_ms, duration_source, pull.live_prefix,
            payload_rate, pull.receive_store_us as f64 / 1000.0,
            pull.receive_store_peak_us as f64 / 1000.0,
            pull.receive_store_queue_wait_us as f64 / 1000.0,
            pull.receive_store_drain_us as f64 / 1000.0,
        ),
    ];
    if valid_time && duration_ms > 0 && !pull.live_prefix && pull.wire_bytes > 0
        && pull.received_payload_bytes > 0 && u64::from(pull.received_payload_bytes) <= pull.payload_bytes as u64
    {
        // Average stored bitrate and this attempt's transport ratio; an estimate
        // excludes reconnect/setup latency and does not verify a future transfer.
        let t10 = 600.0 * pull.elapsed_s * pull.payload_bytes as f64
            / f64::from(pull.received_payload_bytes) / (f64::from(duration_ms) / 1000.0);
        lines.push(format!(
            "recording pull project_10min: audio_content={:.3} min duration_source={} codec={} measured_elapsed={:.3}s wire={:.2} KiB/s project_10min_same_encoding_estimate_s={:.3} estimate=true excludes_setup=true",
            f64::from(duration_ms) / 60_000.0, duration_source, pull.codec, pull.elapsed_s, wire_rate, t10,
        ));
    }
    let qualified = valid_time && !pull.live_prefix && !pull.transport_ima && pull.codec == 3
        && duration_ms >= targets::MINIMUM_AUDIO_DURATION_MS
        && pull.received_payload_bytes >= targets::MINIMUM_RECEIVED_BYTES
        && u64::from(pull.received_payload_bytes) <= pull.payload_bytes as u64;
    let evaluation = |threshold: f64, strict: bool| {
        if !qualified { "not_evaluated" }
        else if (strict && payload_rate > threshold) || (!strict && payload_rate >= threshold) { "met" }
        else { "not_met" }
    };
    lines.push(format!(
        "recording_pull_target version=\"{}\" sample={} effective_kib_s={:.2} delivery_kib_s={} stretch_kib_s={} explore_kib_s={} qm11_payload={} qm11_payload_stretch={} qm11_payload_explore={} scope=payload_rate_only full_chain_acceptance=false",
        targets::VERSION, if qualified { "sustained" } else { "insufficient_or_inapplicable" }, payload_rate,
        targets::PAYLOAD_DELIVERY_KIB_S, targets::PAYLOAD_STRETCH_KIB_S, targets::PAYLOAD_EXPLORE_KIB_S,
        evaluation(targets::PAYLOAD_DELIVERY_KIB_S, targets::PAYLOAD_DELIVERY_STRICT), evaluation(targets::PAYLOAD_STRETCH_KIB_S, false),
        evaluation(targets::PAYLOAD_EXPLORE_KIB_S, false),
    ));
    lines
}

#[cfg(test)]
mod tests;
