#!/usr/bin/env bash
# Point the SSH rule of the security group at this machine's current public IP.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env AWS_PROFILE AWS_REGION SECURITY_GROUP_ID
need curl "Install curl."

mine="$(curl -fsS --max-time 10 https://checkip.amazonaws.com | tr -d '[:space:]')/32"
say "Your address: ${mine}"
current="$(aws_cmd ec2 describe-security-groups --group-ids "${SECURITY_GROUP_ID}" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`22\` && ToPort==\`22\` && IpProtocol=='tcp'].IpRanges[].CidrIp" \
    --output text)"

present=0
for cidr in ${current}; do
    [ "${cidr}" = "${mine}" ] && present=1
done
if [ "${present}" = "0" ]; then
    say "Allowing SSH from ${mine}"
    aws_cmd ec2 authorize-security-group-ingress --group-id "${SECURITY_GROUP_ID}" \
        --protocol tcp --port 22 --cidr "${mine}" >/dev/null
fi
for cidr in ${current}; do
    if [ "${cidr}" != "${mine}" ]; then
        say "Removing the old SSH rule for ${cidr}"
        aws_cmd ec2 revoke-security-group-ingress --group-id "${SECURITY_GROUP_ID}" \
            --protocol tcp --port 22 --cidr "${cidr}" >/dev/null
    fi
done
say "SSH is now allowed only from ${mine}"
