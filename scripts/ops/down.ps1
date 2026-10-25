# Turn the instance off. The disk (and the database on it) is kept; compute billing stops.
#   down.ps1        asks first
#   down.ps1 -Yes   does not ask
param([switch]$Yes)
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv AWS_PROFILE, AWS_REGION, INSTANCE_ID

if (-not $Yes) {
    $answer = Read-Host "Stop $($env:INSTANCE_ID)? The Discord bot goes offline and crew.py will exit 3. [y/N]"
    if ($answer -notin @('y', 'Y', 'yes')) { Say 'Cancelled'; exit 0 }
}
Say "Stopping $($env:INSTANCE_ID)"
Invoke-Aws ec2 stop-instances --instance-ids $env:INSTANCE_ID | Out-Null
Say 'Waiting for the instance to stop'
Invoke-Aws ec2 wait instance-stopped --instance-ids $env:INSTANCE_ID | Out-Null
Say 'Stopped. Billing continues only for the disk and the Elastic IP.'
