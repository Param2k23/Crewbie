# Cubbie Skill changes

The Skill stays installable from `https://github.com/<owner>/Crewbie/tree/master/skills/crewbie-unlocks`.
Track 1 votes depend on it, so every change must keep solo planning working (C-1).

## 1. `crew.py` CLI contract

Location: `skills/crewbie-unlocks/scripts/crew.py`. Python 3 standard library only (`urllib.request`, `json`,
`secrets`, `hashlib`, `argparse`, `pathlib`). Single file.

Configuration:

- API base URL: constant `DEFAULT_API_URL` in the script, overridable by env `CREWBIE_API_URL`.
- State file: `~/.config/crewbie/install.json` (mode 0600): `{ "token": "...", "install_id": "...", "cursor": 0 }`.
- Timeout: 15 s per request; one retry on connection error.

Subcommands and output (default line format; `--json` prints the raw API JSON):

| Command | Calls | Output lines |
|---|---|---|
| `register` | `POST /v1/installs` | `INSTALL <id>` / `LINKED yes|no` |
| `link` | `POST /v1/installs/me/link-codes` | `LINK_CODE <code>` / `INVITE <url>` / `COMMAND /crew link code:<code>` / `EXPIRES <local time>` |
| `whoami` | `GET /v1/installs/me` | `INSTALL <id>` / `LINKED yes|no` / `DISCORD <username>` |
| `rooms --event <json>` (repeatable, max 5) | `POST /v1/rooms/lookup` | per event: `EVENT <ref> ROOMS <n>` then `ROOM size=<n> window=<4:00-6:00pm> vibe=<v> budget=<b> interests=<a,b>` |
| `submit --file <intent.json>` | `POST /v1/intents` | `INTENT <id>` then either `OFFER <id> TYPE join EXPIRES <time>` + `CREW size=<n> window=<...> vibe=<v> budget=<b>` (+ `CHANGED window` if the room window moved) or `OFFER <id> TYPE new_room EXPIRES <time>` or `MATCHING` |
| `accept --offer <id>` | `POST /v1/offers/{id}/accept` | `JOINED room=<id> size=<n>` / `THREAD <url>` or `THREAD pending`; on `LINK_REQUIRED`: exit 2 with the `link` output lines |
| `decline --offer <id>` | `POST /v1/offers/{id}/decline` | `DECLINED` |
| `leave --intent <id>` | `POST /v1/intents/{id}/withdraw` | `LEFT` |
| `updates` | `GET /v1/updates?cursor=` | one line per update: `UPDATE <kind> event="<title>" ...` ; `NO_UPDATES` if empty; saves cursor |

Exit codes: 0 ok, 2 student action needed (link, expired, stale), 3 API unreachable, 4 invalid input, 5 server
error. Errors print `ERROR <code> <message>` on stderr.

The script never prints the token. `register` is called automatically by any other subcommand if no state file
exists.

## 2. SKILL.md: replace "Find a crew: optional service handoff"

Keep the rest of SKILL.md. Replace that section with the text below (adjust wording, keep the rules). Also add a
short line to "Send a compact Unlock Card" telling Cubbie it may add "N students going" from `crew.py rooms`.

```markdown
## Find a crew

Crewbie can match the student with other students going to the same activity, in a private Discord thread.
It is optional; solo plans never depend on it.

When to offer: after the student confirms an activity (not just a recommendation), ask once:
"Want me to find other students going to this?"

Before the first submit for an activity, tell the student exactly what goes to the Crewbie server and ask for a yes:
- Shared with the crew as a group summary: the event and its link, your time window, how long you want to stay,
  budget level (low, mid or high), vibe (chill, social or active), up to 3 interests.
- Kept private by your Crewbie agent and never shown to anyone: the earliest you could start and latest you
  could stay, and your budget cap if you give one. Your agent uses these to say yes or no to small time changes.
Do not send dietary needs, calendar details, course names, or anything else.

Steps:
1. Write intent.json with only those fields (format in scripts/crew.py --help). Use America/Phoenix unless the
   student says otherwise.
2. Run `python3 scripts/crew.py submit --file intent.json`.
3. If it prints `OFFER ... TYPE join`, text the student the CREW line in plain words, mention if the time changed,
   and ask "Join?". If `TYPE new_room`, say no crew exists yet and ask whether to start one. If `MATCHING`, say
   you will check back.
4. Only after the student says yes, run `python3 scripts/crew.py accept --offer <id>`. If they say no, run
   `decline`.
5. If accept exits with code 2 and prints LINK_CODE, send the student the invite and the exact command, then end
   your turn. When they say they did it, run accept again.
6. If THREAD shows a URL, send it. If THREAD is pending, say the chat link will come shortly.
7. Offer a scheduled check-in for this activity (with the student's yes): every 30 minutes until the activity
   starts, run `python3 scripts/crew.py updates` and text only lines that start with UPDATE, in plain words.
   Text nothing on NO_UPDATES. Stop the check-in after the activity starts or when the student asks.

Leaving: if the student wants out, run `python3 scripts/crew.py leave --intent <id>` and confirm.

If any crew.py command exits with code 3, say crew matching is unavailable right now and continue with the solo
plan. Never claim a match, join, or message happened unless crew.py printed it.
Cubbie never messages other students; the Crewbie Discord bot handles the group chat.
```

## 3. Intent file format (for `--help` and tests)

Same JSON body as `POST /v1/intents` in 03-API-CONTRACT.md.

## 4. Tests

`tests/skill/` runs `crew.py` as a subprocess against the FastAPI test server (via `CREWBIE_API_URL`) with a
temporary HOME, covering every subcommand, exit codes, cursor persistence, and that the token never appears in
stdout or stderr.
