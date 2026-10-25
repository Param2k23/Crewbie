# Follow the application log on the instance (Ctrl+C to stop).
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv SSH_KEY_PATH, SSH_USER, ELASTIC_IP, REMOTE_DIR
Invoke-Ssh "cd '$($env:REMOTE_DIR)' && $($script:Compose) logs --tail 200 -f crewbie" -Tty
