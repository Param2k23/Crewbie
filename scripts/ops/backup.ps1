# Copy a consistent snapshot of the SQLite database to backups\ (gitignored).
# The file holds encrypted envelopes: keep CREWBIE_ENVELOPE_KEY safe or the backup cannot be read.
. "$PSScriptRoot\lib.ps1"
Import-OpsEnv SSH_KEY_PATH, SSH_USER, ELASTIC_IP, REMOTE_DIR

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$directory = Join-Path $script:RepoRoot 'backups'
New-Item -ItemType Directory -Force $directory | Out-Null
$target = Join-Path $directory "crewbie-$stamp.db"

Say 'Backing up the database on the instance'
# SQLite's online backup API inside the container: safe while the app is writing.
$python = "import sqlite3; s = sqlite3.connect('/data/crewbie.db'); d = sqlite3.connect('/tmp/backup.db'); s.backup(d); d.close()"
$remote = @"
set -e
cd '$($env:REMOTE_DIR)'
$($script:Compose) exec -T crewbie python -c "$python"
$($script:Compose) cp crewbie:/tmp/backup.db /tmp/crewbie-backup.db
"@
Invoke-Ssh $remote | Out-Null
Invoke-Native 'scp' (@('-i', $script:SshKey) + $script:SshOpts +
    @("$($env:SSH_USER)@$($env:ELASTIC_IP):/tmp/crewbie-backup.db", $target)) | Out-Null
Invoke-Ssh 'rm -f /tmp/crewbie-backup.db' | Out-Null
Say "Saved $target"
