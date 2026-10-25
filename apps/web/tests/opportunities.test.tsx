// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CampusPulse } from "@/components/CampusPulse";
import { fixtureOpportunities } from "@/lib/fixtures";
import { availabilityMatch, dietBadge, foodBadge } from "@/lib/opportunities/wording";

describe("Campus Pulse wording", () => {
  it("never claims free food now or dietary guarantees for unverified listings", () => {
    const { container } = render(<CampusPulse />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/free food (now|available)/i);
    expect(text).not.toMatch(/guaranteed|vegetarian[- ]friendly|halal|vegan/i);
    expect(text).toMatch(/availability unknown/);
    expect(text).toMatch(/unverified/);
  });
  it("labels fixture listings and shows source + freshness", () => {
    render(<CampusPulse />);
    const cards = within(screen.getByRole("list", { name: "Opportunities" })).getAllByRole("listitem");
    expect(cards).toHaveLength(3);
    for (const c of cards) {
      expect(within(c).getByText(/Demo listing, not real/)).toBeInTheDocument();
      expect(within(c).getByRole("link")).toHaveAttribute("href", expect.stringContaining("example.org"));
      expect(within(c).getByText(/Last checked/)).toBeInTheDocument();
    }
  });
  it("Find company is disabled and explains why", () => {
    render(<CampusPulse />);
    for (const b of screen.getAllByRole("button", { name: "Find company" })) expect(b).toBeDisabled();
    expect(screen.getAllByText(/needs your opt-in/i).length).toBeGreaterThanOrEqual(3);
  });
  it("is activity-agnostic: demo activity ideas appear with the same uncertainty labels", () => {
    render(<CampusPulse />);
    const ideas = within(screen.getByRole("list", { name: "Demo activity ideas" })).getAllByRole("listitem");
    expect(ideas.length).toBe(5);
    expect(screen.getByText(/Flagstaff scenic day/)).toBeInTheDocument();
  });
  it("food and dietary badges stay honest for every fixture state", () => {
    const [pizza, , workshop] = fixtureOpportunities;
    expect(foodBadge(pizza!).label).toMatch(/unknown/);
    expect(foodBadge({ ...pizza!, food_status: "confirmed_by_organizer" }).label).toMatch(/leftover amount unknown/);
    expect(dietBadge(pizza!)).toMatch(/unverified/);
    expect(foodBadge(workshop!).label).toMatch(/unknown/);
  });
  it("availability match uses pure time overlap", () => {
    const [pizza, tacos] = fixtureOpportunities;
    expect(availabilityMatch(pizza!, "2026-10-26T12:00:00-07:00", "2026-10-26T13:30:00-07:00")).toBe("fits");
    expect(availabilityMatch(pizza!, "2026-10-26T12:30:00-07:00", "2026-10-26T13:30:00-07:00")).toBe("partial");
    expect(availabilityMatch(tacos!, "2026-10-26T12:00:00-07:00", "2026-10-26T13:30:00-07:00")).toBe("none");
  });
});
