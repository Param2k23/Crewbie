# Turn the instance on and wait until Crewbie answers.
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv AWS_PROFILE, AWS_REGION, INSTANCE_ID, CREWBIE_HOSTNAME

Say "Starting $($env:INSTANCE_ID)"
Invoke-Aws ec2 start-instances --instance-ids $env:INSTANCE_ID | Out-Null
Say 'Waiting for the instance to be running'
Invoke-Aws ec2 wait instance-running --instance-ids $env:INSTANCE_ID | Out-Null
Say 'Waiting for the status checks'
Invoke-Aws ec2 wait instance-status-ok --instance-ids $env:INSTANCE_ID | Out-Null
Say "Waiting for https://$($env:CREWBIE_HOSTNAME)/healthz (up to 5 minutes)"
$body = Wait-Health 300
if (-not $body) { Fail 'healthz did not answer within 5 minutes. Try scripts\ops\logs.ps1' }
Say "Up: $body"
