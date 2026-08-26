$ErrorActionPreference = "Stop"

# ==================================================
# TeacherAI Production
# Web     : teacherai-07
# Backend : math-ai-07
# ==================================================

$FirebaseProjectId = "teacherai-07"
$FirebaseSite = "teacherai-07"

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

# --------------------------------------------------
Step "1/7 - Git kontrolü"

$branch = git branch --show-current

if ($branch -ne "main") {
    throw "Deploy sadece main branch üzerinden yapılabilir."
}

$status = git status --porcelain

if ($status) {
    Write-Host $status
    throw "Önce local değişiklikleri commit et."
}

# --------------------------------------------------
Step "2/7 - API container build"

gcloud config set project $ApiProjectId

gcloud builds submit `
    --config cloudbuild.api.yaml `
    --project $ApiProjectId

if ($LASTEXITCODE -ne 0) {
    throw "API container build başarısız."
}

# --------------------------------------------------
Step "3/7 - Cloud Run deploy"

gcloud run deploy $ServiceName `
    --image $Image `
    --region $Region `
    --project $ApiProjectId `
    --platform managed `
    --allow-unauthenticated `
    --port 8000 `
    --set-secrets "OPENAI_API_KEY=openai-api-key:latest"

if ($LASTEXITCODE -ne 0) {
    throw "Cloud Run deploy başarısız."
}

# --------------------------------------------------
Step "4/7 - API adresi"

$ApiUrl = gcloud run services describe $ServiceName `
    --region $Region `
    --project $ApiProjectId `
    --format="value(status.url)"

if (-not $ApiUrl) {
    throw "Cloud Run URL alınamadı."
}

Write-Host "API: $ApiUrl"

# Static web build bu adresi kullanacak
$env:NEXT_PUBLIC_API_BASE_URL = "$ApiUrl/api/v1"

# --------------------------------------------------
Step "5/7 - Web build"

Remove-Item -Recurse -Force apps\web\out -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force apps\web\.next -ErrorAction SilentlyContinue

npm run build:web

if ($LASTEXITCODE -ne 0) {
    throw "Web build başarısız."
}

if (-not (Test-Path "apps\web\out\index.html")) {
    throw "apps/web/out/index.html bulunamadı."
}

Write-Host "Web build: OK"

# --------------------------------------------------
Step "6/7 - Firebase Hosting"

firebase use $FirebaseProjectId

if ($LASTEXITCODE -ne 0) {
    throw "Firebase proje seçimi başarısız."
}

firebase deploy --only hosting

if ($LASTEXITCODE -ne 0) {
    throw "Firebase Hosting deploy başarısız."
}

# --------------------------------------------------
Step "7/7 - Tamamlandı"

Write-Host ""
Write-Host "=================================================="
Write-Host "DEPLOY BAŞARILI"
Write-Host "Web: https://$FirebaseSite.web.app"
Write-Host "API: $ApiUrl"
Write-Host "=================================================="