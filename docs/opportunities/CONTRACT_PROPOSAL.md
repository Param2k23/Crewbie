# Integrator proposal: activity discovery envelope

Status: proposed for cross-agent adoption, not a change to frozen contracts.

Keep `list_opportunities(campus, starts_after, ends_before, food_only)` and `get_opportunity(id)` unchanged. Existing consumers continue receiving canonical Opportunity mappings with campus/time/food fields. Optional `activity` metadata is additive and is emitted only when provided, consistent with the current additional-properties rule.

Adopt a new, opt-in `DiscoveryService.recommend(...)` envelope as documented in [ACTIVITY_DISCOVERY.md](ACTIVITY_DISCOVERY.md). Its `record_type` explicitly distinguishes verified source records, general ideas and synthetic fixtures. Ideas have null source URLs and no Opportunity object; they do not satisfy the frozen Opportunity schema and must never be forced into it with fictional dates, campus or evidence.

Proposed fields: `candidate_id`, `record_type`, `categories`, `horizon`, `known`, `fit`, `requires_verification` and optional `opportunity`. Purpose: support time-first and intent-first selection across planning horizons without implying venue inventory or reservable capacity. Safety: all fits explicitly set `availability_confirmed=false`; source quotes and uncertainties remain visible; no private preferences echoed; coordinator must perform its own constraint checks. No breaking field or enum changes requested. Agent 01 and coordinator should explicitly opt into this new interface after integrator review.

Venue convention: canonical start/end represent a verified listing validity period, with separate evidenced opening intervals. If the integrator prefers not to extend Opportunity to venues at all, keep venue candidates only in the opt-in envelope. Existing event-only consumers should continue using event providers. No shared schema was edited by Agent 02.
