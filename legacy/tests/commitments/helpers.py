import copy

from apps.chat_bot.demo import ROSTER, SESSION, build, load_snapshot

V1 = lambda: copy.deepcopy(load_snapshot("plan_flagstaff_001", 1))
V2 = lambda: copy.deepcopy(load_snapshot("plan_flagstaff_002", 2))


def msg(rid, who, text, **kw):
    return {"request_id": rid, "member_ref": who, "text": text, "identity_source": "mock", **kw}


def fresh(present=V2):
    host, svc, provider, sink, listener, clock, consent = build()
    if present:
        host.present_proposal(present())
    return host, svc, provider, sink, listener, clock, consent


def accept_all(host, version=2, skip=()):
    for i, who in enumerate(ROSTER):
        if who not in skip:
            host.handle_chat_message(msg(f"a{version}{i}", who, f"I accept version {version}"))
