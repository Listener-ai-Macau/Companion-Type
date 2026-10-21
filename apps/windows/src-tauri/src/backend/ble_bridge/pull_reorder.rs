//! Keep dual-notify reordering bounded when an earlier offset is missing.
use std::{collections::BTreeMap, time::Instant};

use super::RecordingChunk;

// Covers four ready-notification bursts, at most 28 KiB of product payload.
// More distant data remains on the board and can be requested again.
const MAX_PENDING_CHUNKS: usize = 128;

#[derive(Default)]
pub(super) struct PendingChunks {
    chunks: BTreeMap<u32, (RecordingChunk, Instant)>,
    first_arrival: Option<Instant>,
    last_validated_arrival: Option<Instant>,
}

impl PendingChunks {
    #[cfg(test)]
    pub fn insert(&mut self, chunk: RecordingChunk, next_offset: u32) {
        self.insert_at(chunk, next_offset, Instant::now());
    }

    pub fn insert_at(&mut self, chunk: RecordingChunk, next_offset: u32, arrived_at: Instant) {
        if chunk.byte_offset < next_offset {
            return;
        }
        if !chunk.payload.is_empty() && chunk.flags & super::RECORDING_CHUNK_ERROR_FLAG == 0 {
            // Start when data reaches the host, before a ready burst is drained,
            // reordered or written. Dropped/resent data still costs receive time.
            self.first_arrival = Some(self.first_arrival.map_or(arrived_at, |first| first.min(arrived_at)));
        }
        if self.chunks.len() == MAX_PENDING_CHUNKS
            && !self.chunks.contains_key(&chunk.byte_offset)
        {
            let last = *self.chunks.last_key_value().expect("full reorder window").0;
            if chunk.byte_offset >= last {
                return;
            }
            // Always admit the awaited offset, keeping the nearest future data.
            self.chunks.pop_last();
        }
        self.chunks.insert(chunk.byte_offset, (chunk, arrived_at));
    }

    pub fn take(&mut self, offset: u32) -> Option<(RecordingChunk, Instant)> {
        while self.chunks.first_key_value().is_some_and(|(&key, _)| key < offset) {
            self.chunks.pop_first();
        }
        self.chunks.remove(&offset)
    }

    // Only the caller that checked packet identity/offset/CRC may advance the
    // final timestamp. An unrelated or never-used future packet cannot do so.
    pub fn validated(&mut self, arrived_at: Instant) {
        self.last_validated_arrival = Some(self.last_validated_arrival
            .map_or(arrived_at, |last| last.max(arrived_at)));
    }

    pub fn elapsed_seconds(&self) -> Option<f64> {
        Some(self.last_validated_arrival?.saturating_duration_since(self.first_arrival?)
            .as_secs_f64().max(0.001))
    }

    pub fn full_gap(&self, offset: u32) -> bool {
        self.chunks.len() == MAX_PENDING_CHUNKS && !self.chunks.contains_key(&offset)
    }

    pub fn clear(&mut self) {
        self.chunks.clear();
        // A live storage retry is part of the same receive attempt. Retain its
        // elapsed time rather than making recovery appear faster by restarting.
    }

    #[cfg(test)]
    pub fn offsets(&self) -> Vec<u32> {
        self.chunks.keys().copied().collect()
    }

    #[cfg(test)]
    pub fn len(&self) -> usize { self.chunks.len() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn chunk(offset: u32) -> RecordingChunk {
        RecordingChunk {
            recording_id: 17, packet_sequence: offset / 224, byte_offset: offset,
            total_length: 0, payload_length: 224, flags: super::super::RECORDING_CHUNK_COMPACT_FLAG,
            packet_crc32: 0, final_sha256: [0; 32], payload: vec![(offset / 224) as u8; 224],
        }
    }

    #[test]
    fn missing_offset_cannot_buffer_a_whole_recording_and_is_always_admitted() {
        let mut pending = PendingChunks::default();
        // The first packet is absent while several MiB of later callbacks arrive.
        for index in 1..20_000 { pending.insert(chunk(index * 224), 0); }
        assert_eq!(pending.len(), MAX_PENDING_CHUNKS);
        assert_eq!(pending.offsets(), (1..=128).map(|n| n * 224).collect::<Vec<_>>());
        assert!(pending.full_gap(0));
        pending.insert(chunk(0), 0);
        assert_eq!(pending.len(), MAX_PENDING_CHUNKS);
        assert!(!pending.full_gap(0));
        let mut restored = Vec::new();
        for index in 0..128 {
            restored.extend_from_slice(&pending.take(index * 224).expect("nearest data retained").0.payload);
        }
        // A restart from this exact cursor supplies the data excluded by the cap.
        let next = restored.len() as u32;
        assert_eq!(next, 128 * 224);
        for index in (128..512).rev() { pending.insert(chunk(index * 224), next); }
        for index in 128..256 {
            restored.extend_from_slice(&pending.take(index * 224).unwrap().0.payload);
        }
        let expected = (0..256).flat_map(|n| vec![n as u8; 224]).collect::<Vec<_>>();
        assert_eq!(restored, expected);
        assert_eq!(pending.len(), 0);
    }

    #[test]
    fn delayed_other_lane_and_duplicates_preserve_one_ordered_original() {
        let mut pending = PendingChunks::default();
        for index in 0..40 { pending.insert(chunk((index ^ 1) * 224), 0); }
        for index in 0..40 {
            let offset = index * 224;
            pending.insert(chunk(offset), offset);
            let accepted = pending.take(offset).unwrap().0;
            assert_eq!(accepted.byte_offset, offset);
            assert_eq!(accepted.payload, vec![index as u8; 224]);
            pending.insert(chunk(offset), offset + 224);
            assert!(!pending.full_gap(offset + 224));
        }
        assert_eq!(pending.len(), 0);
    }

    #[test]
    fn arrival_time_precedes_burst_processing_and_durable_io() {
        let first = Instant::now();
        let mut pending = PendingChunks::default();
        pending.insert_at(chunk(0), 0, first);
        pending.insert_at(chunk(224), 0, first + std::time::Duration::from_millis(40));
        // Consume an already-ready burst much later: timestamping take/append
        // here would shrink the measured 40ms receive window toward zero.
        let (_, at) = pending.take(0).unwrap();
        pending.validated(at);
        let (_, at) = pending.take(224).unwrap();
        pending.validated(at);
        assert_eq!(pending.elapsed_seconds(), Some(0.04));
    }

    #[test]
    fn out_of_order_retries_keep_the_first_arrival_and_latest_needed_packet() {
        let first = Instant::now();
        let mut pending = PendingChunks::default();
        pending.insert_at(chunk(224), 0, first);
        pending.insert_at(chunk(224), 0, first + std::time::Duration::from_millis(400));
        pending.insert_at(chunk(0), 0, first + std::time::Duration::from_millis(800));
        for offset in [0, 224] {
            let (_, at) = pending.take(offset).unwrap();
            pending.validated(at);
        }
        // Acceptance order must not move the end backwards; a duplicate must
        // not move the start forwards and hide the wait for the missing offset.
        assert_eq!(pending.elapsed_seconds(), Some(0.8));
    }

    #[test]
    fn cached_prefix_and_unvalidated_future_data_do_not_set_the_receive_end() {
        let first = Instant::now();
        let mut pending = PendingChunks::default();
        pending.insert_at(chunk(0), 224, first - std::time::Duration::from_secs(1));
        pending.insert_at(chunk(224), 224, first);
        pending.insert_at(chunk(448), 224, first + std::time::Duration::from_millis(20));
        pending.insert_at(chunk(896), 224, first + std::time::Duration::from_secs(5));
        assert_eq!(pending.elapsed_seconds(), None);
        for offset in [224, 448] {
            let (_, at) = pending.take(offset).unwrap();
            pending.validated(at);
        }
        pending.clear();
        assert_eq!(pending.elapsed_seconds(), Some(0.02));
    }
}
