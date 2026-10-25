# Pull GIT_BRANCH on the instance and rebuild and restart the containers.
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv SSH_KEY_PATH, SSH_USER, ELASTIC_IP, REMOTE_DIR, GIT_BRANCH, CREWBIE_HOSTNAME

Say "Deploying $($env:GIT_BRANCH) to $($env:ELASTIC_IP)"
$remote = @"
set -e
cd '$($env:REMOTE_DIR)'
test -f .env || { echo 'No .env on the server. Run scripts/ops/push-env.ps1 first.' >&2; exit 1; }
git fetch --prune origin
git checkout '$($env:GIT_BRANCH)'
git pull --ff-only origin '$($env:GIT_BRANCH)'
$($script:Compose) up -d --build
$($script:Compose) ps
"@
Invoke-Ssh $remote | Write-Host
Say 'Waiting for /healthz (up to 2 minutes)'
$body = Wait-Health 120
if (-not $body) { Fail 'healthz did not answer. Try scripts\ops\logs.ps1' }
Say "Healthy: $body"
