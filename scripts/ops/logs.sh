#!/usr/bin/env bash
# Follow the application log on the instance (Ctrl+C to stop).
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env SSH_KEY_PATH SSH_USER ELASTIC_IP REMOTE_DIR
ssh_tty "cd '${REMOTE_DIR}' && ${COMPOSE} logs --tail 200 -f crewbie"
