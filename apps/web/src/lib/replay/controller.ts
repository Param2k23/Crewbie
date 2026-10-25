/**
 * Deterministic fixture replay. Timers only pace *when a recorded event is revealed*;
 * they never create events or outcomes. Same events + same step count => same state.
 */
export interface Scheduler {
  set(fn: () => void, ms: number): unknown;
  clear(handle: unknown): void;
}

export const browserScheduler: Scheduler = {
  set: (fn, ms) => setTimeout(fn, ms),
  clear: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
};

export interface ReplaySnapshot {
  cursor: number;
  total: number;
  playing: boolean;
  /** Set when playback stopped at a hold point (e.g. waiting for the judge). */
  holdMessage: string | null;
  speed: number;
}

export interface ReplayOptions {
  events: unknown[];
  onEvent: (raw: unknown) => void;
  /** Called on reset so the owner can clear its reducer state. */
  onReset?: () => void;
  baseIntervalMs?: number;
  scheduler?: Scheduler;
  /** cursor index -> message. Playback pauses *before* revealing the event at that index. */
  holds?: Record<number, string>;
}

export class ReplayController {
  private events: unknown[];
  private readonly base: unknown[];
  private cursor = 0;
  private playing = false;
  private speed = 1;
  private handle: unknown = null;
  private releasedHolds = new Set<number>();
  private listeners = new Set<() => void>();
  private snap: ReplaySnapshot;
  private readonly sched: Scheduler;
  private readonly baseMs: number;

  constructor(private readonly opts: ReplayOptions) {
    this.base = opts.events;
    this.events = [...opts.events];
    this.sched = opts.scheduler ?? browserScheduler;
    this.baseMs = opts.baseIntervalMs ?? 1600;
    this.snap = this.compute();
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => void this.listeners.delete(fn);
  };
  getSnapshot = (): ReplaySnapshot => this.snap;

  private compute(): ReplaySnapshot {
    const hold = this.opts.holds?.[this.cursor];
    const held = hold !== undefined && !this.releasedHolds.has(this.cursor);
    return { cursor: this.cursor, total: this.events.length, playing: this.playing, holdMessage: held ? hold! : null, speed: this.speed };
  }
  private emit() {
    this.snap = this.compute();
    this.listeners.forEach((l) => l());
  }

  /** Reveal exactly one recorded event. Manual stepping passes through hold points deliberately. */
  step(): boolean {
    if (this.cursor >= this.events.length) return false;
    if (this.opts.holds?.[this.cursor] !== undefined) this.releasedHolds.add(this.cursor);
    this.opts.onEvent(this.events[this.cursor++]);
    this.emit();
    return true;
  }

  play() {
    if (this.playing) return;
    this.playing = true;
    this.emit();
    this.schedule();
  }
  pause() {
    this.playing = false;
    if (this.handle !== null) this.sched.clear(this.handle);
    this.handle = null;
    this.emit();
  }
  private schedule() {
    if (!this.playing) return;
    this.handle = this.sched.set(() => {
      this.handle = null;
      if (!this.playing) return;
      const hold = this.opts.holds?.[this.cursor];
      if (hold !== undefined && !this.releasedHolds.has(this.cursor)) {
        this.playing = false;
        this.emit();
        return;
      }
      if (!this.step()) {
        this.playing = false;
        this.emit();
        return;
      }
      this.schedule();
    }, this.baseMs / this.speed);
  }

  setSpeed(speed: number) {
    this.speed = Math.max(0.25, Math.min(8, speed));
    if (this.playing && this.handle !== null) {
      this.sched.clear(this.handle);
      this.schedule();
    }
    this.emit();
  }

  /** Queue additional recorded events (used by the labeled local simulator). */
  append(events: unknown[]) {
    this.events.push(...events);
    this.emit();
  }

  /** Release a hold point so playback may continue past it. */
  release() {
    this.releasedHolds.add(this.cursor);
    this.emit();
  }

  reset() {
    this.pause();
    this.cursor = 0;
    this.events = [...this.base];
    this.releasedHolds.clear();
    this.opts.onReset?.();
    this.emit();
  }

  dispose() {
    this.pause();
  }
}
