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

Step "1/7 - Google Cloud API projesi"

gcloud config set project $ApiProjectId
Assert-LastExitCode "Google Cloud projesi ayarlanamadı."


Step "2/7 - API container build"

gcloud builds submit `
    --config cloudbuild.api.yaml `
    --project $ApiProjectId

Assert-LastExitCode "Cloud Build başarısız."


Step "3/7 - Cloud Run deploy"

gcloud run deploy $ServiceName `
    --image $Image `
    --region $Region `
    --project $ApiProjectId `
    --platform managed `
    --allow-unauthenticated `
    --port 8000

Assert-LastExitCode "Cloud Run deploy başarısız."


Step "4/7 - Cloud Run URL"

$ApiUrl = gcloud run services describe $ServiceName `
    --region $Region `
    --project $ApiProjectId `
    --format="value(status.url)"

Assert-LastExitCode "Cloud Run URL alınamadı."

if (-not $ApiUrl) {
    throw "Cloud Run URL boş döndü."
}

$ApiBaseUrl = "$ApiUrl/api/v1"

Write-Host "API: $ApiUrl"


Step "5/7 - Web production build"

$env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl

Remove-Item -Recurse -Force apps\web\out -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force apps\web\.next -ErrorAction SilentlyContinue

npm run build:web
Assert-LastExitCode "Web production build başarısız."

if (-not (Test-Path "apps\web\out\index.html")) {
    throw "apps/web/out/index.html oluşturulamadı."
}


Step "6/7 - Firebase Hosting projesi"

firebase use $FirebaseProjectId
Assert-LastExitCode "Firebase projesi seçilemedi."


Step "7/7 - Firebase Hosting deploy"

firebase deploy --only hosting --project $FirebaseProjectId
Assert-LastExitCode "Firebase Hosting deploy başarısız."


Write-Host ""
Write-Host "=================================================="
Write-Host "DEPLOY BAŞARILI"
Write-Host "Web: $WebUrl"
Write-Host "API: $ApiUrl"
Write-Host "=================================================="