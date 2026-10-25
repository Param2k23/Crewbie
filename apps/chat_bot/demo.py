"""Standalone mock group chat: four students plus Crewbie Host. No network.

    python -m apps.chat_bot.demo                      # scripted full scenario
    python -m apps.chat_bot.demo --transcript docs/implementation/fixtures/chat_transcript.json
    python -m apps.chat_bot.demo --scenario weekend   # vague idea -> plan -> 4 confirmations -> change -> reset
    python -m apps.chat_bot.demo --scenario dinner    # evening meetup with mixed responses
    python -m apps.chat_bot.demo --scenario newgroup  # consent-gated group formation
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.commitments import CommitmentService, MemoryConsentGateway, MemoryEventSink, MemoryListener

from .host import CrewbieHost
from .mock_negotiation import MockNegotiationService
from .providers import PROVIDER_STATUS, MockMessagingProvider

DATA = Path(__file__).parent / "data" / "public_snapshots.json"
ROSTER = {"stu_alex": "Alex", "stu_maya": "Maya", "stu_jordan": "Jordan", "stu_taylor": "Taylor"}
SESSION = "session_trip_001"
T0 = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> datetime:
        self.now += timedelta(**kw)
        return self.now


def load_snapshot(plan_id: str, version: int) -> dict:
    return json.loads(DATA.read_text())["snapshots"][f"{plan_id}:{version}"]


def build(state_path=None):
    clock = Clock()
    consent = MemoryConsentGateway()
    for ref in ROSTER:
        consent.grant(ref, SESSION)
    sink, listener, provider = MemoryEventSink(), MemoryListener(), MockMessagingProvider()
    svc = CommitmentService(sink, listener, consent, clock=clock, state_path=state_path)
    host = CrewbieHost(svc, provider, "mock_channel_trip", ROSTER, clock=clock, session_id=SESSION,
                       negotiation=MockNegotiationService(SESSION, list(ROSTER)))
    return host, svc, provider, sink, listener, clock, consent


class Chat:
    """Prints a readable transcript while driving the host."""

    def __init__(self, host, provider, clock):
        self.host, self.provider, self.clock, self.n = host, provider, clock, 0

    def _flush(self, since: int) -> None:
        for out in self.provider.group_outbox[since:]:
            for line in out["text"].splitlines():
                print(f"  Crewbie Host: {line}")

    def say(self, who: str, text: str, **extra) -> dict:
        self.n += 1
        self.clock.advance(minutes=1)
        print(f"[{self.clock.now:%H:%M}] {ROSTER.get(who, who)}: {text}")
        before = len(self.provider.group_outbox)
        res = self.host.handle_chat_message({
            "request_id": extra.pop("request_id", f"m{self.n}"), "member_ref": who, "text": text,
            "sent_at": extra.pop("sent_at", self.clock.now.isoformat()), "identity_source": "mock", **extra})
        self._flush(before)
        return res

    def host_does(self, label: str, fn, *a, **kw):
        before = len(self.provider.group_outbox)
        print(f"[{self.clock.now:%H:%M}] -- {label}")
        res = fn(*a, **kw)
        self._flush(before)
        return res


def show(svc, plan_id, version, sink):
    s = svc.get_commitment_summary(SESSION, plan_id, version)
    print(f"  >> state={s['proposal_state']} accepted={s['accepted_count']}/{s['required_count']} members={s['members']}")


def scripted() -> int:
    host, svc, provider, sink, listener, clock, consent = build()
    chat = Chat(host, provider, clock)
    print("=== Crewbie mock group chat (synthetic, no network) ===\n")
    chat.host_does("Introductions need consent: Casey has not opted in", host.introduce, SESSION,
                   ["stu_alex", "stu_casey"], SESSION, "the Flagstaff trip", {})
    print(f"  >> blocked: {host.introduce(SESSION, ['stu_alex', 'stu_casey'], SESSION, 'x', {})['error_code']}")
    chat.host_does("Existing friends, optional icebreaker", host.suggest_icebreaker, SESSION,
                   list(ROSTER), SESSION, "trip", existing_group=True)
    v1 = load_snapshot("plan_flagstaff_001", 1)
    chat.host_does("A4 posts validated proposal v1", host.present_proposal, v1)
    chat.say("stu_alex", "I accept version 1")
    chat.say("stu_maya", "sounds fun")
    chat.say("stu_taylor", "Yes, if we leave after 10")
    dup = chat.say("stu_alex", "I accept version 1", request_id="m1")
    print(f"  >> duplicate delivery ignored (action={dup['action']})")
    show(svc, "plan_flagstaff_001", 1, sink)
    clock.advance(hours=7)
    chat.host_does("Silent member after 7h: one gentle nudge", host.follow_up)
    chat.say("stu_jordan", "no, too early for me")
    show(svc, "plan_flagstaff_001", 1, sink)
    v2 = load_snapshot("plan_flagstaff_002", 2)
    chat.host_does("A4 revises -> v2 (all v1 approvals invalidated)", host.present_proposal, v2)
    print(f"  >> v1 summary: {svc.get_commitment_summary(SESSION, 'plan_flagstaff_001', 1)['error_code']}")
    chat.say("stu_alex", "I accept version 1")
    chat.say("stu_alex", "I accept version 2")
    chat.say("stu_maya", "I confirm plan version 2")
    chat.say("stu_jordan", "maybe")
    chat.say("stu_taylor", "I confirm plan version 2")
    show(svc, "plan_flagstaff_002", 2, sink)
    chat.say("stu_jordan", "I accept version 2")
    show(svc, "plan_flagstaff_002", 2, sink)
    print(f"\nEvents emitted: {[e['type'] for e in sink.events]}")
    print(f"proposal_confirmed count: {len(sink.of_type('proposal_confirmed'))}")
    print(f"Provider status: mock=implemented; discord={PROVIDER_STATUS['discord']['note']}")
    ok = svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)["confirmed"]
    return 0 if ok and len(sink.of_type("proposal_confirmed")) == 1 else 1


def replay(path: str) -> int:
    data = json.loads(Path(path).read_text())
    host, svc, provider, sink, listener, clock, consent = build()
    chat = Chat(host, provider, clock)
    print(f"=== Replaying {path} ({data['fixture_notice']}) ===\n")
    chat.host_does("proposal posted", host.present_proposal, load_snapshot(data["plan_id"], data["version"]))
    bad = 0
    for msg in data["messages"]:
        res = chat.say(msg["member_ref"], msg["text"], request_id=msg["request_id"])
        got, want = res.get("state"), msg.get("expected_state")
        flag = "OK " if got == want else "MISMATCH"
        bad += got != want
        print(f"  >> {flag} state={got} expected={want}")
    show(svc, data["plan_id"], data["version"], sink)
    print(f"Events: {[e['type'] for e in sink.events]}")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcript", help="replay a chat_transcript.json fixture")
    ap.add_argument("--scenario", choices=["flagstaff", "weekend", "dinner", "newgroup"], default="flagstaff",
                    help="scripted scenario to run (default: flagstaff)")
    args = ap.parse_args(argv)
    if args.transcript:
        return replay(args.transcript)
    if args.scenario == "flagstaff":
        return scripted()
    from . import scenarios
    return getattr(scenarios, args.scenario)()


if __name__ == "__main__":
    sys.exit(main())
