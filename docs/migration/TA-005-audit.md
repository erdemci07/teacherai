# TA-005 canlı proje denetimi: math-ai-07 → teacherai-07

Tarih: 21 Kasım 2026. Bütün komutlar **[R] salt okunur** sınıfındaydı ve `--project` bayrağı açıkça verildi. Yerel gcloud/firebase varsayılanları değiştirilmedi. Kaynak oluşturulmadı, API etkinleştirilmedi. gcloud'un "API'yi etkinleştireyim mi?" istemi etkileşimsiz ortamda `N` ile geçti. Betikte `CLOUDSDK_CORE_DISABLE_PROMPTS=1` kullanılır ve izin listesi dışındaki her gcloud fiili kod düzeyinde reddedilir.

Bu belgede kişisel veri, UID, e-posta veya gizli değer yoktur. Kişisel hesaplar `user:<user-1>` biçiminde maskelenmiştir.

## Kapsam ve eksik kalan kısım

`scripts/migration/audit_projects.py` yazıldı ve saf özet fonksiyonları birim testlidir. Ancak oturumdaki otomatik izin denetleyicisi, betiğin canlı Auth kullanıcı listesine ve Firestore belgelerine erişen **tam çalıştırmasını reddetti**. Bu yüzden aşağıdaki veriler **doğrulanamadı**:

- Auth kullanıcı sayıları, sağlayıcı dağılımı, oluşturulma aralığı ve iki projedeki UID kesişimi
- Auth oturum açma yöntemleri ve yetkili alan adları
- Firestore koleksiyon adları, belge sayıları, değer türleri ve sahip UID eşlemesi
- Canlı güvenlik kurallarının `firestore.rules` ile farkı

Bu kısmı Erdem kendi oturumuyla çalıştırmalıdır. Betik çıktıyı ayrı bir dosyaya yazar:

```
[R] gcloud auth application-default login          # Erdem çalıştırır; yalnız yerel kimlik dosyası oluşturur
[R] python -m scripts.migration.audit_projects --source math-ai-07 --target teacherai-07 \
        --output docs/migration/TA-005-audit-live.md
```

Belgenin geri kalanı, tek tek çalıştırılan meta veri komutlarına dayanır.

## 1. Proje

| | math-ai-07 | teacherai-07 |
| --- | --- | --- |
| Proje numarası | 584518659954 | 441839517163 |
| Oluşturulma | 2026-08-19 | 2026-08-26 |
| Billing | etkin (Blaze) | **kapalı (Spark)** |
| Etkin API sayısı | 59 | 36 |

Yalnız math-ai-07'de etkin olan ve taşıma için gereken API'ler şunlardır: `run`, `firestore`, `secretmanager`, `artifactregistry`, `cloudbuild`, `iam`, `iamcredentials`. Bunlara ek olarak App Hosting, Developer Connect ve Gemini Cloud Assist gibi gerekmeyenler de etkindir. `firebaseappcheck` iki projede de etkin değil.

Komutlar: `gcloud projects describe <p>`, `gcloud billing projects describe <p>`, `gcloud services list --enabled --project=<p>`.

## 2. Auth

| Kanıt | Sonuç |
| --- | --- |
| Firebase web uygulamaları (`firebase apps:list`) | math-ai-07: "math-ai" ve "TeacherAI Web". teacherai-07: **hiç uygulama yok**. |
| Web uygulamalarının `authDomain` / `projectId` değeri (`firebase apps:sdkconfig`, yalnız bu iki alan) | İkisinde de `math-ai-07.firebaseapp.com` / `math-ai-07` |
| Canlı API'nin token doğrulama projesi | Cloud Run'da `TEACHERAI_FIREBASE_PROJECT_ID` ve `TEACHERAI_FIREBASE_AUTH_PROJECT_ID` tanımlı değil. Bu durumda koddaki varsayılan `math-ai-07` kullanılır (`settings.py`, `container.py`). |
| teacherai-07 Identity Toolkit | API etkin. Web uygulaması olmadığı için istemci SDK'sıyla kullanıcı oluşmuş olması beklenmez. **Sayı doğrulanamadı.** |
| Kullanıcı sayıları, sağlayıcılar, UID kesişimi | **Doğrulanamadı** (yukarıdaki izin reddi) |

## 3. Web yapılandırması

`https://teacherai-07.web.app` canlı paketi herkese açık GET ile incelendi. Son sürüm 1 Eylül 2026 tarihli.

- API adresi `https://teacherai-api-n75p6jbera-uk.a.run.app/api/v1` olarak gömülü. Bu, math-ai-07'deki Cloud Run adresidir.
- Firebase yapılandırması **gömülü değil**. Pakette `NEXT_PUBLIC_FIREBASE_*` değerleri yerine `process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID` başvuruları kalmış. Build sırasında bu değişkenler verilmemiş. İstemci kodu dört değerin hepsi doluysa Firebase'i başlatır (`Object.values(n).every(Boolean)`). Bu nedenle **canlı sitede oturum açma büyük olasılıkla devre dışıdır.** Tarayıcıda doğrulanmadı.
- App Check site anahtarı: pakette yok. `firebaseappcheck` API'si iki projede de etkin değil, yani kayıt yok.
- Depoda yerel `apps/web/.env*` dosyası yok. Bu yüzden build'in hangi değerlerle yapılacağı repodan doğrulanamaz.

## 4. Firestore

| | math-ai-07 | teacherai-07 |
| --- | --- | --- |
| Veritabanı | `(default)`, FIRESTORE_NATIVE, STANDARD | **yok** (API etkin değil) |
| Konum | **eur3** (Avrupa çok bölgeli) | — |
| Eşzamanlılık | PESSIMISTIC | — |
| PITR | kapalı | — |
| Silme koruması | kapalı | — |
| Yedek planı / yedek | yok / yok | — |
| Bileşik indeks | **0** (repoda 1: `lessons(student_id ASC, created_at DESC)`) | — |
| TTL politikası | **0** (repoda 6) | — |

Cloud Run us-east4'te, Firestore eur3'te çalışıyor. Her Firestore işlemi Atlantik'i geçiyor.

Repodaki indeks ve TTL tanımları hiç yayımlanmamış. TA-001B'den beri açık olan "indeks ve TTL yayımı" maddesi doğrulandı. Geçmiş listesi sorgusunun bileşik indeks olmadan canlıda çalışıp çalışmadığı denetlenmedi.

Koleksiyonlar, belge sayıları ve canlı kurallar **doğrulanamadı.** Kod tarafındaki koleksiyonlar ve sahip alanları şunlardır:

| Koleksiyon | Sahip | TTL |
| --- | --- | --- |
| users, student_profiles, student_memories, account_deletions | belge kimliği = UID | account_deletions 30 gün |
| lessons, practice_questions, practice_attempts, interaction_events | `student_id` | practice_questions 7 gün |
| shared_solutions | `owner_id` (eski kayıtlarda yok) | — |
| feedback | `user_id` | — |
| lesson_analyses | `owner` | 1 gün |
| ai_daily_usage, ai_output_usage | `owner_hash` = sha256(UID) | 30 gün |
| ai_global_usage | yok (gün belgesi) | 30 gün |

Kodda alt koleksiyon kullanımı yoktur.

`firestore.rules` dosyası `firebase.json`'da referans verilmediği için repodan hiç yayımlanmamıştır. Canlıda Console'da yazılmış başka kurallar olabilir. Fark, betik çalıştırılınca görülecek.

## 5. Cloud Run (math-ai-07)

| Ayar | Değer |
| --- | --- |
| Servis / bölge | `teacherai-api` / us-east4 |
| Hazır revizyon | `teacherai-api-00055-78x` |
| URL | `https://teacherai-api-n75p6jbera-uk.a.run.app` |
| min / max instance | 0 (varsayılan) / 20 |
| Eşzamanlılık, zaman aşımı | 80, 300 sn |
| CPU, bellek | 1000m, 512Mi |
| Ingress, `allUsers` invoker | `all`, **evet** (herkese açık API; kimlik uygulama içinde doğrulanır) |
| Çalışma zamanı hesabı | `584518659954-compute@developer.gserviceaccount.com`. Bu hesap projede **`roles/editor`** taşıyor. |
| Ortam değişkeni adları | `FEEDBACK_EMAIL_NOTIFICATIONS`, `FEEDBACK_EMAIL_SENDER`, `FEEDBACK_NOTIFICATION_EMAIL`, `OPENAI_LESSON_MODEL` |
| Secret referansları | `OPENAI_API_KEY ← openai-api-key:latest` |

**Önemli:** `TEACHERAI_ENVIRONMENT` tanımlı değil, bu yüzden canlı servis `development` ortamında çalışıyor. `TEACHERAI_APP_CHECK_MODE` da tanımlı değil (`off`). Production'a özgü denetimler (TA-005'te eklenen proje eşitliği dahil) canlıda bugün etkin değil. Yeni serviste `TEACHERAI_ENVIRONMENT=production` zorunlu tutulmalıdır.

## 6. Diğer

| | math-ai-07 | teacherai-07 |
| --- | --- | --- |
| Artifact Registry | `teacherai` (DOCKER, us-east4), `firebaseapphosting-images` | API etkin değil |
| Secret Manager (yalnız ad, sürüm sayısı) | `openai-api-key` (2 etkin sürüm), `RESEND_API_KEY`, `GMAIL_SMTP_APP_PASSWORD`, `firebaseWebApiKey` (son üçünde listelenen sürüm yok) | API etkin değil |
| Bucket'lar | `firebaseapphosting-sources-…-us-east4` (2), `math-ai-07_cloudbuild` (US) | yok |
| Hosting siteleri | `math-ai-07` ("TeacherAI Web" uygulamasına bağlı). Canlı sürüm 2026-08-26, `/` ve `/s/…` **404** dönüyor. | `teacherai-07`, canlı sürüm 2026-09-01. `/s/:id` → run.app'e 302. |
| App Hosting backend'leri | `my-web-app`, `math-ai` (us-east4; ikisinde de ABIU kapalı) | — |
| Özel alan adı | doğrulanamadı (REST ile okunur; betikte) | doğrulanamadı |
| App Check | API etkin değil | API etkin değil |

## 7. IAM (kişisel hesaplar maskeli)

- **math-ai-07:** `roles/owner` → `user:<user-1>`. `roles/editor` → varsayılan Compute hesabı (Cloud Run çalışma zamanı). `roles/firebaseauth.admin` ve `roles/iam.serviceAccountTokenCreator` → `firebase-adminsdk-fbsvc@math-ai-07`. App Hosting hesabının `firebase.sdkAdminServiceAgent`, `storage.objectViewer` ve `developerconnect.readTokenAccessor` rolleri var. Geri kalanlar Google tarafından yönetilen hizmet ajanlarıdır.
- **teacherai-07:** `roles/owner` → `user:<user-1>` (aynı kişi). Bunun dışında yalnız Firebase yönetim ve Admin SDK ajanları var.

## 8. Paylaşım bağlantıları

Paylaşım URL'si `shared_solutions` belgesinde **saklanmaz**. Her yanıtta `public_app_url` değerinden hesaplanır (`ShareService.share_url`). Kod geçmişinde üretilen biçimler şunlardır:

| Dönem (commit) | Üretilen biçim | Bugünkü durumu |
| --- | --- | --- |
| 2026-08-25 `af75777` → 2026-08-26 20:18 `73e72c6` | `https://math-ai-07.web.app/s/{id}` | math-ai-07 sitesi `/s/` için **404** dönüyor; bu bağlantılar bugün kırık |
| 2026-08-26 20:18 `73e72c6` → 23:11 `eb3ac41` | `public_share_url_base`, yoksa isteğin geldiği taban, yani `*.run.app/s/{id}` | run.app servisi doğrudan sunuyor (çalışıyor) |
| 2026-08-26 23:11 `eb3ac41` → bugün | `https://teacherai-07.web.app/s/{id}` | Hosting 302 ile run.app'e yönlendiriyor |

Bu dönemlerin canlıya dağıtılıp dağıtılmadığı ve hangi dönemde kaç paylaşım oluşturulduğu, `shared_solutions.created_at` aralığıyla birlikte betiğin çalıştırılmasıyla görülecek.

## Bulunan durum

- **K1 — Auth nerede? Kol (b), kanıt güçlü; sayılar doğrulanamadı.** Bütün Firebase web uygulamaları ve `authDomain` değeri math-ai-07'dedir. teacherai-07'de web uygulaması yoktur. Canlı API token'ı varsayılan olarak math-ai-07'ye karşı doğrular. teacherai-07'de kullanıcı olmadığı **varsayılmaz**. Kesişim sayısı betikle doğrulanmadan (c) kolu dışlanamaz. Taşıma adımları (b) koluna göre yazılmıştır, (c) için durma koşulu vardır.
- **K2 — teacherai-07'de Firestore var mı? Yok.** API etkin değil, veritabanı yok, konum henüz seçilmedi. Kaynak veritabanı **eur3**'tedir. Karşılaştırma için [runbook §2](TA-005-runbook.md#2-hedef-hazırlığı-w-onaylı) bölümüne bakın. Karar Erdem'indir.
- **K3 — teacherai-07 Blaze planında mı? Hayır, Spark.** `billingEnabled=false`. Cloud Run, Secret Manager ve Artifact Registry için Blaze'e geçmek gerekir. Bu ücretli bir adımdır ve onay ister.
- **K4 — run.app paylaşım bağlantıları dağıtılmış mı? Doğrulanamadı; kod geçmişine göre olası.** Yaklaşık üç saatlik bir pencerede run.app tabanlı bağlantı üretilebiliyordu. Bugünkü bütün bağlantılar da Hosting üzerinden run.app'e 302 ile yönleniyor, yani arama motorları ve önbellekler run.app adresini görmüş olabilir. Eski serviste en az 30 gün `TEACHERAI_LEGACY_REDIRECT_BASE` ile 301 yönlendirmesi tutulmalıdır. Ek bulgu: 25–26 Ağustos'ta üretilmiş olabilecek `math-ai-07.web.app/s/…` bağlantıları bugün zaten kırık. Bunlar için math-ai-07 sitesine bir yönlendirme dağıtımı ayrı bir [W] adımıdır.
