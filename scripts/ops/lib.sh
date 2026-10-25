#!/usr/bin/env bash
# Shared by the ops scripts: load ops.env, check required values, small helpers.
# Source it; do not run it.
set -euo pipefail

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # used by the scripts that source this file
REPO_ROOT="$(cd "${OPS_DIR}/../.." && pwd)"
OPS_ENV_FILE="${OPS_ENV_FILE:-${OPS_DIR}/ops.env}"
# shellcheck disable=SC2034
COMPOSE="docker compose --env-file .env -f deploy/docker-compose.yml"

say() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# load_ops_env NAME... : read ops.env, then require each NAME to be set and non-empty.
load_ops_env() {
    [ -f "${OPS_ENV_FILE}" ] || die "missing ${OPS_ENV_FILE}. Copy scripts/ops/ops.env.example to scripts/ops/ops.env and fill it in."
    set -a
    # shellcheck disable=SC1090
    . "${OPS_ENV_FILE}"
    set +a
    local name
    for name in "$@"; do
        [ -n "${!name:-}" ] || die "${name} is not set in ${OPS_ENV_FILE}"
    done
    SSH_KEY="${SSH_KEY_PATH:-}"
    SSH_KEY="${SSH_KEY/#\~/${HOME}}"
}

need() { command -v "$1" >/dev/null 2>&1 || die "$1 is not installed or not on PATH. $2"; }

aws_cmd() {
    need aws "Install the AWS CLI (see docs/spec/10-AWS-DEPLOYMENT.md, step A10)."
    aws --profile "${AWS_PROFILE}" --region "${AWS_REGION}" "$@"
}

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)

# ssh_cmd REMOTE_COMMAND : run a command on the instance.
ssh_cmd() {
    need ssh "Install an OpenSSH client."
    ssh -i "${SSH_KEY}" "${SSH_OPTS[@]}" "${SSH_USER}@${ELASTIC_IP}" "$@"
}

# ssh_tty REMOTE_COMMAND : same, with a terminal (for following logs).
ssh_tty() {
    ssh -t -i "${SSH_KEY}" "${SSH_OPTS[@]}" "${SSH_USER}@${ELASTIC_IP}" "$@"
}

healthz() { curl -fsS --max-time 10 "https://${CREWBIE_HOSTNAME}/healthz"; }

# wait_for_health SECONDS : poll /healthz until it answers ok.
wait_for_health() {
    local deadline=$((SECONDS + $1)) body
    until body="$(healthz 2>/dev/null)"; do
        [ "${SECONDS}" -lt "${deadline}" ] || return 1
        sleep 5
    done
    printf '%s\n' "${body}"
}
