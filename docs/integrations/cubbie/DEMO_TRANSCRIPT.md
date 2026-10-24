# Local demo evidence

Executed 2026-10-24 on branch agent-01-cubbie with Python 3.9.5. This is simulator evidence, **not actual Cubbie execution**. The brief IDs vary per run.

Commands:

```powershell
python -B -m unittest discover -s tests/cubbie -v
python -B -m integrations.cubbie.demo --simulate-schedule
```

Observed: **18 tests passed**, covering canonical fixture output fields, campus/time/food filtering, half-open boundaries and minimum overlap, expiry/freshness, missing and invalid event data, duplicate/conflicting IDs, dietary uncertainty and unsuitability, source links, restricted access, missing venue, preferences, ambiguous times, consent, mock timing, idempotency, cancellation, revocation and unavailable provider.

Representative stdout excerpt (fixture title punctuation normalized for readability):

```text
Campus Pulse | LOCAL SIMULATOR | Track 1 runtime UNVERIFIED
[DEMO FIXTURE - fictional event] Engineering Club Pizza Meetup - DEMO ONLY
2026-10-26T12:00-07:00 to 2026-10-26T13:00-07:00 (America/Phoenix)
Venue: Sample public campus venue - NOT A REAL LISTING.
Food mentioned in listing. Free meal and remaining availability are not guaranteed. Diet not verified; ask the organizer about ingredients and dietary suitability.
Public access unknown; verify entry policy. RSVP requirements unknown.
Source: https://example.org/crewbie-demo/pizza
Checked: 2026-10-24T18:00:00Z
Check the source before attending. Reply 'Find company' to request consent-based matching.
```

Observed private brief: intent=find_campus_food, campus=Tempe, opportunity_id=opp_demo_pizza, wants_companion=false, synthetic=true, requirements_to_verify includes vegetarian_options and event_entry_policy.

Observed Find company result: intent=find_companion, wants_companion=true, requirements_to_verify includes matching_consent. No match search or introduction performed.

Observed provider failure:

```text
PROVIDER_UNAVAILABLE: Sponsor runtime and scheduled delivery are unverified; use private preview
```

Explicit scheduling simulation registered demo-alert-1 in mock mode. Dispatch returned one mock due notice with `sent: false`, asking for a regenerated private preview from the current catalog before real delivery. No external notification occurred.
