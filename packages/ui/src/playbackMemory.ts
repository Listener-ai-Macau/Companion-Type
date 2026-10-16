/** Local listening preferences only. Keys come from the native original hash,
 * never from an asset URL, title or path. No audio or meeting content is stored. */
export const playbackSpeeds = [0.5, 0.75, 1, 1.25, 1.5, 2];
export interface PlaybackMemory { version: 1; position: number; duration: number; speed: number; completed: boolean }
const key = (identity?: string) => identity && /^[a-f0-9]{64}$/.test(identity) ? `companion.playback.v1:${identity}` : null;
export function loadPlaybackMemory(identity?: string): { value: PlaybackMemory | null; failed: boolean } {
  const id = key(identity); if (!id) return {value:null, failed:false};
  try {
    const raw = window.localStorage.getItem(id); if (!raw) return {value:null, failed:false};
    const v = JSON.parse(raw);
    if (v?.version !== 1 || !Number.isFinite(v.position) || !Number.isFinite(v.duration)
      || v.duration <= 0 || v.position < 0 || v.position > v.duration || !playbackSpeeds.includes(v.speed)
      || typeof v.completed !== 'boolean') return {value:null, failed:false};
    return {value:v, failed:false};
  } catch { return {value:null, failed:true}; }
}
export function savePlaybackMemory(identity: string | undefined, value: PlaybackMemory): boolean {
  const id = key(identity); if (!id) return true;
  try { window.localStorage.setItem(id, JSON.stringify(value)); return true; } catch { return false; }
}
export function clearPlaybackMemory(): boolean {
  try {
    const storage=window.localStorage;
    for(let i=storage.length-1;i>=0;i--){const id=storage.key(i);if(id?.startsWith('companion.playback.v1:'))storage.removeItem(id);}
    return true;
  } catch {return false;}
}
