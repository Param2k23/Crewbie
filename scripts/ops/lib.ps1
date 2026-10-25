# Shared by the ops scripts: load ops.env, check required values, small helpers.
# Dot-source it from a script (". $PSScriptRoot\lib.ps1"); do not run it directly.
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$script:OpsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:RepoRoot = (Resolve-Path (Join-Path $script:OpsDir '..\..')).Path
$script:Compose = 'docker compose --env-file .env -f deploy/docker-compose.yml'
$script:SshOpts = @('-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=15')

function Say([string]$Message) { Write-Host "==> $Message" }

function Fail([string]$Message) {
    [Console]::Error.WriteLine("ERROR: $Message")
    exit 1
}

# Import-OpsEnv NAME... : read ops.env, then require each NAME to be set and non-empty.
function Import-OpsEnv([string[]]$Required) {
    $file = if ($env:OPS_ENV_FILE) { $env:OPS_ENV_FILE } else { Join-Path $script:OpsDir 'ops.env' }
    if (-not (Test-Path $file)) {
        Fail "missing $file. Copy scripts\ops\ops.env.example to scripts\ops\ops.env and fill it in."
    }
    foreach ($line in Get-Content $file) {
        $text = $line.Trim()
        if ($text -eq '' -or $text.StartsWith('#')) { continue }
        $name, $value = $text -split '=', 2
        Set-Item -Path ("Env:" + $name.Trim()) -Value $value.Trim()
    }
    foreach ($name in $Required) {
        $item = Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        if ((-not $item) -or (-not $item.Value)) { Fail "$name is not set in $file" }
    }
    $script:SshKey = $env:SSH_KEY_PATH -replace '^~', $HOME
}

# Run a native program and stop with a clear message if it fails (PowerShell does not by default).
function Invoke-Native([string]$Tool, [string[]]$Arguments) {
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
        Fail "$Tool is not installed or not on PATH."
    }
    $output = & $Tool @Arguments
    if ($LASTEXITCODE -ne 0) { Fail "$Tool failed (exit code $LASTEXITCODE)." }
    $output
}

function Invoke-Aws {
    Invoke-Native 'aws' (@('--profile', $env:AWS_PROFILE, '--region', $env:AWS_REGION) + $args)
}

# Invoke-Ssh COMMAND [-Tty] : run a command on the instance.
function Invoke-Ssh([string]$Command, [switch]$Tty) {
    $options = @('-i', $script:SshKey) + $script:SshOpts
    if ($Tty) { $options = @('-t') + $options }
    $target = "$($env:SSH_USER)@$($env:ELASTIC_IP)"
    Invoke-Native 'ssh' ($options + @($target, ($Command -replace "`r", '')))
}

function Get-Health {
    try {
        Invoke-RestMethod -Uri "https://$($env:CREWBIE_HOSTNAME)/healthz" -TimeoutSec 10 |
            ConvertTo-Json -Compress
    } catch {
        $null
    }
}

# Wait-Health SECONDS : poll /healthz until it answers; returns the body or $null on timeout.
function Wait-Health([int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ($true) {
        $body = Get-Health
        if ($body) { return $body }
        if ((Get-Date) -gt $deadline) { return $null }
        Start-Sleep -Seconds 5
    }
}
