# Cubbie × Crewbie: demo brief

Written for: the owner, to paste into a Claude chat when planning the final demo video and script.
Everything below was checked against the running system or the code on 2026-10-25.

## The pitch in three sentences
Crewbie is a Skill built entirely on Cubbie, the iMessage assistant. A student texts Cubbie, and Cubbie finds
student-only perks first, plans around their week, and, only if the student says yes, finds other students going
to the same thing and opens a private Discord thread for them. There is no app and no signup: Cubbie is the
single front door, and it asks before anything is shared.

## What is live right now
- Website: https://crewbie-cubbie.vercel.app (also cubbie-crewbie.vercel.app)
- Install text for Cubbie: `Install https://github.com/Param2k23/Crewbie/tree/master/skills/crewbie-unlocks`
- Code (public): https://github.com/Param2k23/Crewbie
- Backend: one small AWS server (API + Discord bot), https://18-220-104-252.sslip.io/healthz
- Discord server: invite https://discord.gg/uu7sNePkpF with `#welcome`, `#crew-board` (one card per crew,
  with a Join button) and `#crews` (private threads)
- The server can be turned off to save money (`scripts/ops/down.sh`) and on again in about 3 minutes
  (`scripts/ops/up.sh`). It must be ON when you record.

## The story, as the student sees it
1. Install: one text, Cubbie asks before fetching, then asks the tone: Chill, Playful or Roast Me.
2. Ask: "I'm at ASU Tempe and free tonight 6 to 10, under $15." Cubbie searches student-only offers first and
   shows an Unlock Card with the source link.
3. Confirm a plan, then Cubbie asks: "Want me to find other students going to this?"
4. Cubbie lists exactly what is shared and what stays private, and waits for a yes.
5. First student: no crew yet, so Cubbie offers to start one. The student links Discord once with
   `/crew link code:XXXXXX`. A card appears on `#crew-board`.
6. Second student, different phrasing and a different web page: Cubbie finds the same event, asks "Is this the
   same one? 1 going", then "Join?". After the yes, a private Discord thread opens with an icebreaker, both get a
   DM, and the first student's Cubbie texts "two people are going".

## Talking points that are true
- Cubbie is the base: install, memory (tone, preferences, with permission), calendar and Canvas (with permission),
  browsing and source checking, scheduled check-ins, and consent all come from Cubbie.
- Student-exclusive offers are ranked before public ones. Real result from a live test: a movie at $10.81 with a
  student ID versus $14.59 public, with the theater's page as the source.
- Roast Me is optional and bounded. Real line from a live test: "You installed a whole skill just to outsource
  the banter. Efficient."
- Privacy: a student's earliest/latest times and budget cap are stored encrypted and never shown to anyone, not
  other students, not Discord. Only room-level facts (time window, vibe, budget level) are shared.
- A student's private agent can accept a small time change inside the limits they gave; the thread then says
  "Plan moved to 10:00 to 11:30 am."
- If the service is down, Cubbie still gives a normal solo plan. Matching is optional.
- Three layers map to the three hackathon tracks: the Skill, the agents, the group chat.

## Do not say (it is not true yet)
- "LLM agents" or "AI negotiating": the agents are rule-based on purpose. An LLM layer is planned on a separate
  branch. Say "private agents that follow your limits".
- "Guaranteed match" or "always finds someone": a crew needs another student going to the same event.
- "Official Cubbie partner": we built on Cubbie for its hackathon; the site only thanks the sponsor.
- Mission Control: dropped from the story. It still exists at `/demo` but is not part of the pitch.
- Not yet tried live: joining from the Discord card with a fresh account, and Cubbie's behaviour with the service
  switched off (both are covered by automated tests only).

## Logistics and risks for recording
- Turn the server on first and check `scripts/ops/status.sh` shows `discord: connected`.
- Offers expire after 15 minutes, link codes after 10. Cubbie's scheduled check-ins run at most every 15 minutes,
  so a live "someone joined" text takes up to 15 minutes. Plan a cut, ask Cubbie "any updates?", or record it
  in a second take.
- Use one real event with a date and start time. The two students can word it differently. Pre-test the exact
  phrasing, because Cubbie's replies vary slightly between runs.
- Linking Discord is a one-time step per student. If a Discord account was linked before, the bot asks to
  replace the link and the student must press the button.
- Clean `#crew-board` and `#crews` of old test cards and threads first.
- Each Cubbie must have the latest Skill: text the install message again to update.
- The demo cast: two Cubbie students and two Discord accounts (the icebreaker thread needs two people). A third
  Discord account lets you show privacy: it cannot see the thread.

## A 3-minute shape to react to (adjust freely)
- 0:00 to 0:20 Hook and title card "Cubbie × Crewbie". The problem: good plans die because nobody else is
  going.
- 0:20 to 0:50 Install and tone in one text (show Roast Me for personality).
- 0:50 to 1:25 The student-first search and the Unlock Card with the student price.
- 1:25 to 2:15 Start the crew, link Discord, the card on `#crew-board`; second student finds it in different
  words and joins.
- 2:15 to 2:45 The private thread, the icebreaker, the DM, and A's Cubbie text. Optional: the "Plan moved" notice
  to show agents agreeing on a time.
- 2:45 to 3:00 The website, the install text, and thanks to the Cubbie team.

## Questions to settle in the chat
Who is the audience (judges, Cubbie team, students)? Voiceover, on-screen text or both? Who plays each student?
Do we show the 15-minute check-in live or cut to it? One strong closing line? Should the video mention that LLM
agents are next?
