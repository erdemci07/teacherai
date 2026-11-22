# TA-005B: production dağıtımı. Karar ve sıra mantığı scripts/deploy_plan.py içindedir; bu dosya yalnız sarmalayıcıdır.
#
#   .\scripts\deploy-production.ps1 -Mode Bootstrap|Update [-Region europe-west1]            # yalnız plan (varsayılan)
#   .\scripts\deploy-production.ps1 -Mode Update -Region europe-west1 -Execute [-PublishHosting]
#
# Bölgenin varsayılanı scripts/deploy-production.json içindeki K2 kararıdır; karar yoksa -Region zorunludur.
param(
    [Parameter(Mandatory = $true)][ValidateSet("Bootstrap", "Update")][string]$Mode,
    [string]$Region,
    [switch]$PlanOnly,
    [switch]$Execute,
    [switch]$PublishHosting
)
$ErrorActionPreference = "Stop"

if ($PlanOnly -and $Execute) { throw "-PlanOnly ve -Execute birlikte kullanılamaz." }

$python = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$arguments = @("-m", "scripts.deploy_plan", "--mode", $Mode.ToLowerInvariant())
if ($Region) { $arguments += @("--region", $Region) }
if ($Execute) { $arguments += "--execute" } else { $arguments += "--plan-only" }
if ($PublishHosting) { $arguments += "--publish-hosting" }

& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "Dağıtım durdu (çıkış $LASTEXITCODE)." }
