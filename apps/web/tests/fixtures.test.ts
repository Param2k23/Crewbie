import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("fixture copies", () => {
  for (const f of ["agent_events.json", "opportunities.json", "scenarios.json"]) {
    it(`${f} matches docs/implementation/fixtures`, () => {
      const here = resolve(__dirname, "../src/lib/fixtures", f);
      const canon = resolve(__dirname, "../../../docs/implementation/fixtures", f);
      expect(readFileSync(here, "utf8")).toBe(readFileSync(canon, "utf8"));
    });
  }
});
