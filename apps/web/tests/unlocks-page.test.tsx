import { existsSync } from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import UnlocksPage, { metadata } from "@/app/unlocks/page";
import { DEMO_VIDEO_URL, INSTALL_MESSAGE, REPO_URL, SKILL_PATH } from "@/app/unlocks/_lib/install";
import { planningExamples } from "@/app/unlocks/_lib/planningExamples";

const html = renderToStaticMarkup(<UnlocksPage />);
const text = html.replace(/<[^>]+>/g, " ").replace(/&[a-z#0-9]+;/g, " ").replace(/\s+/g, " ");

describe("Cubbie x Crewbie landing page", () => {
  it("is built around Cubbie from the title to the footer", () => {
    expect(String(metadata.title)).toContain("Cubbie");
    expect(text).toContain("Text Cubbie. Plans actually happen.");
    expect(text).toContain("We built Crewbie on Cubbie. Here is why it works.");
    expect(text).toContain("Three layers. One Cubbie.");
    expect(text).toContain("Built on Cubbie for the Cubbie hackathon");
    expect((text.match(/Cubbie/g) ?? []).length).toBeGreaterThan(40);
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
    const labels = [...text.matchAll(/0(\d) \/ (?:Cubbie is|Discover|Make it|Fewer|Company|Built on Cubbie)/g)].map((m) => Number(m[1]));
    expect(labels).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("makes no claims the product cannot back", () => {
    expect(text).not.toMatch(/still being connected|does not match students/i);
    expect(text).toContain("A companion is never guaranteed");
    expect(text).toContain("asks for consent and never shares personal info apart from the logistics");
    expect(text).toContain("No booking, payment or automatic crew membership");
    expect(text).not.toMatch(/guarantee[sd]? (a )?(match|companion)|official partner|endorsed by|\d+ ?%|\$\d/i);
  });

  it("keeps the planning walkthrough about Cubbie", () => {
    expect(planningExamples).toHaveLength(3);
    for (const example of planningExamples) expect(example[1]).toContain("Cubbie");
    expect(text).toContain("You text Cubbie");
  });

  it("labels the sample card as an example and keeps the page free of fine-print noise", () => {
    expect(text).toContain("EXAMPLE UNLOCK");
    expect(text).toContain("Endless opportunities, endless possibilities");
    expect(text).not.toMatch(/Illustrative (categories|walkthrough|activity)|An illustrative example/);
  });

  it("makes the closing lockup a headline, not fine print", () => {
    expect(html).toMatch(/class="[^"]*finaleBrand[^"]*"[^>]*>Cubbie <span[^>]*>×<\/span> Crewbie/);
  });

  it("explains the six things Cubbie brings, in Cubbie's own capabilities", () => {
    for (const phrase of ["Your messages are the app.", "Cubbie remembers you.", "Cubbie knows your week.", "Cubbie does the research.", "Cubbie follows up.", "Cubbie keeps you in charge."]) {
      expect(text).toContain(phrase);
    }
  });

  it("maps the project to the three hackathon tracks and thanks the sponsor", () => {
    expect(text).toContain("Track 1 · Cubbie Skill");
    expect(text).toContain("Track 2 · Agents");
    expect(text).toContain("Track 3 · Group chat");
    expect(text).toContain("Thank you to the Cubbie team for sponsoring");
  });

  it("links to the open-source repo and shows the video button only when a video exists", () => {
    expect(html).toContain(`href="${REPO_URL}"`);
    expect(DEMO_VIDEO_URL === null ? !html.includes("Watch Cubbie") : html.includes(DEMO_VIDEO_URL)).toBe(true);
  });
});
