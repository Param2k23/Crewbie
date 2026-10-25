#!/usr/bin/env bash
# Turn the instance off. The disk (and the database on it) is kept; compute billing stops.
#   down.sh        asks first
#   down.sh --yes  does not ask
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env AWS_PROFILE AWS_REGION INSTANCE_ID

if [ "${1:-}" != "--yes" ]; then
    read -r -p "Stop ${INSTANCE_ID}? The Discord bot goes offline and crew.py will exit 3. [y/N] " answer
    case "${answer}" in
        y | Y | yes) ;;
        *) say "Cancelled"; exit 0 ;;
    esac
fi
say "Stopping ${INSTANCE_ID}"
aws_cmd ec2 stop-instances --instance-ids "${INSTANCE_ID}" >/dev/null
say "Waiting for the instance to stop"
aws_cmd ec2 wait instance-stopped --instance-ids "${INSTANCE_ID}"
say "Stopped. Billing continues only for the disk and the Elastic IP."
