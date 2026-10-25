"""The bash ops scripts, run against stub aws/ssh/scp/curl commands that record their arguments.

There is no AWS here, so these tests check what each script *asks for*: the right commands, in
the right order, with the safety rules (confirmation, no secrets in git, no lock-out) enforced.
"""

import base64
import os
import subprocess
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[2] / "scripts/ops"
KEY = base64.urlsafe_b64encode(b"k" * 32).decode()

STUB = """#!/usr/bin/env bash
# Log one line per call, even when an argument spans several lines.
printf '%s\n' "$(basename "$0") $*" | tr '\n' ' ' >> "$FAKE_LOG"; echo >> "$FAKE_LOG"
if [ "$(basename "$0")" = scp ]; then
  last="${*: -1}"
  case "$last" in *:*) ;; *) : > "$last" ;; esac
fi
case "$(basename "$0") $*" in
  *"describe-instances"*"State.Name"*) echo "${FAKE_STATE:-running}" ;;
  *"describe-instances"*"PublicIpAddress"*) echo "203.0.113.10" ;;
  *"describe-instances"*"VolumeId"*) echo "vol-0abc" ;;
  *"describe-security-groups"*) echo "${FAKE_SG_CIDRS:-198.51.100.7/32}" ;;
  *"create-snapshot"*) echo "snap-0abc" ;;
  "curl"*"checkip.amazonaws.com"*) echo "192.0.2.55" ;;
  "curl"*"/healthz"*)
    [ "${FAKE_HEALTH:-ok}" = "ok" ] || exit 22
    echo '{"status":"ok","discord":"connected"}' ;;
esac
exit 0
"""


@pytest.fixture
def sandbox(tmp_path: Path):  # type: ignore[no-untyped-def]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("aws", "ssh", "scp", "curl"):
        stub = bin_dir / name
        stub.write_text(STUB)
        stub.chmod(0o755)
    ops_env = tmp_path / "ops.env"
    ops_env.write_text(
        "AWS_PROFILE=crewbie-ops\nAWS_REGION=us-west-2\nINSTANCE_ID=i-0abc\n"
        "SECURITY_GROUP_ID=sg-0abc\nELASTIC_IP=203.0.113.10\n"
        "CREWBIE_HOSTNAME=203-0-113-10.sslip.io\nSSH_KEY_PATH=~/.ssh/crewbie-key.pem\n"
        "SSH_USER=ubuntu\nREMOTE_DIR=/opt/crewbie\nGIT_BRANCH=crewbie-v2\n"
    )
    log = tmp_path / "calls.log"
    log.touch()

    def run(
        script: str, *args: str, stdin: str = "", **env: str
    ) -> subprocess.CompletedProcess[str]:
        full_env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "OPS_ENV_FILE": str(ops_env),
            "FAKE_LOG": str(log),
            **env,
        }
        return subprocess.run(
            ["bash", str(OPS / script), *args], input=stdin, capture_output=True, text=True,
            env=full_env, timeout=120, check=False,
        )  # fmt: skip

    def calls() -> list[str]:
        return [line.strip() for line in log.read_text().splitlines() if line.strip()]

    return run, calls, ops_env, tmp_path


def test_a_missing_ops_env_says_how_to_create_it(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, _, ops_env, _ = sandbox
    ops_env.unlink()
    result = run("status.sh")
    assert result.returncode == 1 and "ops.env.example" in result.stderr


def test_a_missing_value_names_the_variable(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, ops_env, _ = sandbox
    ops_env.write_text(ops_env.read_text().replace("INSTANCE_ID=i-0abc\n", ""))
    result = run("up.sh")
    assert result.returncode == 1 and "INSTANCE_ID is not set" in result.stderr
    assert calls() == []  # nothing was sent to AWS


def test_up_starts_waits_for_checks_then_for_health(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    result = run("up.sh")
    assert result.returncode == 0, result.stderr
    aws = [c for c in calls() if c.startswith("aws")]
    assert "start-instances --instance-ids i-0abc" in aws[0]
    assert "--profile crewbie-ops --region us-west-2" in aws[0]
    assert "wait instance-running" in aws[1] and "wait instance-status-ok" in aws[2]
    assert any("https://203-0-113-10.sslip.io/healthz" in c for c in calls())
    assert '"discord":"connected"' in result.stdout


def test_down_asks_first_and_only_stops_on_yes(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    declined = run("down.sh", stdin="n\n")
    assert declined.returncode == 0 and "Cancelled" in declined.stdout
    assert not any("stop-instances" in c for c in calls())
    confirmed = run("down.sh", stdin="y\n")
    assert confirmed.returncode == 0
    stops = [c for c in calls() if "stop-instances" in c or "wait instance-stopped" in c]
    assert len(stops) == 2 and "stop-instances" in stops[0]
    assert run("down.sh", "--yes").returncode == 0


def test_status_reports_state_ip_and_health_and_tolerates_a_stopped_server(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, _, _, _ = sandbox
    up = run("status.sh")
    assert "instance: running" in up.stdout and "public ip: 203.0.113.10" in up.stdout
    assert '"status":"ok"' in up.stdout
    down = run("status.sh", FAKE_STATE="stopped", FAKE_HEALTH="down")
    assert (
        down.returncode == 0 and "instance: stopped" in down.stdout and "no answer" in down.stdout
    )


def test_deploy_pulls_the_branch_rebuilds_and_checks_health(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    result = run("deploy.sh")
    assert result.returncode == 0, result.stderr
    (remote,) = [c for c in calls() if c.startswith("ssh")]
    assert "ubuntu@203.0.113.10" in remote and "-i " in remote
    for expected in (
        "cd '/opt/crewbie'", "git checkout 'crewbie-v2'", "git pull --ff-only origin 'crewbie-v2'",
        "docker compose --env-file .env -f deploy/docker-compose.yml up -d --build",
    ):  # fmt: skip
        assert expected in remote
    assert "push-env.sh first" in remote  # fails clearly if the server has no .env yet


def test_logs_follow_the_application_container_with_a_terminal(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    assert run("logs.sh").returncode == 0
    (remote,) = [c for c in calls() if c.startswith("ssh")]
    assert "ssh -t" in remote and "logs --tail 200 -f crewbie" in remote


def test_ssh_script_connects_with_the_key_and_user(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    assert run("ssh.sh").returncode == 0
    (remote,) = calls()
    assert remote.endswith("ubuntu@203.0.113.10") and "crewbie-key.pem" in remote


def env_prod(tmp_path: Path, body: str | None = None) -> Path:
    path = tmp_path / ".env.prod"
    path.write_text(
        body
        if body is not None
        else f"CREWBIE_ENV=prod\nCREWBIE_PUBLIC_URL=https://203-0-113-10.sslip.io\nCREWBIE_ENVELOPE_KEY={KEY}\n"
    )
    return path


def test_push_env_copies_the_file_and_locks_down_its_permissions(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, tmp_path = sandbox
    result = run("push-env.sh", ENV_PROD_FILE=str(env_prod(tmp_path)))
    assert result.returncode == 0, result.stderr
    scp = next(c for c in calls() if c.startswith("scp"))
    assert scp.endswith("ubuntu@203.0.113.10:/opt/crewbie/.env")
    assert any("chmod 600 '/opt/crewbie/.env'" in c for c in calls())
    assert KEY not in result.stdout + result.stderr


def test_push_env_refuses_a_missing_file_placeholders_or_a_broken_config(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, tmp_path = sandbox
    missing = run("push-env.sh", ENV_PROD_FILE=str(tmp_path / "nope"))
    assert missing.returncode == 1 and "missing" in missing.stderr
    placeholders = run(
        "push-env.sh",
        ENV_PROD_FILE=str(env_prod(tmp_path, "CREWBIE_PUBLIC_URL=https://<CREWBIE_HOSTNAME>\n")),
    )
    assert placeholders.returncode == 1 and "placeholders" in placeholders.stderr
    broken = run(
        "push-env.sh",
        ENV_PROD_FILE=str(
            env_prod(tmp_path, "CREWBIE_ENV=prod\nCREWBIE_ADMIN_TOKEN=hunter2hunter2\n")
        ),
    )
    assert broken.returncode == 1 and "CREWBIE_ENVELOPE_KEY: missing" in broken.stderr
    assert "hunter2" not in broken.stdout + broken.stderr  # names only, never values
    assert not any(c.startswith("scp") for c in calls())


def test_push_env_refuses_a_file_that_git_tracks(sandbox, tmp_path_factory) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    tracked = Path(__file__).resolve().parents[2] / "pyproject.toml"  # any tracked file will do
    result = run("push-env.sh", ENV_PROD_FILE=str(tracked))
    assert result.returncode == 1 and "tracked by git" in result.stderr
    assert not any(c.startswith("scp") for c in calls())


def test_backup_uses_sqlites_online_backup_and_saves_under_backups(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    result = run("backup.sh")
    assert result.returncode == 0, result.stderr
    remote = next(c for c in calls() if "sqlite3.connect" in c)
    assert "s.backup(d)" in remote and "compose" in remote
    scp = next(c for c in calls() if c.startswith("scp"))
    assert "/tmp/crewbie-backup.db" in scp and "/backups/crewbie-" in scp
    assert any("rm -f /tmp/crewbie-backup.db" in c for c in calls())
    for saved in (OPS.parents[1] / "backups").glob("crewbie-*.db"):
        saved.unlink()


def test_snapshot_targets_the_root_volume_with_a_dated_tag(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    result = run("snapshot.sh")
    assert result.returncode == 0 and "snap-0abc" in result.stdout
    create = next(c for c in calls() if "create-snapshot" in c)
    assert "--volume-id vol-0abc" in create and "Key=Name,Value=crewbie-" in create


def test_allow_my_ip_adds_the_new_address_before_removing_the_old_one(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    result = run("allow-my-ip.sh", FAKE_SG_CIDRS="198.51.100.7/32")
    assert result.returncode == 0, result.stderr
    changes = [c for c in calls() if "security-group-ingress" in c]
    assert "authorize-security-group-ingress" in changes[0] and "192.0.2.55/32" in changes[0]
    assert "revoke-security-group-ingress" in changes[1] and "198.51.100.7/32" in changes[1]
    assert all("--port 22" in c and "--group-id sg-0abc" in c for c in changes)


def test_allow_my_ip_is_a_no_op_when_the_address_is_already_allowed(sandbox) -> None:  # type: ignore[no-untyped-def]
    run, calls, _, _ = sandbox
    assert run("allow-my-ip.sh", FAKE_SG_CIDRS="192.0.2.55/32").returncode == 0
    assert not [c for c in calls() if "security-group-ingress" in c]
