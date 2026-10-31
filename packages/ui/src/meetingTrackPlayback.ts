/** Direct playback of the two saved meeting tracks, without a mixed copy. */
export interface MeetingPlaybackPart {url: string; firstSample: number; samples: number}
export interface MeetingPlaybackTracks {microphone: MeetingPlaybackPart[]; system: MeetingPlaybackPart[]}
export interface MeetingPlaybackState {position: number; duration: number; playing: boolean; error: string | null}
const RATE = 16_000;
const DRIFT_SECONDS = 0.15;

function validate(parts: MeetingPlaybackPart[]): number {
  let next = 0;
  for (const part of parts) {
    if (!part.url || !Number.isSafeInteger(part.firstSample) || !Number.isSafeInteger(part.samples)
      || part.firstSample !== next || part.samples <= 0 || !Number.isSafeInteger(next + part.samples)) {
      throw new Error('会议音轨分段不连续，无法回听。');
    }
    next += part.samples;
  }
  return next / RATE;
}
function partAt(parts: MeetingPlaybackPart[], seconds: number): MeetingPlaybackPart | undefined {
  const sample = Math.max(0, seconds * RATE);
  let lo = 0, hi = parts.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (parts[mid].firstSample + parts[mid].samples <= sample) lo = mid + 1;
    else hi = mid;
  }
  return parts[lo];
}
interface Channel {element: HTMLAudioElement; parts: MeetingPlaybackPart[]; active?: MeetingPlaybackPart}

/** Owns both elements; seeks and segment changes pause both before resuming.
 * Playback remains local. Sources must be authorized by the desktop backend. */
export class MeetingTrackPlayback {
  private readonly channels: Channel[];
  private readonly master: Channel;
  private readonly duration: number;
  private epoch = 0;
  private moving = false;
  private playing = false;
  private position = 0;
  private speed = 1;
  private timer: ReturnType<typeof setInterval> | null = null;
  private disposed = false;
  private readonly ended: Array<() => void>;
  private readonly waiting: Array<() => void>;
  private readonly failed: Array<() => void>;
  private cancelBufferWait: (() => void) | null = null;
  private readonly changed: (state: MeetingPlaybackState) => void;

  constructor(tracks: MeetingPlaybackTracks, microphone: HTMLAudioElement, system: HTMLAudioElement,
    changed: (state: MeetingPlaybackState) => void) {
    this.changed = changed;
    const micDuration = validate(tracks.microphone), systemDuration = validate(tracks.system);
    this.duration = Math.max(micDuration, systemDuration);
    if (!this.duration) throw new Error('这场会议没有可回听的音轨。');
    this.channels = [{element: microphone, parts: tracks.microphone}, {element: system, parts: tracks.system}];
    this.master = this.channels[micDuration >= systemDuration ? 0 : 1];
    this.ended = this.channels.map(channel => () => this.partEnded(channel));
    this.waiting = this.channels.map(channel => () => this.buffering(channel));
    this.failed = this.channels.map(() => () => {
      if (!this.playing || this.moving) return;
      this.position = this.currentPosition(); this.epoch++; this.playing = false;
      this.channels.forEach(c => c.element.pause()); this.report('会议音轨无法播放，请检查原文件。');
    });
    this.channels.forEach((channel, index) => {
      channel.element.addEventListener('ended', this.ended[index]);
      channel.element.addEventListener('waiting', this.waiting[index]);
      channel.element.addEventListener('error', this.failed[index]);
    });
    this.report(null);
  }
  private report(error: string | null) {
    if (!this.disposed) this.changed({position: this.position, duration: this.duration, playing: this.playing, error});
  }
  private currentPosition(): number {
    const part = this.master.active, element = this.master.element;
    if (this.playing && !this.moving && part && Number.isFinite(element.currentTime)) {
      return Math.min(this.duration, Math.max(0, part.firstSample / RATE + element.currentTime));
    }
    return this.position;
  }
  private async ready(channel: Channel, part: MeetingPlaybackPart, epoch: number): Promise<void> {
    const element = channel.element;
    if (channel.active?.url === part.url && element.readyState >= 1) {channel.active = part; return;}
    channel.active = part;
    await new Promise<void>((resolve, reject) => {
      let timeout: ReturnType<typeof setTimeout>;
      const clean = () => {clearTimeout(timeout);element.removeEventListener('loadedmetadata', success);element.removeEventListener('error', failure);};
      const success = () => {clean();resolve();};
      const failure = () => {clean();reject(new Error('会议音轨无法播放，请检查原文件。'));};
      element.addEventListener('loadedmetadata', success); element.addEventListener('error', failure);
      timeout = setTimeout(() => {clean();reject(new Error('会议音轨加载超时，请重试。'));}, 15_000);
      element.src = part.url; element.load();
      if (element.readyState >= 1) success();
    });
    if (epoch !== this.epoch || this.disposed) throw new Error('播放已停止。');
  }
  private async transition(position: number, shouldPlay: boolean): Promise<void> {
    if (this.disposed) return;
    this.cancelBufferWait?.(); this.cancelBufferWait = null;
    const epoch = ++this.epoch;
    this.moving = true;
    this.channels.forEach(c => c.element.pause());
    this.position = Math.min(this.duration, Math.max(0, position));
    try {
      const selected = this.channels.map(channel => partAt(channel.parts, this.position));
      await Promise.all(this.channels.map(async (channel, index) => {
        const part = selected[index];
        if (!part) {channel.active = undefined;return;}
        await this.ready(channel, part, epoch);
        if (epoch !== this.epoch || this.disposed) return;
        channel.element.playbackRate = this.speed; channel.element.preservesPitch = true;
        channel.element.currentTime = Math.max(0, this.position - part.firstSample / RATE);
      }));
      if (epoch !== this.epoch || this.disposed) return;
      this.playing = shouldPlay && this.position < this.duration;
      if (this.playing) await Promise.all(this.channels.filter((_, i) => selected[i]).map(c => c.element.play()));
      if (epoch !== this.epoch || this.disposed) return;
      this.moving = false;
      this.report(null);
    } catch (error) {
      if (epoch !== this.epoch || this.disposed) return;
      this.channels.forEach(c => c.element.pause()); this.playing = false; this.moving = false;
      this.report(error instanceof Error ? error.message : '会议音轨无法播放，请重试。');
    }
  }
  async play(): Promise<void> {
    if (this.position >= this.duration) this.position = 0;
    await this.transition(this.position, true);
    if (!this.timer && !this.disposed) this.timer = setInterval(() => this.synchronize(), 200);
  }
  pause(): void {
    this.position = this.currentPosition(); this.epoch++; this.playing = false; this.moving = false;
    this.cancelBufferWait?.(); this.cancelBufferWait = null;
    this.channels.forEach(c => c.element.pause()); this.report(null);
  }
  async seek(seconds: number): Promise<void> {
    if (!Number.isFinite(seconds)) throw new Error('回听位置无效。');
    await this.transition(seconds, this.playing);
  }
  setSpeed(speed: number): void {
    if (!Number.isFinite(speed) || speed < 0.5 || speed > 2) return;
    this.speed = speed; this.channels.forEach(c => {c.element.playbackRate = speed;});
  }
  private partEnded(channel: Channel): void {
    if (!this.playing || this.moving || !channel.active) return;
    const end = (channel.active.firstSample + channel.active.samples) / RATE;
    const next = Math.max(this.currentPosition(), end);
    if (next >= this.duration) {
      this.epoch++; this.position = this.duration; this.playing = false;
      this.channels.forEach(c => c.element.pause()); this.report(null); return;
    }
    void this.transition(next, true);
  }
  private buffering(channel: Channel): void {
    if (!this.playing || this.moving || this.disposed) return;
    this.position = this.currentPosition(); const epoch = ++this.epoch;
    this.moving = true; this.playing = false; this.channels.forEach(c => c.element.pause()); this.report(null);
    let timeout: ReturnType<typeof setTimeout>;
    const clean = () => {clearTimeout(timeout);channel.element.removeEventListener('canplay', resume);
      channel.element.removeEventListener('error', failure);this.cancelBufferWait = null;};
    const resume = () => {clean();if (epoch === this.epoch && !this.disposed) void this.transition(this.position, true);};
    const failure = () => {clean();if (epoch === this.epoch && !this.disposed) {
      this.moving = false; this.report('会议音轨暂时无法读取，请重试。');
    }};
    this.cancelBufferWait = clean;
    channel.element.addEventListener('canplay', resume);channel.element.addEventListener('error', failure);
    timeout = setTimeout(failure, 15_000);
  }
  /** Correct drift without changing either recording. */
  synchronize(): void {
    if (!this.playing || this.moving || this.disposed) return;
    this.position = this.currentPosition();
    for (const channel of this.channels) {
      if (channel === this.master) continue;
      const wanted = partAt(channel.parts, this.position);
      if (wanted?.url !== channel.active?.url) {void this.transition(this.position, true);return;}
      if (wanted && Math.abs(channel.element.currentTime - (this.position - wanted.firstSample / RATE)) > DRIFT_SECONDS) {
        channel.element.currentTime = Math.max(0, this.position - wanted.firstSample / RATE);
      }
    }
    this.report(null);
  }
  getPosition(): number {return this.currentPosition();}
  dispose(): void {
    this.disposed = true; this.epoch++; this.playing = false;
    this.cancelBufferWait?.(); this.cancelBufferWait = null;
    if (this.timer) clearInterval(this.timer); this.timer = null;
    this.channels.forEach((channel, index) => {
      channel.element.pause(); channel.element.removeEventListener('ended', this.ended[index]);
      channel.element.removeEventListener('waiting', this.waiting[index]);
      channel.element.removeEventListener('error', this.failed[index]);
      channel.element.removeAttribute('src'); channel.element.load();
    });
  }
}
