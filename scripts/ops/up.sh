#!/usr/bin/env bash
# Turn the instance on and wait until Crewbie answers.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env AWS_PROFILE AWS_REGION INSTANCE_ID CREWBIE_HOSTNAME

say "Starting ${INSTANCE_ID}"
aws_cmd ec2 start-instances --instance-ids "${INSTANCE_ID}" >/dev/null
say "Waiting for the instance to be running"
aws_cmd ec2 wait instance-running --instance-ids "${INSTANCE_ID}"
say "Waiting for the status checks"
aws_cmd ec2 wait instance-status-ok --instance-ids "${INSTANCE_ID}"
say "Waiting for https://${CREWBIE_HOSTNAME}/healthz (up to 5 minutes)"
body="$(wait_for_health 300)" || die "healthz did not answer within 5 minutes. Try scripts/ops/logs.sh"
say "Up: ${body}"
