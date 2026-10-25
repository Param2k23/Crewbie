# Copy .env.prod (local, never committed) to the instance as .env with mode 600.
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv SSH_KEY_PATH, SSH_USER, ELASTIC_IP, REMOTE_DIR

$file = if ($env:ENV_PROD_FILE) { $env:ENV_PROD_FILE } else { Join-Path $script:RepoRoot '.env.prod' }
if (-not (Test-Path $file)) {
    Fail "missing $file. Copy docs\spec\env.prod.example to .env.prod and fill in the secrets."
}
& git -C $script:RepoRoot ls-files --error-unmatch $file 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Fail '.env.prod is tracked by git. Run: git rm --cached .env.prod' }
if (Select-String -Path $file -Pattern '<' -Quiet) {
    Fail '.env.prod still has <placeholders>. Fill in every value first.'
}
if (Get-Command uv -ErrorAction SilentlyContinue) {
    # Names only; values are never printed.
    $check = @'
import os
import sys
from pathlib import Path
from crewbie.config import collect_raw_values, startup_problems

problems = startup_problems(collect_raw_values(Path(os.environ["ENV_PROD_CHECK"]), {}))
for problem in problems:
    sys.stderr.write("  " + problem + "\n")
sys.exit(1 if problems else 0)
'@
    $env:ENV_PROD_CHECK = $file
    Push-Location $script:RepoRoot
    try { $check | uv run python - } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { Fail '.env.prod would not start in production. Fix the variables listed above.' }
} else {
    Say 'uv not found; skipping the local .env.prod check'
}

Say "Copying .env.prod to $($env:ELASTIC_IP):$($env:REMOTE_DIR)/.env"
Invoke-Native 'scp' (@('-i', $script:SshKey) + $script:SshOpts +
    @($file, "$($env:SSH_USER)@$($env:ELASTIC_IP):$($env:REMOTE_DIR)/.env")) | Out-Null
Invoke-Ssh "chmod 600 '$($env:REMOTE_DIR)/.env'" | Out-Null
Say 'Done. Run scripts\ops\deploy.ps1 to apply it.'
