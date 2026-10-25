#!/usr/bin/env bash
# Copy a consistent snapshot of the SQLite database to backups/ (gitignored).
# The file holds encrypted envelopes: keep CREWBIE_ENVELOPE_KEY safe or the backup cannot be read.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env SSH_KEY_PATH SSH_USER ELASTIC_IP REMOTE_DIR
need scp "Install an OpenSSH client."

stamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${REPO_ROOT}/backups"
target="${REPO_ROOT}/backups/crewbie-${stamp}.db"

say "Backing up the database on the instance"
# SQLite's online backup API inside the container: safe while the app is writing.
ssh_cmd "set -e
cd '${REMOTE_DIR}'
${COMPOSE} exec -T crewbie python -c \"import sqlite3; s = sqlite3.connect('/data/crewbie.db'); d = sqlite3.connect('/tmp/backup.db'); s.backup(d); d.close()\"
${COMPOSE} cp crewbie:/tmp/backup.db /tmp/crewbie-backup.db"
scp -i "${SSH_KEY}" "${SSH_OPTS[@]}" "${SSH_USER}@${ELASTIC_IP}:/tmp/crewbie-backup.db" "${target}"
ssh_cmd "rm -f /tmp/crewbie-backup.db"
chmod 600 "${target}"
say "Saved ${target}"
