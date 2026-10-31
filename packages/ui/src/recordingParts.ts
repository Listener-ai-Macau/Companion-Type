/** One logical recording, represented as ordered local audio files. */
export interface RecordingPart { url: string; firstSample: number; samples: number }
const SAMPLE_RATE = 16_000;

export function recordingPartsDuration(parts: RecordingPart[]): number {
  if (!parts.length) throw new Error('这场录音没有可播放的文件。');
  let next = 0;
  for (const part of parts) {
    if (!part.url || !Number.isSafeInteger(part.firstSample) || !Number.isSafeInteger(part.samples)
      || part.firstSample !== next || part.samples <= 0 || !Number.isSafeInteger(next + part.samples)) {
      throw new Error('这场录音的分段不连续，请重新恢复。');
    }
    next += part.samples;
  }
  return next / SAMPLE_RATE;
}

/** Map a meeting-wide position to a file and its local offset. */
export function recordingPartAt(parts: RecordingPart[], seconds: number): { index: number; offset: number } {
  const duration = recordingPartsDuration(parts);
  if (!Number.isFinite(seconds) || seconds < 0 || seconds > duration) throw new Error('回听位置超出录音范围。');
  if (seconds === duration) return { index: parts.length - 1, offset: parts.at(-1)!.samples / SAMPLE_RATE };
  const sample = seconds * SAMPLE_RATE;
  let low = 0, high = parts.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (parts[middle].firstSample + parts[middle].samples <= sample) low = middle + 1;
    else high = middle;
  }
  return { index: low, offset: seconds - parts[low].firstSample / SAMPLE_RATE };
}
