"""Synthetic standalone Unlock Card, availability and scheduling draft demo."""
import json

from .unlocks import assess_window, checkin_draft, solo_fallback, unlock_card


def main():
    context = dict(authorized=True, window_confirmed=True,
                   availability_start="2026-10-26T12:00:00-07:00", availability_end="2026-10-26T14:00:00-07:00",
                   personality="Roast Me", roast_opt_in=True)
    item = dict(title="Student equipment loan — FICTIONAL DEMO", category="benefit", synthetic=True,
                source_url="https://example.org/crewbie-demo/equipment", checked_at="2026-10-26T15:00:00Z",
                eligibility="unknown", restrictions=["Student ID may be required; eligibility not verified", "Booking availability unknown"],
                duration_minutes=45, travel_minutes_each_way=10, cost_verified=False,
                next_step="Inspect terms, confirm eligibility, then choose a solo plan or Find a Crew.")
    print("Crewbie Unlocks | LOCAL MOCK EVIDENCE | native Cubbie runtime UNVERIFIED")
    print(unlock_card(item, context, now="2026-10-26T16:00:00Z")["text"])
    print("Blank calendar is not availability:", json.dumps(assess_window(dict(context, window_confirmed=False))))
    print("Backend-independent solo option:", json.dumps(solo_fallback()))
    settings = dict(cadence="weekdays", local_time="09:00", timezone="America/Phoenix", notification="text", empty="silent")
    print("Native scheduling DRAFT, not registration:", json.dumps(checkin_draft(dict(context, alerts_opt_in=True, approved_checkin=settings), **settings)))


if __name__ == "__main__":
    main()
