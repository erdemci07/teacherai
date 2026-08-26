$ErrorActionPreference = "Stop"

$FirebaseProjectId = "teacherai-07"
$FirebaseSite = "teacherai-07"
$WebUrl = "https://$FirebaseSite.web.app"

$ApiProjectId = "math-ai-07"
$Region = "us-east4"
$ServiceName = "teacherai-api"
$Image = "us-east4-docker.pkg.dev/$ApiProjectId/teacherai/teacherai-api:latest"

function Step($message) {
    Write-Host ""
    Write-Host "=================================================="
    Write-Host $message
    Write-Host "=================================================="
}

function Assert-LastExitCode($message) {
    if ($LASTEXITCODE -ne 0) {
        throw $message
    }
}

function Invoke-Checked($message, [scriptblock]$command) {
    & $command
    Assert-LastExitCode $message
}

Step "1/12 - Git repository kontrolü"

$branch = git branch --show-current
Assert-LastExitCode "Git branch kontrolü başarısız."

if ($branch -ne "main") {
    throw "Deploy sadece main branch üzerinden yapılabilir. Mevcut branch: $branch"
}

$status = git status --porcelain
Assert-LastExitCode "Git status kontrolü başarısız."

if ($status) {
    Write-Host "Working tree temiz değil:"
    Write-Host $status
    throw "Önce local değişiklikleri commit et. Deploy script local değişiklik yönetimi yapmaz."
}

Step "2/12 - Remote main güncelliği"

Invoke-Checked "git fetch origin main başarısız." { git fetch origin main }

$local = git rev-parse HEAD
Assert-LastExitCode "Local HEAD okunamadı."
$remote = git rev-parse origin/main
Assert-LastExitCode "origin/main okunamadı."

if ($local -ne $remote) {
    throw "Local main ile origin/main aynı değil. Önce: git pull --ff-only origin main"
}

Step "3/12 - API testleri"

if (Test-Path ".\.venv\Scripts\python.exe") {
    Invoke-Checked "API testleri başarısız." { .\.venv\Scripts\python.exe -m pytest -q apps/api/tests }
}
else {
    Invoke-Checked "API testleri başarısız." { python -m pytest -q apps/api/tests }
}

Step "4/12 - Google Cloud API projesi"

Invoke-Checked "gcloud API projesi ayarlanamadı." { gcloud config set project $ApiProjectId }

Step "5/12 - API container build"

Invoke-Checked "Cloud Build başarısız; Cloud Run deploy durduruldu." {
    gcloud builds submit `
        --config cloudbuild.api.yaml `
        --project $ApiProjectId
}

Step "6/12 - Cloud Run deploy"

Invoke-Checked "Cloud Run deploy başarısız." {
    gcloud run deploy $ServiceName `
        --image $Image `
        --region $Region `
        --project $ApiProjectId `
        --platform managed `
        --allow-unauthenticated `
        --port 8000
}

Step "7/12 - Cloud Run URL çözümleme"

$ApiUrl = gcloud run services describe $ServiceName `
    --region $Region `
    --project $ApiProjectId `
    --format="value(status.url)"
Assert-LastExitCode "Cloud Run URL alınamadı."

if (-not $ApiUrl) {
    throw "Cloud Run URL boş döndü."
}

$ApiBaseUrl = "$ApiUrl/api/v1"
Write-Host "API URL: $ApiUrl"
Write-Host "Frontend API base: $ApiBaseUrl"

Step "8/12 - Cloud Run public URL env güncelleme"

Invoke-Checked "Cloud Run public URL env güncellemesi başarısız." {
    gcloud run services update $ServiceName `
        --region $Region `
        --project $ApiProjectId `
        --update-env-vars "PUBLIC_APP_URL=$WebUrl,PUBLIC_SHARE_URL_BASE=$ApiUrl"
}

Step "9/12 - Cloud Run health check"

$health = Invoke-RestMethod -Uri "$ApiBaseUrl/health"

if (-not $health.success) {
    throw "API health check başarısız."
}

Write-Host "API health: OK"

Step "10/12 - Web production build"

$env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl

Remove-Item -Recurse -Force apps\web\out -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force apps\web\.next -ErrorAction SilentlyContinue

Invoke-Checked "Web production build başarısız." { npm run build:web }

if (-not (Test-Path "apps\web\out\index.html")) {
    throw "Static export oluşmadı: apps/web/out/index.html bulunamadı."
}

Step "11/12 - Firebase Hosting projesi"

Invoke-Checked "Firebase projesi seçilemedi." { firebase use $FirebaseProjectId }

Step "12/12 - Firebase Hosting deploy"

Invoke-Checked "Firebase Hosting deploy başarısız." { firebase deploy --only hosting --project $FirebaseProjectId }

Write-Host ""
Write-Host "=================================================="
Write-Host "DEPLOY BAŞARILI"
Write-Host "Web: $WebUrl"
Write-Host "API: $ApiUrl"
Write-Host "Share route: $ApiUrl/s/{share_id}"
Write-Host "=================================================="
