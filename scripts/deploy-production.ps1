$ErrorActionPreference = "Stop"

# API / Google Cloud
$ProjectId = "math-ai-07"
$Region = "us-east4"
$ServiceName = "teacherai-api"
$Image = "us-east4-docker.pkg.dev/$ProjectId/teacherai/teacherai-api:latest"

# Firebase Hosting
$FirebaseProjectId = "teacherai-07"
$FirebaseSite = "teacherai-07"

function Step($message) {
    Write-Host ""
    Write-Host "=================================================="
    Write-Host $message
    Write-Host "=================================================="
}

Step "1/9 - Git repository kontrolü"

$branch = git branch --show-current

if ($branch -ne "main") {
    throw "Deploy sadece main branch üzerinden yapılabilir. Mevcut branch: $branch"
}

$status = git status --porcelain

if ($status) {
    Write-Host "Working tree temiz değil:"
    Write-Host $status
    throw "Önce local değişiklikleri commit/stash et."
}


Step "2/9 - Remote main güncelliği"

git fetch origin main

$local = git rev-parse HEAD
$remote = git rev-parse origin/main

if ($local -ne $remote) {
    throw "Local main ile origin/main aynı değil. Önce: git pull --ff-only origin main"
}


Step "3/9 - API testleri"

if (Test-Path ".\.venv\Scripts\python.exe") {
    .\.venv\Scripts\python.exe -m pytest -q apps/api/tests
}
else {
    python -m pytest -q apps/api/tests
}


Step "4/9 - Web production build"

$env:NEXT_PUBLIC_API_BASE_URL = "/api/v1"

Remove-Item -Recurse -Force apps\web\out -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force apps\web\.next -ErrorAction SilentlyContinue

npm run build:web

if (-not (Test-Path "apps\web\out\index.html")) {
    throw "Static export oluşmadı: apps/web/out/index.html bulunamadı."
}


Step "5/9 - Google Cloud proje kontrolü"

gcloud config set project $ProjectId


Step "6/9 - API container build"

gcloud builds submit `
    --config cloudbuild.api.yaml `
    --project $ProjectId


Step "7/9 - Cloud Run deploy"

gcloud run deploy $ServiceName `
    --image $Image `
    --region $Region `
    --project $ProjectId `
    --platform managed `
    --port 8000 `
    --set-secrets "OPENAI_API_KEY=openai-api-key:latest" `
    --async
Step "8/9 - Cloud Run health check"

$ApiUrl = gcloud run services describe $ServiceName `
    --region $Region `
    --project $ProjectId `
    --format="value(status.url)"

if (-not $ApiUrl) {
    throw "Cloud Run URL alınamadı."
}

Write-Host "API URL: $ApiUrl"
Write-Host "Yeni revision hazır olması bekleniyor..."

$healthOk = $false

for ($i = 1; $i -le 30; $i++) {
    try {
        $health = Invoke-RestMethod `
            -Uri "$ApiUrl/api/v1/health" `
            -TimeoutSec 10

        if ($health.success) {
            $healthOk = $true
            break
        }
    }
    catch {
        Write-Host "API henüz hazır değil... ($i/30)"
    }

    Start-Sleep -Seconds 5
}

if (-not $healthOk) {
    throw "Cloud Run yeni revision zamanında hazır olmadı."
}

Write-Host "API health: OK"Step "9/9 - Firebase Hosting deploy"

firebase use $FirebaseProjectId

firebase deploy --only hosting --project $FirebaseProjectId


Write-Host ""
Write-Host "=================================================="
Write-Host "DEPLOY BAŞARILI"
Write-Host "Web: https://$FirebaseSite.web.app"
Write-Host "API: $ApiUrl"
Write-Host "=================================================="