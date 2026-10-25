#!/usr/bin/env bash
# Take an EBS snapshot of the instance's root volume (tagged crewbie-<date>).
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env AWS_PROFILE AWS_REGION INSTANCE_ID

volume="$(aws_cmd ec2 describe-instances --instance-ids "${INSTANCE_ID}" \
    --query 'Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId' --output text)"
[ -n "${volume}" ] && [ "${volume}" != "None" ] || die "could not find the root volume of ${INSTANCE_ID}"
tag="crewbie-$(date +%Y-%m-%d)"
say "Snapshotting ${volume} as ${tag}"
aws_cmd ec2 create-snapshot --volume-id "${volume}" --description "${tag}" \
    --tag-specifications "ResourceType=snapshot,Tags=[{Key=Name,Value=${tag}}]" \
    --query 'SnapshotId' --output text
say "Started. Snapshots bill per GB; delete old ones in the console when you no longer need them."
