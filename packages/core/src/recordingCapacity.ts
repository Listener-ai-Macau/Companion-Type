import type { CompanionV1RecordingCapacity } from './companionV1';
type Capacity = CompanionV1RecordingCapacity;
function geometry(c: Capacity): [number, number] | null | undefined {
  if (c.segmentFrames == null && c.segmentExtentBytes == null) return undefined;
  const f = c.segmentFrames, e = c.segmentExtentBytes;
  return Number.isSafeInteger(f) && Number.isSafeInteger(e) && f! > 0 && e! > 0 ? [f!, e!] : null;
}
export function recordingCapacityAvailableSeconds(c: Capacity): number {
  if (c.usedEntries >= c.maxEntries) return 0;
  const g = geometry(c);
  if (g === null) return 0;
  if (g) return Math.floor(Math.min(Math.floor(c.largestFreeExtent / g[1]), c.maxEntries - c.usedEntries) * g[0] / 50);
  return Math.max(0, Math.floor((c.largestFreeExtent - c.reserveHeadroom) / c.bytesPerSecond));
}
export function recordingCapacityRequiredBytes(c: Capacity, seconds: number): number {
  if (!Number.isFinite(seconds) || seconds < 0) return Infinity;
  const g = geometry(c);
  if (g === null) return Infinity;
  if (g) return Math.ceil(seconds * 50 / g[0]) * g[1];
  return Math.ceil((seconds * c.bytesPerSecond + c.reserveHeadroom) / 4096) * 4096;
}
export function recordingCapacityCanFit(c: Capacity, seconds: number, requiredBytes = recordingCapacityRequiredBytes(c, seconds)): boolean {
  if (c.usedEntries >= c.maxEntries) return false;
  const bytes = requiredBytes, g = geometry(c);
  return Number.isFinite(bytes) && bytes <= c.largestFreeExtent
    && (g === undefined || (g !== null && Math.ceil(seconds * 50 / g[0]) <= c.maxEntries - c.usedEntries));
}
