# Campus opportunity source audit

Audit date: 2026-10-24. Method: read-only public browser/search retrieval without credentials, cookies, registration or CAPTCHA solving. Browser results may be cached; search crawl dates are not organizer update times. No claim of exhaustive coverage or fresh inventory.

## Observed access

| Source | Observed result | Available fields / limits |
| --- | --- | --- |
| [ASU portal guidance](https://eoss.asu.edu/clubs/manage-your-student-organization) | Public | ASU identifies Sun Devil Central as its organization platform; supports event RSVPs and Event Pass attendance. Older Sun Devil Sync references should not drive a connector. |
| [Central general directory](https://sundevilcentral.eoss.asu.edu/events) | Redirect to `/webapp/auth/login?msg=LOGIN_REQUIRED&redirect=events` | Authenticated directory; no records extracted and no login attempted. |
| [Student Organizations and Leadership events](https://sundevilcentral.eoss.asu.edu/admin/events/) | Public organization landing page | Names and dates for upcoming October/November 2026 events. Organization coverage only, not the whole directory. |
| [Snack Session detail](https://sundevilcentral.eoss.asu.edu/admin/rsvp_boot?id=412803) | Public detail; private venue | Organizer, Tempe tag, Oct 29 2026, 12:30–14:00 MST, description with snack evidence and officer audience, registration option. Venue requires sign-in: preserve null. Free registration is not explicit free-food evidence. RSVP offered does not prove RSVP mandatory. |
| [Central calendar helper](https://sundevilcentral.eoss.asu.edu/ics_helper?TB_iframe=true&embed=1&height=550&modal=true&mode=set&width=850) | Public subscription information | Advertises school-wide public ICS calendar; personal feed requires login. Group feeds may include member/officer-only records based on role. Actual feed payload, timestamp semantics and food fields not validated. Do not enumerate private feeds. |
| [ASU Events food detail](https://asuevents.asu.edu/event/la-mesa-culture-healing-and-medicine-food) | Public | Date, MST time, museum venue/address, public/free categories, food description and RSVP link. August 30 2026 event is past and excluded from current recommendations. Category Free concerns event cost; no dietary or remaining-inventory proof. Calendar download link returned a tool error; ICS payload unverified. |
| [Central robots](https://sundevilcentral.eoss.asu.edu/robots.txt), [ASU Events robots](https://asuevents.asu.edu/robots.txt) | Browser tool reported inaccessible | Rules unknown, not permission granted. No broad automated crawl performed. |

## Food and attendance observation

The Snack Session page includes the short statement “Plus, there are snacks!” This supports `food_status=listed` only. Its organizer is Student Organizations and Leadership; its description targets club officers. Use `access_status=restricted` conservatively and retain the audience text, rather than interpreting public page visibility as unrestricted attendance. A private venue stays null; the organizer contact address must not become the venue. Its outer time range contains two shorter session options, so retain that ambiguity for a human to verify. No attendee identities or counts are ingested. [Detail source](https://sundevilcentral.eoss.asu.edu/admin/rsvp_boot?id=412803).

## Access policy and selected approach

Primary candidate for future automated ingestion: public ASU Events details, conditional on verified robots/terms, permitted request method and rate limits. Public Central organization detail pages are a useful supplemental source with field-level restrictions. Public readability alone does not establish bulk reuse permission. Terms/rate limits/API authorization remain unverified; no production crawler is enabled.

The implemented adapter accepts manually verified or otherwise authorized **structured imports**, with explicit caller permission and access metadata. It rejects denied responses, login redirects and challenges without traversing them. This is not a live scraper or an authenticated connector. No guessed API endpoints, private session reuse or personal feed tokens are used.

Immediate fallback is the existing three fictional shared fixtures, with DEMO titles, `synthetic=true`, fixture provenance and an explicit warning. Fallback requires explicit configuration for failing providers and reports `SOURCE_UNAVAILABLE`; it never silently substitutes fixtures for live results.

## Freshness and remaining blockers

`checked_at` means source retrieval/verification time, never organizer confirmation time. The service marks checks older than 24 hours or in the future stale; default search excludes them and ended events. Details remain retrievable with warnings. Search index recency cannot reset freshness or guarantee food remains.

Live ingestion remains conditional: verify robots/terms, obtain permitted feed/API access and rate limits, then implement bounded timeout/retry/cache behavior and genuine transport tests. No network adapter, HTTP server, organizer verification workflow, geocoding or inventory feed is claimed. ASU authorization and Agent 01 are not needed for the offline service. Dietary evidence and RSVP/entry certainty are often missing; unknown values are retained.
