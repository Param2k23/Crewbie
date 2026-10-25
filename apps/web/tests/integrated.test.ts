import { describe, expect, it } from "vitest";
import traces from "./data/integrated-traces.json";
import { feed } from "./helpers";

// Recorded by calling the real Python composition, not the frontend simulator.
describe("integrated backend event contracts", () => {
  for (const kind of ["unlocks", "evening", "weekend"] as const) {
    it(`${kind}: displays the actual selected winner and human commitments`, () => {
      const pending = feed(traces[kind].pending);
      const final = feed(traces[kind].confirmed);
      expect(pending.rejected).toEqual([]);
      expect(pending.view.currentVersion).toBe(traces[kind].snapshot.version);
      expect(pending.view.confirmed).toBe(false);
      expect(final.view.confirmed).toBe(true);
      expect(final.view.acceptedCount).toBe(4);
      expect(final.view.warnings).toEqual([]);
    });
  }
  it("a real weekend constraint change resets old approvals", () => {
    const state = feed(traces.weekend.replanned);
    expect(state.view.confirmed).toBe(false);
    expect(state.view.currentVersion).toBe(traces.weekend.replanned_snapshot.version);
    expect(state.view.acceptedCount).toBe(0);
  });
});
