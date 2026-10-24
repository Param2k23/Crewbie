export interface Opportunity {
  opportunity_id: string;
  title: string;
  campus: string;
  start_at: string;
  end_at: string;
  location_label: string | null;
  food_status: "none" | "listed" | "confirmed_by_organizer" | "unknown";
  food_detail: string;
  dietary_suitability: "known_suitable" | "known_unsuitable" | "unknown";
  access_status: "public" | "restricted" | "unknown";
  rsvp_required: boolean | null;
  source_url: string;
  checked_at: string;
  synthetic: boolean;
}
