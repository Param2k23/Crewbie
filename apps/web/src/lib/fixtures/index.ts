import agentEvents from "./agent_events.json";
import opportunitiesFile from "./opportunities.json";
import scenariosFile from "./scenarios.json";
import type { Opportunity } from "../opportunities/types";

/** Canonical fixture copies (see scripts/sync-fixtures.mjs). */
export const fixtureEvents: unknown[] = agentEvents.events;
export const fixtureNotice: string = agentEvents.fixture_notice;
export const fixtureOpportunities = opportunitiesFile.opportunities as Opportunity[];
export const opportunitiesNotice: string = opportunitiesFile.fixture_notice;

/** Only the non-private brief is read; private profiles in scenarios.json are deliberately never imported. */
const campusPulse = scenariosFile.scenarios.find((s) => s.id === "campus_pulse");
export const campusPulseBrief = campusPulse?.student_brief as
  | { availability_start: string; availability_end: string; campus: string; requirements_to_verify: string[]; opportunity_id: string }
  | undefined;
