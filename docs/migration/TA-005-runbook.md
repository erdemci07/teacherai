# TA-005 runbook: math-ai-07 → teacherai-07 tek proje geçişi

**Bu fazda hiçbir adım çalıştırılmadı.** Aşağıdaki [W] komutların her biri, Erdem'in o adım için ayrı ve açık onayıyla çalıştırılır. [R] komutlar salt okunurdur. Her komutta `--project` açıkça verilir; `gcloud config set project` ve `firebase use` kullanılmaz.

Değişkenler:

```
SRC=math-ai-07
DST=teacherai-07
REGION=us-east4      # K2 kararına göre değişebilir
DB_LOCATION=<K2>     # örn. eur3
```

## 0. Karar kapıları (adım 2'den önce)

| Kapı | Durum (denetim) | Gerekli karar |
| --- | --- | --- |
| K1 Auth | (b) kanıtı güçlü: bütün web uygulamaları ve `authDomain` SRC'de. Sayılar doğrulanmadı. | Erdem `audit_projects` betiğini çalıştırır. Kesişim > 0 ise (c) kolu uygulanır ve **durulur**. |
| K2 Firestore konumu | DST'de veritabanı yok. SRC **eur3**'te, Cloud Run us-east4'te. | Konum seçimi. Konum sonradan **değiştirilemez**. |
| K3 Blaze | DST Spark planında | Ücretli yükseltme onayı |
| K4 run.app bağlantıları | Olası (26 Ağustos'ta ~3 saatlik pencere). Bugünkü bağlantılar run.app'e 302 ile gidiyor. | Eski serviste en az 30 gün yönlendirme |
| Hedef | Denetime göre SRC'de her şey var; DST'de yalnız Hosting sitesi var | Aşağıdaki not |

**Hedefin yeniden değerlendirilmesi (bilgi notu, karar Erdem'in).** DST'ye taşımak şunları gerektirir: Auth dışa/içe aktarımı (kullanıcılar yeniden oturum açar), yeni Firestore veritabanı ve veri kopyası, yeni Secret Manager, Artifact Registry ve Cloud Run kaynakları. Tersi yönde, yani her şeyi SRC'de toplamak, yalnız Hosting'in taşınmasını gerektirir. Ancak `teacherai-07.web.app` alan adı DST projesine bağlıdır ve taşınamaz. Alan adını korumak için ya DST'de bir yönlendirme sitesi kalmalı ya da özel alan adı kullanılmalıdır. Bu runbook verilen hedefe (DST) göre yazıldı.

### K2: konum karşılaştırması

| Seçenek | Cloud Run ile gecikme | Veri konumu ve KVKK (hukuki değerlendirme Erdem'de) | Not |
| --- | --- | --- | --- |
| **eur3** (europe-west1 + europe-west4) | Cloud Run europe-west1'e taşınırsa aynı bölge. us-east4'te kalırsa bugünkü gibi Atlantik ötesi. | Veri bugünkü konumunda kalır. Gizlilik metninde konum değişmez. | europe-west1 Hosting rewrite listesinde var ve "en iyi performans" listesinde. Önerilen eşleşme: Cloud Run **europe-west1**. |
| nam5 (us-central1 + us-central2) | us-east4 ile bölgeler arası, ABD içi | Veri ABD'ye taşınır. Yurt dışı aktarım metni güncellenir. | Çok bölgeli dayanıklılık |
| us-east4 (tek bölge) | Cloud Run ile aynı bölge | Veri ABD'ye taşınır | Tek bölge, daha düşük dayanıklılık |

Kaynaklar:

- Firestore konumları ve konumun sonradan değiştirilemeyeceği: https://cloud.google.com/firestore/docs/locations
- Hosting rewrite bölgeleri: https://firebase.google.com/docs/hosting/cloud-run

## 1. Yedek

| # | Komut | Sınıf / onay | Beklenen / doğrulama | Geri dönüş |
| --- | --- | --- | --- | --- |
| 1.1 | `gcloud firestore databases describe --database="(default)" --project=$SRC --format="value(pointInTimeRecoveryEnablement,locationId)"` | [R] | Denetimdeki değer: `POINT_IN_TIME_RECOVERY_DISABLED eur3`. Çıktı kayda geçirilir. | — |
| 1.2 | `gcloud storage buckets create gs://$SRC-migration-backup --location=EU --uniform-bucket-level-access --project=$SRC` | [W] onay | Bucket oluşur. Belgeye göre bucket "veritabanı konumuna yakın" olmalı; eur3 için EU çok bölgeli bucket. | `gcloud storage rm -r gs://$SRC-migration-backup` [W] |
| 1.3 | `gcloud firestore export gs://$SRC-migration-backup/$(date +%Y%m%dT%H%M) --database="(default)" --project=$SRC` | [W] onay, ücretli | `gcloud firestore operations list --project=$SRC` [R] ile `SUCCESSFUL` görülür | Dışa aktarım veriyi değiştirmez |
| 1.4 | K1(b)/(c) ise: `firebase auth:export auth-$SRC.json --format=json --project $SRC` | [S]/[W] **yalnız Erdem**, şifreli diskte | Dosya repoya ve paylaşılan dizinlere girmez. İşlemden sonra güvenli silinir. | — |
| 1.5 | `gcloud run services describe teacherai-api --region=us-east4 --project=$SRC --format="value(status.latestReadyRevisionName)"` | [R] | Bugün: `teacherai-api-00055-78x`. Kaydedilir. | — |
| 1.6 | `firebase hosting:channel:list --project $DST` | [R] | Canlı sürüm zamanı kaydedilir (bugün 2026-09-01 19:31) | Hosting geri alma Console'daki "Release history" ile |

## 2. Hedef hazırlığı ([W], onaylı, ücretli)

| # | Komut | Doğrulama | Geri dönüş |
| --- | --- | --- | --- |
| 2.1 | Billing hesabını DST'ye bağla (Console → Billing) ve bütçe uyarılarını kur: aylık bütçe, %50 / %90 / %100 e-posta | `gcloud billing projects describe $DST` [R] → `billingEnabled: true` | Billing bağlantısını kaldır |
| 2.2 | `gcloud services enable run.googleapis.com firestore.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com iam.googleapis.com --project=$DST` | `gcloud services list --enabled --project=$DST` [R] | `gcloud services disable …` |
| 2.3 | `gcloud firestore databases create --database="(default)" --location=$DB_LOCATION --type=firestore-native --project=$DST` | `gcloud firestore databases list --project=$DST` [R]. **Konum kalıcıdır.** | Veritabanı silinebilir ama aynı ad bir süre kullanılamaz |
| 2.4 | `gcloud artifacts repositories create teacherai --repository-format=docker --location=$REGION --project=$DST` | `gcloud artifacts repositories list --project=$DST` [R] | `… repositories delete teacherai` |
| 2.5 | Yeni bir OpenAI projesi ve harcama limiti oluştur (OpenAI Console). Ardından `printf %s "$NEW_KEY" \| gcloud secrets create openai-api-key --data-file=- --replication-policy=automatic --project=$DST`. Anahtar SRC'den **kopyalanmaz**. | `gcloud secrets versions list openai-api-key --project=$DST` [R] → 1 etkin | Sürümü devre dışı bırak. OpenAI anahtarını iptal et. |
| 2.6 | `gcloud iam service-accounts create teacherai-api-runtime --project=$DST` ve gerekli rollerin bağlanması (aşağıdaki tablo) | `gcloud projects get-iam-policy $DST` [R] | Hesabı veya bağları sil |
| 2.7 | Cloud Run servisi: `scripts/deploy-production.ps1` adım 6–7 (ayar eşliği tablosu aşağıda) | `gcloud run services describe teacherai-api --region=$REGION --project=$DST` [R] | `gcloud run services delete` |
| 2.8 | Kurallar, indeksler ve TTL: `firebase deploy --only firestore --project $DST` | `gcloud firestore indexes composite list` ve `gcloud firestore fields ttls list --project=$DST` [R]. Beklenen: 1 bileşik indeks, 6 TTL. | Önceki kural sürümüne Console'dan dön |
| 2.9 | App Check: API etkinleştirme, web uygulaması kaydı, reCAPTCHA Enterprise anahtarı. Önce `TEACHERAI_APP_CHECK_MODE=monitor`. | Günlükte doğrulama oranı | Modu `off` yap |
| 2.10 | K1(b) ise DST'de bir web uygulaması oluştur (`firebase apps:create WEB "TeacherAI Web" --project $DST`). Auth sağlayıcılarını (e-posta/parola, Google), yetkili alan adlarını ve e-posta şablonlarını yeniden yapılandır. | `firebase apps:sdkconfig` [R] → `authDomain: $DST.firebaseapp.com` | Uygulamayı sil |

### 2.6: çalışma zamanı hesabının rolleri

Aşağıdaki roller kodun yaptığı işlerden çıkarıldı. **Resmî rol belgeleriyle doğrulanmadı.** Bağlamadan önce doğrulanmalı.

Resmî olarak doğrulanan tek şey şudur: Google varsayılan Compute hesabını değil, kullanıcı tarafından yönetilen bir hesabı önerir ve otomatik Editor rolünün kaldırılmasını "kuvvetle" önerir (https://cloud.google.com/run/docs/securing/service-identity). Bugün SRC'de varsayılan hesap **Editor** rolündedir.

| Rol | Neden |
| --- | --- |
| `roles/datastore.user` | Firestore okuma, yazma ve işlemler |
| `roles/secretmanager.secretAccessor` (yalnız `openai-api-key` üzerinde) | `--set-secrets` |
| `roles/firebaseauth.admin` | Hesap silme ve token iptali (`FirebaseIdentity.delete/revoke`), `check_revoked=True` doğrulaması |

### 2.7: Cloud Run ayar eşliği

| Ayar | Eski (SRC, denetim) | Yeni (DST) |
| --- | --- | --- |
| Bölge | us-east4 | K2'ye göre (öneri: eur3 seçilirse europe-west1) |
| min / max instance | 0 / 20 | 0 / **20 (açık `--max-instances`)** |
| Eşzamanlılık, zaman aşımı, CPU, bellek | 80, 300 sn, 1, 512Mi | aynı |
| Ingress, `allUsers` invoker | all, evet | aynı (kimlik uygulama içinde doğrulanır) |
| Hizmet hesabı | varsayılan Compute (Editor) | `teacherai-api-runtime` (en az yetki) |
| `TEACHERAI_ENVIRONMENT` | **tanımsız (development)** | `production` (artık Cloud Run'da zorunlu) |
| Firebase proje kimlikleri | tanımsız (koddaki varsayılan) | `TEACHERAI_FIREBASE_PROJECT_ID` = `TEACHERAI_FIREBASE_AUTH_PROJECT_ID` = $DST (eşitlik zorunlu) |
| Secret | `OPENAI_API_KEY ← openai-api-key:latest` | aynı ad, **yeni anahtar** |
| Geri bildirim e-posta değişkenleri | var | Erdem karar verir (Resend anahtarı DST'de yok) |

Bölge değişirse `firebase.json` içindeki `run.region` ve `deploy-production.ps1` içindeki `$Region` birlikte değiştirilir. Sözleşme testi ikisini aynı tutar.

## 3. Prova

1. **[W]** Anlık görüntüyü kopyala. Önce kuru koşu:
   ```
   python -m scripts.migration.copy_firestore --source $SRC --target $DST
   ```
   Sonra gerçek kopya:
   ```
   python -m scripts.migration.copy_firestore --execute --source $SRC --target $DST --confirm-target $DST
   ```
2. **[R]** Doğrula:
   ```
   python -m scripts.migration.copy_firestore --verify --source $SRC --target $DST --auth-uids target
   ```
   Beklenen: her koleksiyonda `missing: 0` ve `different: 0`. Sahiplik satırlarında `owner_missing` K1 koluna göre değerlendirilir. K1(b)'de Auth içe aktarımından önce `owner_missing` olması beklenir.
3. **[W, onaylı]** Önizleme kanalında yeni web build'i: `NEXT_PUBLIC_API_BASE_URL=<DST Cloud Run URL>/api/v1` ve DST web yapılandırmasıyla `npm run build:web`, ardından `firebase hosting:channel:deploy ta005-prova --expires 3d --project $DST`. Önizleme alan adı CORS listesine geçici olarak eklenir.
4. **Duman testleri** (önizleme kanalında, test hesabıyla): giriş, foto analiz, ders, etkileşim, paylaşım (`/s/…` rewrite), hesap silme ve makbuz sorgusu, kota sınırı.
5. Gerekirse prova verisini sil: yalnız DST'de, `copy_firestore --verify` sayılarıyla eşleşen test belgeleri.

## 4. Kontrollü geçiş

| # | Adım | Sınıf | Doğrulama |
| --- | --- | --- | --- |
| 4.1 | Duyuru (zaman penceresi, beklenen kesinti: yazma kapalı ~30 dk) | — | — |
| 4.2 | Eski serviste salt okunur mod: `gcloud run services update teacherai-api --region=us-east4 --project=$SRC --update-env-vars TEACHERAI_MAINTENANCE_MODE=read_only` | [W] | `POST` istekleri 503 + `Retry-After` döner. Web bakım mesajı gösterir. |
| 4.3 | K1(b): `firebase auth:import auth-$SRC.json --hash-algo=SCRYPT --hash-key=<…> --salt-separator=<…> --rounds=<…> --mem-cost=<…> --project $DST`. Parametreler SRC Console → Authentication → kullanıcı menüsü → "Password hash parameters" ekranından alınır ve repoya girmez. | [W] yalnız Erdem | Kullanıcı sayısı eşit. UID'ler korunur. Token iptal zamanları **taşınmaz**, kullanıcılar yeniden oturum açar. |
| 4.4 | Son fark kopyası `--execute` ve ardından `--verify` | [W] / [R] | `missing: 0`, `different: 0`, `owner_missing: 0` |
| 4.5 | Yeni web build'i (DST API URL'si ve DST web yapılandırması) ve `firebase deploy --only hosting --project $DST` | [W] | `/s/<id>` 200 döner, adres Hosting'de kalır |
| 4.6 | Yeni serviste yazmayı aç (`TEACHERAI_MAINTENANCE_MODE=off`, varsayılan) | [W] | Yeni ders kaydı DST'de |
| 4.7 | İzleme (ilk 24 saat): 5xx oranı, p95 gecikme, `ai_global_budget_exhausted` / `usage_limit` hataları, `account_deletion` sonuçları | [R] | Cloud Run metrikleri ve günlükler |

**Kota etkisi:** `ai_daily_usage`, `ai_output_usage` ve `ai_global_usage` kopyalandığı için günün kotası sıfırlanmaz. Bu koleksiyonlar kopyalanmazsa bütün kullanıcıların o günkü kotası ve küresel bütçe sıfırlanır.

## 5. Geri alma

- **Son karar zamanı:** 4.6'dan sonraki **24 saat**. Bu süreden sonra geri alma yalnız fark geri kopyasıyla yapılır.
- **Yazma açılmadan önce (4.6'dan önce):**
  1. DST Hosting'i önceki sürüme döndür (Console → Release history → Rollback).
  2. Eski serviste `TEACHERAI_MAINTENANCE_MODE=off` yap.
  Veri kaybı olmaz.
- **Yazma açıldıktan sonra:**
  1. Yeni serviste `read_only` modunu aç.
  2. Farkı geri kopyala:
     ```
     python -m scripts.migration.copy_firestore --execute --source $DST --target $SRC --confirm-target $SRC --allow-reverse
     ```
  3. `--verify` ile denetle.
  4. Hosting'i geri al ve eski serviste yazmayı aç.

  K1(b)'de DST'de yeni oluşan Auth hesapları SRC'ye otomatik dönmez. Bu hesaplar için ayrı bir dışa/içe aktarım gerekir.

## 6. Eski projenin emekliye ayrılması

1. **[W]** Eski servisi yönlendirme moduna al:
   ```
   gcloud run services update teacherai-api --region=us-east4 --project=$SRC \
     --update-env-vars TEACHERAI_MAINTENANCE_MODE=redirect,TEACHERAI_LEGACY_REDIRECT_BASE=https://teacherai-07.web.app \
     --min-instances 0
   ```
   Servis en az 30 gün bu modda kalır. run.app `/s/…` bağlantıları 301 ile Hosting'e gider.
2. **[W]** `math-ai-07.web.app` sitesi bugün 404 döndürüyor. 25–26 Ağustos'tan kalan `/s/…` bağlantıları için bu siteye `"redirects": [{"source": "/s/:id", "destination": "https://teacherai-07.web.app/s/:id", "type": 301}]` içeren tek kurallı bir yönlendirme sürümü dağıtılır.
3. **[W]** App Hosting backend'leri (`my-web-app`, `math-ai`) kullanılmıyorsa silinir.
4. **[W, ayrı açık onay]** Proje silme: `gcloud projects delete $SRC`. Runbook yalnız komutu yazar. Önce 30 günlük yönlendirme süresi ve dışa aktarım saklama süresi dolmalıdır.

## 7. KVKK ve gizlilik metni

Veri konumu değişirse (`docs/privacy/gizlilik-metni-taslak.md`) şunlar güncellenir:

- Verinin işlendiği ve saklandığı ülke ve bölge
- Yurt dışına aktarım dayanağı
- Alt işleyenler: Google Cloud ve Firebase bölgeleri
- Saklama süreleri (değişmez)
- Hesap silmenin yeni projede çalıştığı bilgisi

K1(b)'de kullanıcılara yeniden giriş gerekeceği duyurulur. Hukuki değerlendirme Erdem'e aittir.
