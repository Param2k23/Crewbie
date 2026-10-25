# Instance state, public IP and what /healthz says.
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv AWS_PROFILE, AWS_REGION, INSTANCE_ID, CREWBIE_HOSTNAME

$state = Invoke-Aws ec2 describe-instances --instance-ids $env:INSTANCE_ID `
    --query 'Reservations[0].Instances[0].State.Name' --output text
$address = Invoke-Aws ec2 describe-instances --instance-ids $env:INSTANCE_ID `
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
Say "instance: $state"
Say "public ip: $address"
$body = Get-Health
if ($body) { Say "healthz: $body" } else { Say "healthz: no answer from https://$($env:CREWBIE_HOSTNAME)/healthz" }
