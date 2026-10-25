# Point the SSH rule of the security group at this machine's current public IP.
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv AWS_PROFILE, AWS_REGION, SECURITY_GROUP_ID

$mine = (Invoke-RestMethod -Uri 'https://checkip.amazonaws.com' -TimeoutSec 10).ToString().Trim() + '/32'
Say "Your address: $mine"
$query = 'SecurityGroups[0].IpPermissions[?FromPort==`22` && ToPort==`22` && IpProtocol==''tcp''].IpRanges[].CidrIp'
$current = @((Invoke-Aws ec2 describe-security-groups --group-ids $env:SECURITY_GROUP_ID `
    --query $query --output text) -split '\s+' | Where-Object { $_ })

if ($current -notcontains $mine) {
    Say "Allowing SSH from $mine"
    Invoke-Aws ec2 authorize-security-group-ingress --group-id $env:SECURITY_GROUP_ID `
        --protocol tcp --port 22 --cidr $mine | Out-Null
}
foreach ($cidr in $current) {
    if ($cidr -ne $mine) {
        Say "Removing the old SSH rule for $cidr"
        Invoke-Aws ec2 revoke-security-group-ingress --group-id $env:SECURITY_GROUP_ID `
            --protocol tcp --port 22 --cidr $cidr | Out-Null
    }
}
Say "SSH is now allowed only from $mine"
