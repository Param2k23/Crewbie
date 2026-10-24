import type { Opportunity } from "./types";

/** Campus time: ASU campuses in this fixture are in Arizona (no DST). */
export const CAMPUS_TZ = "America/Phoenix";

export function foodBadge(o: Opportunity): { label: string; tone: "neutral" | "warn" | "good" } {
  switch (o.food_status) {
    case "listed":
      return { label: "Food mentioned in listing; availability unknown", tone: "warn" };
    case "confirmed_by_organizer":
      return { label: "Organizer says food is planned; leftover amount unknown", tone: "good" };
    case "none":
      return { label: "No food listed", tone: "neutral" };
    default:
      return { label: "Food not mentioned / unknown", tone: "neutral" };
  }
}

export function dietBadge(o: Opportunity): string {
  switch (o.dietary_suitability) {
    case "known_suitable":
      return "Dietary fit: evidence on file for your preference";
    case "known_unsuitable":
      return "Dietary fit: known unsuitable for your preference";
    default:
      return "Dietary fit: unverified, check with the organizer";
  }
}

export function accessBadge(o: Opportunity): string {
  if (o.access_status === "public") return "Open to the public";
  if (o.access_status === "restricted") return `Restricted entry${o.rsvp_required ? "; RSVP required" : ""}`;
  return "Entry policy unknown" + (o.rsvp_required === true ? "; RSVP required" : o.rsvp_required === null ? "; RSVP status unknown" : "");
}

export function formatCampusTime(iso: string, withDate = true): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    timeZone: CAMPUS_TZ,
    weekday: withDate ? "short" : undefined,
    month: withDate ? "short" : undefined,
    day: withDate ? "numeric" : undefined,
    hour: "numeric",
    minute: "2-digit",
  }).format(d);
}

export type Overlap = "fits" | "partial" | "none";

/** Does the event overlap the student's free window? Pure time arithmetic, no travel-time claims. */
export function availabilityMatch(o: Opportunity, startIso: string, endIso: string): Overlap {
  const s = Date.parse(o.start_at), e = Date.parse(o.end_at);
  const a = Date.parse(startIso), b = Date.parse(endIso);
  if (e <= a || s >= b) return "none";
  return s >= a && e <= b ? "fits" : "partial";
}
