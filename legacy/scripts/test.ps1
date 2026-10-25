$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
foreach ($suite in @('participants','opportunities','negotiation','commitments','realtime','cubbie','integration')) {
    python -B -m unittest discover -s "tests/$suite" -v
    if ($LASTEXITCODE -ne 0) { throw "Failed suite: $suite" }
}
} finally { Pop-Location }
