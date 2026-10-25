// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ArenaFallback } from "@/components/ArenaFallback";
import { StatusPanel } from "@/components/Inspector";
import { fixtureEvents } from "@/lib/fixtures";
import { buildSceneModel } from "@/lib/scene/model";
import { feed, approvalFlow, ev } from "./helpers";

describe("2D fallback shows true state without WebGL", () => {
  it("rejected proposal: conflict is shown and nothing looks confirmed", () => {
    const s = feed(approvalFlow().slice(0, 3));
    render(<ArenaFallback view={s.view} />);
    expect(screen.getByRole("status")).toHaveTextContent(/hard constraint/i);
    expect(screen.getByRole("img")).toHaveAccessibleName(/rejected/i);
  });
  it("pending approvals are not described as confirmed", () => {
    const s = feed(approvalFlow(2, ["a", "b"]));
    const m = buildSceneModel(s.view);
    expect(m.core.status).toBe("awaiting_approval");
    expect(m.summary).toMatch(/2 of 4/);
    render(<StatusPanel view={s.view} />);
    expect(screen.getByText("Pending approvals")).toBeInTheDocument();
    expect(screen.queryByText("Confirmed")).toBeNull();
  });
  it("confirmed fixture replay renders confirmed", () => {
    const s = feed(fixtureEvents);
    render(<StatusPanel view={s.view} />);
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "4");
  });
  it("sync warnings are announced as alerts", () => {
    const s = feed([...approvalFlow(2, ["a"]), ev(30, "proposal_confirmed", { plan_id: "p2", version: 2, accepted_count: 4, required_count: 4 })]);
    render(<StatusPanel view={s.view} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/CONFIRM_MISMATCH/);
    expect(screen.queryByText("Confirmed")).toBeNull();
  });
  it("scene model scales to the group and never invents members", () => {
    const m = buildSceneModel(feed(fixtureEvents.slice(0, 2)).view);
    expect(m.nodes).toHaveLength(4);
    expect(m.nodes.every((n) => n.ref === null)).toBe(true);
    expect(m.edges).toHaveLength(0);
  });
});
