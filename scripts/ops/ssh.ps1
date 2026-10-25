# Open a shell on the instance.
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv SSH_KEY_PATH, SSH_USER, ELASTIC_IP
& ssh -i $script:SshKey @script:SshOpts "$($env:SSH_USER)@$($env:ELASTIC_IP)"
