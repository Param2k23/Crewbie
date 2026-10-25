# AWS deployment (EC2, on/off)

Target: one EC2 `t4g.micro` instance (ARM, 1 GB RAM) running Docker Compose with two containers: `crewbie`
(API + Discord bot) and `caddy` (HTTPS reverse proxy with automatic Let's Encrypt certificates). An Elastic IP
keeps the address fixed across stop/start, and an `sslip.io` hostname gives it a name without buying a domain.

The instance runs only when needed. Stopping it keeps the disk (and the SQLite database) and stops compute
billing.

Part A is done by the owner in the AWS console (first-time AWS user). Part B is done by Claude Code in the repo.
Parts C to F are done together.

## Cost summary (check current prices before relying on them)

| Item | Running | Stopped |
|---|---|---|
| t4g.micro compute | about $0.20/day | $0 |
| Public IPv4 (Elastic IP), charged on and off | about $0.12/day | about $0.12/day |
| 10 GB gp3 disk | about $0.03/day | about $0.03/day |
| Total | about $0.35/day | about $0.15/day |

Billing stops completely only after teardown (Part F).

---

## Part A: Owner steps in the AWS console

Do these in order. Time: about 45 minutes the first time. Anything in `<angle brackets>` is a value you choose
or copy.

### A1. Secure the account

1. Sign in at https://console.aws.amazon.com as the root user (the email you signed up with).
2. Top right: click your account name → **Security credentials**.
3. Under **Multi-factor authentication (MFA)** → **Assign MFA device** → choose **Authenticator app** → scan the
   QR code with Google Authenticator, Authy, 1Password or similar → enter two consecutive codes.
   The root user can do anything, including closing the account. MFA is the single most important step.

### A2. Create an admin user for daily console work

Using the root user every day is risky. Create a separate admin login.

1. Search bar at the top: type **IAM** → open it.
2. Left menu: **Users** → **Create user**.
3. User name: `dhaval-admin`. Check **Provide user access to the AWS Management Console** → **I want to create an
   IAM user** → custom password → uncheck "must create a new password" if you prefer → **Next**.
4. **Attach policies directly** → search and check `AdministratorAccess` → **Next** → **Create user**.
5. On the success page, copy the **Console sign-in URL** (looks like `https://<12-digit-id>.signin.aws.amazon.com/console`)
   and bookmark it.
6. Open the user → **Security credentials** tab → **Assign MFA device** → same steps as A1.
7. Sign out. From now on, sign in with the bookmarked URL as `dhaval-admin`.

### A3. Redeem credits and set a budget alarm

1. Search bar: **Billing and Cost Management** → left menu **Credits** → **Redeem credit** → enter each
   promotional code. Each credit shows its expiry date and which services it applies to. EC2 should be listed.
2. If your second $100 is a prepaid Visa/Mastercard gift card rather than an AWS code, it goes under
   **Payment preferences** as a card. AWS may reject prepaid cards; your $100 credit is enough on its own.
3. Left menu: **Budgets** → **Create budget** → **Use a template** → **Monthly cost budget**.
   Name: `crewbie-monthly`. Amount: `10`. Email: your address. **Create budget**.
   You will get an email at 85% and 100% of $10. Your credits absorb the charges, but the alarm tells you if
   something unexpected is running.

### A4. Pick the region

Top right, next to your user name: click the region and choose **US West (Oregon) us-west-2**. Everything below
must be created in this region. Resources in other regions are invisible unless you switch, which is the most
common "where did my server go" confusion for new AWS users.

### A5. Create an SSH key pair

1. Search bar: **EC2** → left menu **Network & Security → Key Pairs** → **Create key pair**.
2. Name: `crewbie-key`. Type: **ED25519**. Format: **.pem** → **Create key pair**. The file downloads once; AWS
   does not keep a copy.
3. Move it to a safe folder and restrict permissions:
   - macOS/Linux: `mkdir -p ~/.ssh && mv ~/Downloads/crewbie-key.pem ~/.ssh/ && chmod 400 ~/.ssh/crewbie-key.pem`
   - Windows PowerShell:
     ```powershell
     New-Item -ItemType Directory -Force $HOME\.ssh | Out-Null
     Move-Item $HOME\Downloads\crewbie-key.pem $HOME\.ssh\
     icacls $HOME\.ssh\crewbie-key.pem /inheritance:r /grant:r "$($env:USERNAME):(R)"
     ```

### A6. Find your public IP (for SSH access)

Visit https://checkip.amazonaws.com and note the address. Only this address will be allowed to SSH in. If your
network changes (campus vs home), you will update the rule (Part D, "SSH stopped working").

### A7. Launch the instance

EC2 → **Instances** → **Launch instances**.

| Field | Value |
|---|---|
| Name | `crewbie` |
| Application and OS Images | **Ubuntu** → **Ubuntu Server 24.04 LTS** → Architecture **64-bit (Arm)** |
| Instance type | `t4g.micro` |
| Key pair | `crewbie-key` |
| Network settings → Edit | Keep default VPC and subnet; **Auto-assign public IP: Enable** |
| Firewall (security groups) | **Create security group**, name `crewbie-sg` |
| Inbound rule 1 | Type **SSH**, Source type **My IP** (fills the address from A6) |
| Inbound rule 2 | **Add security group rule** → Type **HTTP**, Source **Anywhere (0.0.0.0/0)** |
| Inbound rule 3 | **Add security group rule** → Type **HTTPS**, Source **Anywhere (0.0.0.0/0)** |
| Configure storage | `10` GiB, **gp3** |
| Advanced details → Credit specification | **Standard** (avoids surprise charges from unlimited CPU bursting) |

Click **Launch instance** → **View all instances**. Wait until **Instance state** is *Running* and **Status check**
shows *2/2 checks passed* (2 to 3 minutes). Copy the **Instance ID** (`i-0abc...`).

Port 80 must be open to everyone because Let's Encrypt uses it to verify the certificate. Port 443 serves the
API to Cubbie and to Discord users.

### A8. Attach an Elastic IP

1. EC2 left menu: **Network & Security → Elastic IPs** → **Allocate Elastic IP address** → **Allocate**.
2. Select the new address → **Actions → Associate Elastic IP address** → Instance: `crewbie` → **Associate**.
3. Copy the IP, for example `35.88.12.45`. Your hostname is the IP with dashes plus `.sslip.io`:
   `35-88-12-45.sslip.io`. This is `CREWBIE_HOSTNAME`, and `https://35-88-12-45.sslip.io` is
   `CREWBIE_PUBLIC_URL`.

### A9. Create a limited user for the on/off scripts

The scripts on your laptop need AWS credentials. Give them only start, stop, describe and snapshot permissions,
so a leaked key cannot do much.

1. IAM → **Policies** → **Create policy** → **JSON** tab → paste, replacing `<ACCOUNT_ID>` (12 digits, shown top
   right under your user name) and `<INSTANCE_ID>`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StartStopCrewbie",
      "Effect": "Allow",
      "Action": ["ec2:StartInstances", "ec2:StopInstances", "ec2:RebootInstances"],
      "Resource": "arn:aws:ec2:us-west-2:<ACCOUNT_ID>:instance/<INSTANCE_ID>"
    },
    {
      "Sid": "ReadAndSnapshot",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "ec2:DescribeSecurityGroups",
        "ec2:CreateSnapshot",
        "ec2:CreateTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "UpdateSshRuleOnly",
      "Effect": "Allow",
      "Action": ["ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress"],
      "Resource": "arn:aws:ec2:us-west-2:<ACCOUNT_ID>:security-group/<SECURITY_GROUP_ID>"
    }
  ]
}
```

   `<SECURITY_GROUP_ID>` is on the instance's **Security** tab (`sg-0abc...`). → **Next** → name
   `crewbie-ops-policy` → **Create policy**.
2. IAM → **Users** → **Create user** → name `crewbie-ops` → do **not** give console access → **Next** →
   **Attach policies directly** → check `crewbie-ops-policy` → **Create user**.
3. Open `crewbie-ops` → **Security credentials** → **Create access key** → use case **Command Line Interface
   (CLI)** → confirm → **Create**. Copy the Access key ID and Secret access key now; the secret is shown once.

### A10. Install and configure the AWS CLI on your laptop

1. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html (Windows: MSI
   installer; macOS: pkg installer). Open a new terminal and run `aws --version`.
2. Configure a named profile:

```bash
aws configure --profile crewbie-ops
# AWS Access Key ID:      <from A9>
# AWS Secret Access Key:  <from A9>
# Default region name:    us-west-2
# Default output format:  json
```

3. Test: `aws ec2 describe-instances --instance-ids <INSTANCE_ID> --profile crewbie-ops --query "Reservations[0].Instances[0].State.Name"`
   should print `"running"`.

### A11. Give Claude Code the non-secret values

Put these in `scripts/ops/ops.env` (gitignored; Claude Code creates the file from `ops.env.example`):

```
AWS_PROFILE=crewbie-ops
AWS_REGION=us-west-2
INSTANCE_ID=<i-0abc...>
SECURITY_GROUP_ID=<sg-0abc...>
ELASTIC_IP=<35.88.12.45>
CREWBIE_HOSTNAME=<35-88-12-45.sslip.io>
SSH_KEY_PATH=<~/.ssh/crewbie-key.pem>
SSH_USER=ubuntu
REMOTE_DIR=/opt/crewbie
GIT_BRANCH=crewbie-v2
```

None of these are secrets. The access keys stay in the AWS CLI's own credentials file, never in the repo.

---

## Part B: Files Claude Code creates

### B1. `Dockerfile`

- Base `python:3.12-slim` (multi-arch; builds natively on the ARM instance).
- Install `uv`, copy `pyproject.toml` and `uv.lock`, `uv sync --frozen --no-dev`, then copy `src/`.
- Non-root user `crewbie`; `WORKDIR /app`; `EXPOSE 8000`.
- `CMD ["python", "-m", "crewbie"]`, binding `0.0.0.0:8000`.
- `HEALTHCHECK` calling `/healthz` with Python's `urllib` (no curl in slim images).

### B2. `deploy/docker-compose.yml`

```yaml
services:
  crewbie:
    build:
      context: ..
      dockerfile: Dockerfile
    env_file: ../.env
    environment:
      CREWBIE_DATABASE_URL: sqlite:////data/crewbie.db
    volumes:
      - crewbie_data:/data
    expose:
      - "8000"
    restart: unless-stopped
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }

  caddy:
    image: caddy:<pinned 2.x version, released at least 14 days ago>
    depends_on:
      - crewbie
    ports:
      - "80:80"
      - "443:443"
    environment:
      CREWBIE_HOSTNAME: ${CREWBIE_HOSTNAME}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    restart: unless-stopped

volumes:
  crewbie_data:
  caddy_data:
  caddy_config:
```

`caddy_data` holds the TLS certificate. Keeping it on a named volume means stop/start reuses the certificate
instead of requesting a new one each boot (Let's Encrypt has rate limits).

### B3. `deploy/Caddyfile`

```
{$CREWBIE_HOSTNAME} {
    encode gzip
    reverse_proxy crewbie:8000 {
        flush_interval -1
    }
    header {
        Strict-Transport-Security "max-age=31536000"
        -Server
    }
}
```

`flush_interval -1` keeps the SSE stream (`/v1/stream`) from being buffered.

### B4. `deploy/bootstrap.sh` (run once on the instance)

Idempotent script that:

1. `apt-get update && apt-get upgrade -y`; installs `git`, `sqlite3`, `unattended-upgrades`.
2. Creates a 1 GB swap file at `/swapfile` if absent (1 GB RAM is tight during `docker build`) and adds it to
   `/etc/fstab`.
3. Installs Docker Engine and the Compose plugin from Docker's official apt repository; adds `ubuntu` to the
   `docker` group; `systemctl enable --now docker` (containers with `restart: unless-stopped` then come back
   after every instance start).
4. Creates `/opt/crewbie` owned by `ubuntu`.
5. Sets the timezone to `America/Phoenix` for readable logs (the app still stores UTC).

### B5. `scripts/ops/` (bash `.sh` and PowerShell `.ps1` versions of each)

All read `scripts/ops/ops.env`. All print what they are doing and fail with a clear message if a value is
missing.

| Script | Does |
|---|---|
| `up` | `aws ec2 start-instances`, waits for `instance-running` and status checks, then polls `https://$CREWBIE_HOSTNAME/healthz` until ok (timeout 5 min) |
| `down` | Asks for confirmation, `aws ec2 stop-instances`, waits for `instance-stopped` |
| `status` | Instance state, public IP, `/healthz` result |
| `ssh` | Opens an SSH session: `ssh -i $SSH_KEY_PATH $SSH_USER@$ELASTIC_IP` |
| `deploy` | Over SSH: `git fetch && git checkout $GIT_BRANCH && git pull`, then `docker compose -f deploy/docker-compose.yml up -d --build`, then prints `docker compose ps` and `/healthz` |
| `logs` | Over SSH: `docker compose logs --tail 200 -f crewbie` |
| `push-env` | Copies local `.env.prod` to `$REMOTE_DIR/.env` with `scp`, then `chmod 600` on the server. Refuses if `.env.prod` is tracked by git |
| `backup` | Over SSH: `sqlite3 .backup` of the DB inside the volume to `/tmp`, then `scp` to `backups/crewbie-<timestamp>.db` locally (gitignored) |
| `snapshot` | `aws ec2 create-snapshot` of the root volume with tag `crewbie-<date>` |
| `allow-my-ip` | Replaces the SSH rule in `crewbie-sg` with the current IP from `https://checkip.amazonaws.com` |

Also add `scripts/ops/ops.env.example`, and `.gitignore` entries for `scripts/ops/ops.env`, `.env`, `.env.prod`,
`backups/`.

### B6. Config changes

- `crew.py`: `DEFAULT_API_URL = "https://<CREWBIE_HOSTNAME>"` (filled from `ops.env` during Phase 5).
- `.env.prod` template (`docs/spec/env.prod.example`): `CREWBIE_ENV=prod`,
  `CREWBIE_PUBLIC_URL=https://<CREWBIE_HOSTNAME>`, `CREWBIE_DISCORD_ENABLED=true`, plus the Discord, envelope
  key, admin token and LLM variables. The owner fills secrets locally.

---

## Part C: First deployment (owner and Claude Code together)

1. Claude Code: commit Part B files on `crewbie-v2` and push.
2. Owner: run `scripts/ops/ssh` (or `ssh -i ~/.ssh/crewbie-key.pem ubuntu@<ELASTIC_IP>`). Type `yes` at the
   fingerprint prompt the first time.
3. On the instance:

```bash
sudo mkdir -p /opt/crewbie && sudo chown ubuntu:ubuntu /opt/crewbie
git clone --branch crewbie-v2 https://github.com/Param2k23/Crewbie.git /opt/crewbie
sudo bash /opt/crewbie/deploy/bootstrap.sh
exit
```

   Log out and back in after bootstrap so the `docker` group applies.
4. Owner, on the laptop: fill `.env.prod` (never committed), then `scripts/ops/push-env`.
5. `scripts/ops/deploy`. The first build takes several minutes on a t4g.micro.
6. `scripts/ops/status`. Expect `running` and `/healthz` returning `"status": "ok"` and
   `"discord": "connected"`.
7. From the laptop: `CREWBIE_API_URL=https://<CREWBIE_HOSTNAME> python3 skills/crewbie-unlocks/scripts/crew.py register`
   prints an install ID. Then run acceptance scenarios AS-1 and AS-2.

If the repository is private, use a GitHub deploy key (read-only) on the instance instead of HTTPS cloning.
Claude Code should ask the owner which applies.

---

## Part D: Daily operations

| Task | Command |
|---|---|
| Turn on | `scripts/ops/up` |
| Turn off | `scripts/ops/down` |
| Ship new code | `scripts/ops/deploy` |
| Watch logs | `scripts/ops/logs` |
| Check health | `scripts/ops/status` |
| Back up data | `scripts/ops/backup` |

While the instance is off, `crew.py` exits with code 3 and Cubbie continues with solo plans, and the Discord bot
is offline. Turn it on before any demo or tester session.

Troubleshooting:

| Symptom | Fix |
|---|---|
| SSH times out | Your IP changed. Run `scripts/ops/allow-my-ip`, or in the console edit `crewbie-sg` → SSH rule → My IP |
| HTTPS fails right after first deploy | Caddy is still getting the certificate; check `docker compose logs caddy`. Port 80 must be open to 0.0.0.0/0 |
| Certificate errors mentioning rate limits | Wait an hour; never delete the `caddy_data` volume. Fallback: a free DuckDNS hostname pointing at the Elastic IP |
| `docker build` killed | Out of memory; confirm swap with `free -h`, rerun `bootstrap.sh` |
| `/healthz` shows `discord: disconnected` | Check the bot token in `.env` and the bot logs; confirm the bot is still in the guild |
| Instance gone from the console | Check the region selector says us-west-2 |
| Unexpected charges | Billing → Bills → expand EC2; look for extra instances, volumes or Elastic IPs in any region |

---

## Part E: Security notes

- Root user: MFA on, never used day to day, no access keys.
- `crewbie-ops` keys can only start/stop/describe/snapshot this setup. Delete them in Part F.
- SSH open only to your IP. HTTP/HTTPS open to all (required).
- `.env` on the server is `chmod 600`, owned by `ubuntu`, never in git.
- Ubuntu security updates install automatically via `unattended-upgrades`.

---

## Part F: Teardown (after the hackathon)

Do this when you no longer need the system. Until all steps are done, small charges continue.

1. `scripts/ops/backup` (optional, keeps a local copy of the database).
2. EC2 → **Instances** → select `crewbie` → **Instance state → Terminate instance**. The root volume is deleted
   with it by default.
3. EC2 → **Elastic IPs** → select the address → **Actions → Release Elastic IP addresses**. An unreleased Elastic
   IP keeps billing.
4. EC2 → **Volumes**: delete any volume still listed as *available*.
5. EC2 → **Snapshots**: delete snapshots you don't need (they bill per GB).
6. IAM → **Users** → `crewbie-ops` → delete (removes its access keys). Remove the `crewbie-ops` profile from
   `~/.aws/credentials`.
7. Check every region once: EC2 dashboard → **Global view** shows resources across all regions.
8. A few days later, Billing → **Bills**: confirm no new EC2 charges.
