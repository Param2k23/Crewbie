#!/usr/bin/env bash
# Pull GIT_BRANCH on the instance and rebuild and restart the containers.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env SSH_KEY_PATH SSH_USER ELASTIC_IP REMOTE_DIR GIT_BRANCH CREWBIE_HOSTNAME

say "Deploying ${GIT_BRANCH} to ${ELASTIC_IP}"
ssh_cmd "set -e
cd '${REMOTE_DIR}'
test -f .env || { echo 'No .env on the server. Run scripts/ops/push-env.sh first.' >&2; exit 1; }
git fetch --prune origin
git checkout '${GIT_BRANCH}'
git pull --ff-only origin '${GIT_BRANCH}'
${COMPOSE} up -d --build
${COMPOSE} ps"
say "Waiting for /healthz (up to 2 minutes)"
body="$(wait_for_health 120)" || die "healthz did not answer. Try scripts/ops/logs.sh"
say "Healthy: ${body}"
