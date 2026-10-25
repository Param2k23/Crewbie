import { existsSync } from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import UnlocksPage, { metadata } from "@/app/unlocks/page";
import { INSTALL_MESSAGE, SKILL_PATH } from "@/app/unlocks/_lib/install";
import { planningExamples } from "@/app/unlocks/_lib/planningExamples";

const html = renderToStaticMarkup(<UnlocksPage />);
const text = html.replace(/<[^>]+>/g, " ").replace(/&[a-z#0-9]+;/g, " ").replace(/\s+/g, " ");

describe("Cubbie x Crewbie landing page", () => {
  it("is built around Cubbie from the title to the footer", () => {
    expect(String(metadata.title)).toContain("Cubbie");
    expect(text).toContain("Text Cubbie. Plans actually happen.");
    expect(text).toContain("Everything starts with one text to Cubbie.");
    expect(text).toContain("Built on Cubbie for the Cubbie hackathon");
    expect((text.match(/Cubbie/g) ?? []).length).toBeGreaterThan(25);
  });

  it("shows the Cubbie x Crewbie lockup in the header and the footer", () => {
    expect(html.match(/aria-label="Crewbie"/g)?.length).toBe(2);
    expect(html.match(/>Cubbie<\/span><span[^>]*>×/g)?.length).toBe(2);
  });

  it("tells students to text Cubbie the install message for the real Skill folder", () => {
    expect(text).toContain(INSTALL_MESSAGE);
    expect(INSTALL_MESSAGE).toBe("Install https://github.com/Param2k23/Crewbie/tree/master/skills/crewbie-unlocks");
    expect(existsSync(path.resolve(__dirname, "../../..", SKILL_PATH, "SKILL.md"))).toBe(true);
  });

  it("keeps the numbered sections in order", () => {
    const labels = [...text.matchAll(/0(\d) \/ (?:Cubbie is|Discover|Make it|Fewer|Company)/g)].map((m) => Number(m[1]));
    expect(labels).toEqual([1, 2, 3, 4, 5]);
  });

  it("makes no claims the product cannot back", () => {
    expect(text).not.toMatch(/still being connected|does not match students/i);
    expect(text).toContain("A companion is never guaranteed");
    expect(text).toContain("never books, buys or joins anything without your yes");
    expect(text).not.toMatch(/guarantee[sd]? (a )?(match|companion)|official partner|endorsed by|\d+ ?%|\$\d/i);
  });

  it("keeps the planning walkthrough about Cubbie", () => {
    expect(planningExamples).toHaveLength(3);
    for (const example of planningExamples) expect(example[1]).toContain("Cubbie");
    expect(text).toContain("You text Cubbie");
  });

  it("keeps every illustrative item labeled as illustrative", () => {
    expect(text).toContain("Illustrative activity · Not a verified event listing");
    expect(text).toContain("Illustrative walkthrough");
  });
});
