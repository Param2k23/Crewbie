#!/usr/bin/env bash
# Instance state, public IP and what /healthz says.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env AWS_PROFILE AWS_REGION INSTANCE_ID CREWBIE_HOSTNAME

state="$(aws_cmd ec2 describe-instances --instance-ids "${INSTANCE_ID}" \
    --query 'Reservations[0].Instances[0].State.Name' --output text)"
address="$(aws_cmd ec2 describe-instances --instance-ids "${INSTANCE_ID}" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
say "instance: ${state}"
say "public ip: ${address}"
if body="$(healthz 2>/dev/null)"; then
    say "healthz: ${body}"
else
    say "healthz: no answer from https://${CREWBIE_HOSTNAME}/healthz"
fi
