# Take an EBS snapshot of the instance's root volume (tagged crewbie-<date>).
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv AWS_PROFILE, AWS_REGION, INSTANCE_ID

$volume = Invoke-Aws ec2 describe-instances --instance-ids $env:INSTANCE_ID `
    --query 'Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId' --output text
if ((-not $volume) -or ($volume -eq 'None')) { Fail "could not find the root volume of $($env:INSTANCE_ID)" }
$tag = 'crewbie-' + (Get-Date -Format 'yyyy-MM-dd')
Say "Snapshotting $volume as $tag"
Invoke-Aws ec2 create-snapshot --volume-id $volume --description $tag `
    --tag-specifications "ResourceType=snapshot,Tags=[{Key=Name,Value=$tag}]" `
    --query 'SnapshotId' --output text
Say 'Started. Snapshots bill per GB; delete old ones in the console when you no longer need them.'
