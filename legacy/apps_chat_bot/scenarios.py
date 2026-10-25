"""Scripted mock-chat scenarios for the activity-agnostic Host. Synthetic, offline."""
from __future__ import annotations

from .demo import ROSTER, SESSION, Chat, build


def _deliver(chat, host, label="Planner (mock A4) returns a validated public snapshot"):
    snap = host.negotiation.next_snapshot()
    return chat.host_does(label, host.present_proposal, snap)


def _summary(svc, host):
    p = svc.active_proposal(SESSION)
    s = svc.get_commitment_summary(SESSION, p.plan_id, p.version)
    print(f"  >> v{p.version} state={s['proposal_state']} accepted={s['accepted_count']}/{s['required_count']} members={s['members']}")
    return s


def weekend() -> int:
    host, svc, provider, sink, listener, clock, consent = build()
    chat = Chat(host, provider, clock)
    print("=== Scenario: vague weekend idea to confirmed plan, then a change (synthetic) ===\n")
    chat.say("stu_maya", "Let's do something this weekend")
    _deliver(chat, host)
    first = svc.active_proposal(SESSION)
    for who in ROSTER:
        chat.say(who, f"I accept version {first.version}")
    s1 = _summary(svc, host)
    chat.say("stu_jordan", "Can we move this to Sunday?")
    print(f"  >> after change request: {svc.get_commitment_summary(SESSION, first.plan_id, first.version)['proposal_state']}")
    _deliver(chat, host, "Planner returns revised version")
    old = svc.get_commitment_summary(SESSION, first.plan_id, first.version)
    print(f"  >> old version summary: error={old['error_code']} accepted={old['accepted_count']}")
    chat.say("stu_alex", f"I accept version {first.version}")
    cur = svc.active_proposal(SESSION)
    for who in ROSTER:
        chat.say(who, f"I accept version {cur.version}")
    s2 = _summary(svc, host)
    n = len(sink.of_type("proposal_confirmed"))
    print(f"\nproposal_confirmed events: {n} (one per confirmed version)")
    ok = s1["confirmed"] and old["accepted_count"] == 0 and s2["confirmed"] and cur.version == first.version + 1 and n == 2
    return 0 if ok else 1


def dinner() -> int:
    host, svc, provider, sink, listener, clock, consent = build()
    chat = Chat(host, provider, clock)
    print("=== Scenario: evening meetup, mixed responses (synthetic) ===\n")
    chat.say("stu_alex", "Anyone free for dinner tomorrow?")
    chat.say("stu_taylor", "dinner tomorrow sounds good, anyone?")  # second ask while one is in flight
    _deliver(chat, host)
    v = svc.active_proposal(SESSION).version
    chat.say("stu_alex", f"I accept version {v}")
    chat.say("stu_maya", "maybe")
    chat.say("stu_jordan", "yes if it's cheaper")
    _summary(svc, host)
    clock.advance(hours=7)
    chat.host_does("Gentle follow-up for the silent member", host.follow_up)
    chat.say("stu_taylor", f"I accept version {v}")
    chat.say("stu_maya", f"I accept version {v}")
    chat.say("stu_jordan", "can we make it cheaper?")
    print(f"  >> change request sent to planner: {host.negotiation.requests[-1]['aspects']}")
    _deliver(chat, host, "Planner returns cheaper version")
    cur = svc.active_proposal(SESSION)
    for who in ROSTER:
        chat.say(who, f"I accept version {cur.version}")
    s = _summary(svc, host)
    return 0 if s["confirmed"] and cur.version == v + 1 else 1


def newgroup() -> int:
    host, svc, provider, sink, listener, clock, consent = build()
    scope = "scope_badminton_match"
    for ref in ("stu_alex", "stu_maya", "stu_jordan"):
        consent.grant(ref, scope, "introduction")
    print("=== Scenario: newly matched group, consent first (synthetic) ===\n")
    out = host.groups.form_group("grp_1", scope, "badminton this weekend", "game", list(ROSTER),
                                 {"stu_alex": ["badminton", "hackathons"], "stu_maya": ["Badminton"], "stu_jordan": ["badminton", "chess"]},
                                 session_id=SESSION)
    print(f"  invited (private invitations only): {out['invited']}; Taylor never named or contacted")
    for i, who in enumerate(out["invited"]):
        res = host.groups.handle_private_message({"request_id": f"j{i}", "member_ref": who, "text": "join", "identity_source": "mock"})
    for line in provider.group_outbox[-2:]:
        for t in line["text"].splitlines():
            print(f"  Crewbie Host: {t}")
    chat = Chat(host, provider, clock)
    chat.say("stu_maya", "icebreaker please")
    print(f"  >> private invites sent: {len(provider.private_outbox)}; Taylor invited: {'stu_taylor' in [o['target'] for o in provider.private_outbox]}")
    blocked = host.groups.form_group("grp_2", "scope_unrelated_hike", "a hike", "trip", list(ROSTER), {})
    print(f"  >> same people, unrelated activity without consent: {blocked['action']} {blocked['error_code']}")
    ok = out["invited"] == ["stu_alex", "stu_maya", "stu_jordan"] and blocked["action"] == "blocked"
    return 0 if ok else 1
