#!/usr/bin/env bash
# Open a shell on the instance.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env SSH_KEY_PATH SSH_USER ELASTIC_IP
need ssh "Install an OpenSSH client."
exec ssh -i "${SSH_KEY}" "${SSH_OPTS[@]}" "${SSH_USER}@${ELASTIC_IP}"
