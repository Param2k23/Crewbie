# Inputs needed from the owner

Claude Code: ask for these at the start of the phase that needs them, all at once for that phase. Never ask for a
secret's value in chat; ask the owner to put it in `.env` (local) or the host's secret settings, then verify with
`python -m crewbie.config check`.

| ID | Needed by | Item | Type |
|---|---|---|---|
| I-01 | Phase 0 | Branch strategy confirmation (`crewbie-v2` from `master`, legacy moved) and team members who will push | Decision |
| I-02 | Phase 4 | Discord application, bot token, application ID, guild ID, channel IDs, permanent invite link | Secrets + IDs |
| I-03 | Phase 4 | Two or more Discord test accounts (teammates) | People |
| I-04 | Phase 5 | Hosting choice and account | Decision + account |
| I-05 | Phase 5 | Public HTTPS URL | Config |
| I-06 | Phase 6 | Cubbie accounts for at least two students with the Skill installed | People |
| I-07 | Phase 7 | Anthropic API key with a spend limit | Secret |
| I-08 | Phase 7 | Mission Control scope: adapter only, or also new negotiation view | Decision |
| I-09 | Phase 8 | Demo participants, event to use, approval of demo script | Decision |
| I-10 | Phase 8 | Who submits Tracks 2/3 and the closing time | Decision |
| I-11 | Phase 1 | Envelope encryption key for prod | Secret |
| I-12 | Phase 2 | Admin token | Secret |

## How to obtain each

### I-02 Discord

1. Create (or reuse) a Discord server for Crewbie. Create channels `#welcome`, `#crew-board`, `#crews`.
   - `#crew-board`: in channel settings → Permissions → `@everyone`: deny Send Messages.
   - `#crews`: `@everyone`: deny Send Messages, allow Send Messages in Threads.
2. Go to https://discord.com/developers/applications → New Application → name it "Crewbie".
3. General Information: copy **Application ID** → `CREWBIE_DISCORD_APP_ID`.
4. Bot tab: Reset Token → copy once → `CREWBIE_DISCORD_TOKEN`. Leave all three Privileged Gateway Intents off.
5. OAuth2 → URL Generator: scopes `bot` and `applications.commands`. Bot permissions: View Channels, Send
   Messages, Send Messages in Threads, Create Private Threads, Manage Threads, Embed Links, Read Message History,
   Manage Messages (for board cards). Open the generated URL and add the bot to your server.
6. In Discord: User Settings → Advanced → enable Developer Mode. Right-click the server icon → Copy Server ID →
   `CREWBIE_DISCORD_GUILD_ID`. Right-click `#crew-board` → Copy Channel ID → `CREWBIE_DISCORD_BOARD_CHANNEL_ID`.
   Same for `#crews` → `CREWBIE_DISCORD_CREWS_CHANNEL_ID`.
7. Server Settings → Invites, or right-click `#welcome` → Invite People → Edit invite link → Expire: Never,
   Max uses: No limit → copy → `CREWBIE_DISCORD_INVITE_URL`.
8. Make sure the bot's role is above any role it needs to manage, and that it can see `#crews`.

Note: Discord permission names and limits change occasionally. If thread creation fails with a permissions
error, compare against Discord's current docs for private threads.

### I-04 / I-05 Hosting

Need: public HTTPS on port 443, a persistent disk for SQLite, an always-on process (the bot holds a gateway
connection). Options:

| Option | Steps | Notes |
|---|---|---|
| Railway | New project → Deploy from GitHub repo → add a Volume mounted at `/data` → set variables → Settings → Networking → Generate Domain | Simple; paid usage after trial credit |
| Render | New → Web Service from repo → Docker → add Disk at `/data` (paid instance type) → env vars | Free tier sleeps; use a paid instance for the demo |
| Fly.io | `fly launch` → `fly volumes create data --size 1` → mount in `fly.toml` → `fly secrets set ...` → `fly deploy` | CLI driven; good control |
| Cloudflare Tunnel from a laptop | `cloudflared tunnel --url http://localhost:8000` | Fastest for testing; the URL changes each run unless you set up a named tunnel; laptop must stay on |

Whatever you choose, the resulting URL becomes `CREWBIE_PUBLIC_URL` and `DEFAULT_API_URL` in `crew.py`.

### I-07 Anthropic API key

https://console.anthropic.com → Settings → API Keys → Create Key → set a monthly spend limit under Billing/Limits
→ `ANTHROPIC_API_KEY`. Optional: the system runs with `CREWBIE_LLM_MODE=off`.

### I-11 / I-12 Generated secrets

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # CREWBIE_ENVELOPE_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"                                  # CREWBIE_ADMIN_TOKEN
```

Run locally and paste into `.env` or the host dashboard, not into chat.

### I-06 Cubbie

Each tester texts Cubbie: `Install https://github.com/<owner>/Crewbie/tree/crewbie-v2/skills/crewbie-unlocks`
(branch link during testing; `master` after merge), and confirms the install.

## Environment variables

See `docs/spec/env.example`.
