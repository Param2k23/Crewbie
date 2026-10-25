"""Conservative rule-based classification of free-text chat replies.

There is deliberately no model call here. Anything that is not an unambiguous
approval can only produce a non-final state or a request for clarification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_VERSION_RE = re.compile(r"\b(?:version|ver|v)\s*#?\s*(\d+)\b")
_PLAN_RE = re.compile(r"\bplan_[a-z0-9_]+\b")

_WITHDRAW = re.compile(
    r"\b(i'?m|i am|im)\s+(out|dropping out|going to drop out)\b"
    r"|\b(drop(?:ping)? out|withdraw(?:ing)?|pull(?:ing)? out|count me out|remove me)\b"
    r"|\bcan'?t make it (any ?more)\b|\bnot (coming|going) any ?more\b|\bhave to bail\b"
)
_UNCERTAIN = re.compile(
    r"\bnot (really )?(sure|certain|decided)\b|\bunsure\b|\bno idea\b|\bdon'?t know\b"
    r"|\bdo not know\b|\bundecided\b|\bhaven'?t decided\b|\b(let me|need to|gotta) think\b"
    r"|\bthink about it\b|\bwe'?ll see\b|\bwill see\b"
)
_LEADING_NO = re.compile(r"^(no|nope|nah|no thanks|no thank you)\b")
_CONDITION = re.compile(
    r"\b(if|unless|as long as|so long as|provided|assuming|on condition|depending on"
    r"|subject to|contingent|except|only when|only after|only before|but only)\b"
)
_BUT = re.compile(r"\bbut\b")
_NEG_ACCEPT = re.compile(
    r"\b(can'?t|cannot|can not|won'?t|will not|don'?t|do not|didn'?t|not ready to)\s+"
    r"(accept|confirm|approve|agree|commit)\b"
)
_DECLINE = re.compile(
    r"\b(decline|reject|disagree|object)\b|\bnot for me\b|\bi'?ll pass\b|\bi pass\b|\bhard pass\b"
    r"|\bcan'?t do (it|this|that)\b|\b(won'?t|doesn'?t) work( for me)?\b"
)
_TENTATIVE = re.compile(
    r"\b(maybe|perhaps|possibly|probably|might|could be|i guess|idk|kinda|sort of|leaning)\b"
)
_ACCEPT = re.compile(
    r"\b(accept|accepted|confirm|confirmed|approve|approved|agree to|commit to|sign off on|lock it in)\b"
)
# Plain affirmatives that only count when the platform says the message is a
# reply to the exact proposal message.
_PLAIN_YES = re.compile(r"^(yes|yep|yeah|yup|i'?m in|count me in|let'?s do it|let'?s go)\W*$")
_INTERESTED = re.compile(
    r"\b(sounds? (fun|good|great|interesting|cool|nice|awesome|exciting)"
    r"|looks (good|great|fun|interesting)|interested|love (it|this|that)|excited|i like"
    r"|nice|cool|down|fine by me|yes|yep|yeah|yup|sure|ok|okay)\b"
)


@dataclass(frozen=True)
class ParsedReply:
    state: Optional[str]  # None => cannot classify; ask for clarification
    rule: str
    explicit: bool = False  # True only for unambiguous approval
    needs_clarification: bool = False
    referenced_version: Optional[int] = None
    referenced_plan_id: Optional[str] = None


def _normalise(text: str) -> str:
    t = (text or "").lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", t).strip()


def classify_reply(text: str, *, reply_scoped: bool = False) -> ParsedReply:
    """Classify one chat message.

    ``reply_scoped`` means the provider reports the message as a direct reply
    to the host's proposal message, which anchors a plain "yes" to a version.
    """
    t = _normalise(text)
    vm = _VERSION_RE.search(t)
    pm = _PLAN_RE.search(t)
    ref_v = int(vm.group(1)) if vm else None
    ref_p = pm.group(0) if pm else None

    def out(state, rule, **kw):
        return ParsedReply(state, rule, referenced_version=ref_v, referenced_plan_id=ref_p, **kw)

    if not t:
        return out(None, "empty")
    if _WITHDRAW.search(t):
        return out("withdrawn", "withdraw")
    if _UNCERTAIN.search(t):
        return out("tentative", "uncertain")
    if _LEADING_NO.search(t):
        return out("declined", "leading_no")
    if "?" in t:
        return out(None, "question", needs_clarification=True)
    if _CONDITION.search(t):
        return out("conditional", "condition")
    na = _NEG_ACCEPT.search(t)
    if na:
        return out("tentative", "not_yet") if re.search(r"\byet\b", t) else out("declined", "negated_accept")
    if _DECLINE.search(t):
        return out("declined", "decline")
    if _TENTATIVE.search(t):
        return out("tentative", "tentative_word")
    if _ACCEPT.search(t):
        if _BUT.search(t):
            return out("conditional", "accept_with_but")
        return out("accepted", "explicit_accept", explicit=True)
    if reply_scoped and _PLAIN_YES.match(t):
        return out("accepted", "reply_scoped_yes", explicit=True)
    if _INTERESTED.search(t):
        return out("interested", "weak_positive", needs_clarification=True)
    return out(None, "unclear", needs_clarification=True)
