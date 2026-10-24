import { describe, expect, it } from "vitest";
import { ReplayController, Scheduler } from "@/lib/replay/controller";
import { fixtureEvents } from "@/lib/fixtures";
import { initialState, missionReducer } from "@/lib/events/reducer";

function fakeScheduler() {
  let queue: { fn: () => void; ms: number; id: number }[] = [];
  let id = 0;
  const s: Scheduler = {
    set: (fn, ms) => { queue.push({ fn, ms, id: ++id }); return id; },
    clear: (h) => { queue = queue.filter((q) => q.id !== h); },
  };
  return { s, tick: () => { const q = queue.shift(); q?.fn(); return !!q; }, pending: () => queue.length, last: () => queue.at(-1) };
}

function setup(holds?: Record<number, string>) {
  const sch = fakeScheduler();
  let state = initialState();
  const c = new ReplayController({
    events: fixtureEvents,
    scheduler: sch.s,
    holds,
    onEvent: (raw) => { state = missionReducer(state, { type: "ingest", raw }); },
    onReset: () => { state = initialState(); },
  });
  return { c, sch, get: () => state };
}

describe("ReplayController", () => {
  it("manual step reveals exactly one event at a time", () => {
    const { c, get } = setup();
    c.step();
    expect(get().log).toHaveLength(1);
    expect(c.getSnapshot().cursor).toBe(1);
  });
  it("play advances only via the scheduler and ends at the recorded final state", () => {
    const { c, sch, get } = setup();
    c.play();
    while (sch.tick());
    expect(get().log).toHaveLength(fixtureEvents.length);
    expect(get().view.confirmed).toBe(true);
    expect(c.getSnapshot().playing).toBe(false);
  });
  it("pause stops further reveals", () => {
    const { c, sch, get } = setup();
    c.play();
    sch.tick();
    c.pause();
    expect(sch.pending()).toBe(0);
    expect(get().log).toHaveLength(1);
  });
  it("no timer elapsed => no confirmation (never faked by time)", () => {
    const { get } = setup();
    expect(get().view.confirmed).toBe(false);
  });
  it("reset returns to an empty, identical-on-replay state", () => {
    const { c, sch, get } = setup();
    c.play();
    while (sch.tick());
    const first = get().view;
    c.reset();
    expect(get().log).toHaveLength(0);
    c.play();
    while (sch.tick());
    expect(get().view).toEqual(first);
  });
  it("hold points pause playback until released or stepped", () => {
    const { c, sch, get } = setup({ 3: "waiting for judge" });
    c.play();
    while (sch.tick());
    expect(get().log).toHaveLength(3);
    expect(c.getSnapshot().holdMessage).toBe("waiting for judge");
    c.step();
    expect(get().log).toHaveLength(4);
    expect(c.getSnapshot().holdMessage).toBeNull();
  });
  it("speed changes the interval", () => {
    const { c, sch } = setup();
    c.setSpeed(4);
    c.play();
    expect(sch.last()?.ms).toBe(400);
  });
});
