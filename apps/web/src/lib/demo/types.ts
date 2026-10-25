import type { Opportunity } from "../opportunities/types";

/** Public, sanitized plan preview (itinerary + aggregate budget note). Never per-member costs. */
export interface PlanPreview {
  title: string;
  start: string;
  end: string;
  activities: { label: string; start: string; end: string }[];
  /** Aggregate or redacted wording only. */
  budgetNote: string;
  notes?: string;
}

export interface PlanningIntent {
  /** e.g. "Dinner or a game night" */
  activity: string;
  /** "quick" = hours, "weekend" = days. Only changes the horizon scale, not the interface. */
  kind: "quick" | "weekend";
  horizonLabel: string;
  horizonStart: string;
  horizonEnd: string;
  groupNote: string;
  options: Opportunity[];
}

export interface WindowPreset {
  id: string;
  label: string;
  /** Simulator only: true if a replan can still satisfy everyone. */
  feasible: boolean;
}

export interface ScenarioDef {
  id: "quick" | "weekend";
  label: string;
  session: string;
  intent: PlanningIntent;
  members: readonly string[];
  baseEvents: unknown[];
  holdMessage: string;
  /** Members that have accepted the live version at the hold point. */
  initialAccepted: string[];
  initialVersion: number;
  initialRequired: number;
  previews: Record<number, PlanPreview>;
  windows: WindowPreset[];
  /** Simulator-only thresholds (cents). Never rendered. */
  budgetCurrentPlanCents: number;
  budgetCheapestPlanCents: number;
  revised: {
    hard_budget: { summary: string; preview: (base: PlanPreview) => PlanPreview };
    block_window: { summary: string; preview: (base: PlanPreview) => PlanPreview };
    withdraw: { summary: string; preview: (base: PlanPreview) => PlanPreview };
  };
}
