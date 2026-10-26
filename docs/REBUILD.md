# Rebuild and teardown guide

Everything needed to bring Crewbie's server back after teardown, and to tear it down again. The full
step-by-step AWS console walkthrough (account, MFA, budget, IAM user) is in
[spec/10-AWS-DEPLOYMENT.md](spec/10-AWS-DEPLOYMENT.md) Part A; this page is the short path and the facts that
are easy to forget. Cost while running: about $0.35 per day (t4g.micro, 10 GB disk, Elastic IP). Stopped:
only the disk and IP, a few cents per day. Terminated and released: $0.

## What lives where

| Thing | Location | Survives teardown? |
|---|---|---|
| Code, Skill, website source | GitHub `Param2k23/Crewbie`, branch `master` | Yes |
| Website | Vercel project `crewbie` (crewbie-cubbie.vercel.app, cubbie-crewbie.vercel.app) | Yes, free tier |
| Server, database, Caddy certificates | EC2 instance in us-east-2 | No (deleted) |
| Secrets | `.env`, `.env.prod`, `scripts/ops/ops.env` on the owner's laptop (git-ignored) | Only on the laptop |
| Database copy | `backups/crewbie-20261026-122301.db` on the laptop (git-ignored) | Laptop only |
| Discord server and bot application | Discord Developer Portal and the owner's server | Yes (independent of AWS) |

Back up the secrets files somewhere safe. The envelope key (`CREWBIE_ENVELOPE_KEY`) is required to read any
restored database: private limits are encrypted with it and cannot be recovered without it.

## Rebuild

1. **Account and CLI user.** Follow 10-AWS-DEPLOYMENT.md A1 to A4 (MFA, budget/spend limit, region), A9
   (limited `crewbie-ops` user) and A10 (`aws configure --profile crewbie-ops`). Teardown deletes that user, so
   it must be recreated.
2. **Key pair, security group, instance, Elastic IP** (A5 to A8): Ubuntu 24.04 arm64, `t4g.micro`, 10 GB disk,
   ports 22 (your IP only), 80 and 443 open. Note the instance ID, security group ID and Elastic IP.
3. **Hostname.** With no domain, use `<ip-with-dashes>.sslip.io`, for example `18-220-104-252.sslip.io`. Caddy
   gets a free HTTPS certificate for it automatically.
4. **Config.** Copy `scripts/ops/ops.env.example` to `scripts/ops/ops.env` and fill the values from step 2
   (`GIT_BRANCH=master`). Copy `docs/spec/env.prod.example` to `.env.prod`, set `CREWBIE_PUBLIC_URL` and
   `CREWBIE_HOSTNAME` to the new hostname, and put in the Discord values and the two generated secrets
   (commands in 08-INPUTS-FROM-OWNER.md, I-11 and I-12). Reuse the old `CREWBIE_ENVELOPE_KEY` if you will
   restore the old database; generate a new one for a fresh start.
5. **First deploy** (10-AWS-DEPLOYMENT.md Part C):
   ```bash
   scripts/ops/ssh.sh                      # first login; then on the instance:
   sudo mkdir -p /opt/crewbie && sudo chown ubuntu:ubuntu /opt/crewbie
   git clone --branch master https://github.com/Param2k23/Crewbie.git /opt/crewbie
   sudo bash /opt/crewbie/deploy/bootstrap.sh
   exit                                    # log in again so the docker group applies
   scripts/ops/push-env.sh
   scripts/ops/deploy.sh
   scripts/ops/status.sh                   # expect running, healthz ok, discord connected
   ```
   Windows: use the `.ps1` versions of the same scripts.
6. **Restore data (optional).** Copy a backup to the instance's data volume and restart, or start fresh.
   Fresh start means students must link Discord again, and old board cards in `#crew-board` should be deleted.
7. **Point the Skill at the new server.** The address is baked in as `DEFAULT_API_URL` in
   `skills/crewbie-unlocks/scripts/crew.py`. Change it to the new hostname, run `uv run pytest tests/skill`,
   commit and push to `master`, then redeploy. Students re-send
   `Install https://github.com/Param2k23/Crewbie/tree/master/skills/crewbie-unlocks` to update. Also search for
   the old hostname in `docs/` and `apps/web/` (it appears in `DEMO_BRIEF.md`).
8. **Discord.** The bot application, server and channels survive. If the token was reset, set the new one in
   `.env.prod` and run `scripts/ops/push-env.sh`. Channel setup is in 08-INPUTS-FROM-OWNER.md, I-02.
9. **Website.** Unchanged unless an address appears on it. Redeploy with
   `cd apps/web && npx vercel@65.2.0 deploy --prod --yes`.
10. **Check.** `scripts/ops/status.sh`, then the live checks in `spec/LIVE_TEST.md` with two students.

Daily use: `scripts/ops/down.sh` stops the instance (keeps the disk), `up.sh` starts it (about 3 minutes), `logs.sh`,
`backup.sh`, `snapshot.sh`, `allow-my-ip.sh` if your home IP changed.

## Teardown (what was done on 2026-10-26)

Order matters; an unreleased Elastic IP or a leftover volume keeps billing.

1. `scripts/ops/backup.sh`, then copy `backups/` and the secrets files somewhere safe.
2. Terminate the instance (the root volume is deleted with it).
3. Release the Elastic IP.
4. Delete any volume left in state *available* and any snapshots.
5. Delete the security group and the key pair if you will not reuse them (free, but tidy).
6. Delete the IAM user `crewbie-ops` and remove its profile from `~/.aws/credentials`.
7. Check all regions in EC2's global view, then check Billing a few days later.

Exact commands (AWS CloudShell or any shell with admin rights, region us-east-2):

```bash
aws ec2 terminate-instances --region us-east-2 --instance-ids <INSTANCE_ID>
aws ec2 wait instance-terminated --region us-east-2 --instance-ids <INSTANCE_ID>
aws ec2 release-address --region us-east-2 --allocation-id <eipalloc-...>   # find it: aws ec2 describe-addresses
aws ec2 delete-security-group --region us-east-2 --group-id <SECURITY_GROUP_ID>
aws ec2 delete-key-pair --region us-east-2 --key-name <KEY_NAME>
```

The Discord bot stays online only while the server runs; after teardown it goes offline and `/crew` commands fail.
