# ADR TA-005C: Sağlayıcı tamamlama, şema izdüşümü, muhasebe kapsamı, dağıtım ve geçiş güvenliği

Durum: kabul edildi (kod). Canlı ortamda hiçbir ayar değişmedi. Varsayılan sağlayıcı her işlemde `openai`'dir. Anthropic Vision production'da kapalıdır. Gerçek sağlayıcı çağrısı yapılmadı.

Bu ADR, [ADR TA-005B](adr-ta-005b-provider-gateway.md)'yi tamamlar. Bilimsel bilgi mimarisi ayrı bir kayıttadır: [ADR TA-006/007 hazırlığı](adr-ta-006-scientific-knowledge-architecture.md).

## 1. Üç işlem de Anthropic'te desteklenir

| İşlem | OpenAI | Anthropic | Anthropic koşulu |
| --- | --- | --- | --- |
| Vision (ilk okuma + hedefli yeniden okuma) | varsayılan | evet | `TEACHERAI_PROVIDER_VISION=anthropic`, `TEACHERAI_ANTHROPIC_VISION_MODEL`, `ANTHROPIC_API_KEY` **ve** `TEACHERAI_ALLOW_STUDENT_IMAGES_TO_ANTHROPIC=true` |
| Ders | varsayılan | evet | `TEACHERAI_PROVIDER_LESSON=anthropic`, `TEACHERAI_ANTHROPIC_LESSON_MODEL`, anahtar |
| Etkileşim | varsayılan | evet | `TEACHERAI_PROVIDER_INTERACTION=anthropic`, `TEACHERAI_ANTHROPIC_INTERACTION_MODEL`, anahtar |

Her sağlayıcı aynı yolları paylaşır:

- aynı istem, ders bağlamı ve ön işlenmiş görsel
- aynı geçit: kota, bütçe, tavan, rezervasyon, geçiş belgesi, şema doğrulaması
- aynı Question Integrity, AnswerTarget, MathAI, yöntem denetimi ve kalıcı yazma sınırları

Ayrı bir sağlayıcıya özgü eğitim hattı yoktur. Anthropic sınıfları (`AnthropicVisionProvider`, `AnthropicLessonProvider`, `AnthropicInteractionProvider`) OpenAI sınıflarından yalnız adaptörü ve hata eşlemesini değiştirir.

Fallback yoktur. Bir sağlayıcı hata verirse diğerine geçilmez. Bu, testle gösterildi: Anthropic 529 → `ProviderRateLimitError`, tek HTTP isteği, OpenAI istemcisi hiç açılmadı.

Başlangıçta katalog denetimleri de çalışır:

- Katalogdaki model başka sağlayıcıya aitse uygulama başlamaz (ör. `TEACHERAI_ANTHROPIC_VISION_MODEL=gpt-4.1-mini`).
- Katalogda işlemin gerektirdiği yetenek açıkça `false` ise uygulama başlamaz.
- Production'da yeteneği doğrulanmamış (`null`) model reddedilir.

## 2. Anthropic'e özgü şema izdüşümü

Resmî belge (structured outputs, 24 Kasım 2026'da yeniden okundu) `minimum`, `maximum`, `multipleOf`, `minLength`, `maxLength` desteklemez. Desteklenmeyen özellik 400 döndürür. Aynı belge SDK yardımcılarının dönüşümünü şöyle tarif eder: kısıtı çıkar, açıklamaya ekle, yanıtı özgün şemaya göre doğrula.

TeacherAI resmî SDK'yı kullanmaz (TA-005B: tek POST, yeni bağımlılık yok). Aynı dönüşüm `core/schema_compat.anthropic_projection` ile, dar bir onay listesiyle yapılır.

| Model | Gönderilen şemadan çıkarılan | Sunucuda uygulayan (değişmedi) |
| --- | --- | --- |
| `VisionProviderAnalysis` | `#/properties/confidence` `minimum: 0` | `confidence: Field(ge=0)` |
| `VisionProviderAnalysis` | `#/properties/confidence` `maximum: 1` | `confidence: Field(le=1)` |
| `VisionProviderAnalysis` | `#/$defs/SourceProposal/properties/question_count` `minimum: 0` | `SourceProposal.question_count: Field(ge=0)` |
| `AdaptiveDraft` | `#/$defs/Expression/properties/latex` `minLength: 1` | `Expression.latex: Field(min_length=1)` |
| `RecheckResponse`, `LessonDraftResponse` | hiçbiri (zaten uyumlu) | — |

Çıkarılan her kısıt alanın `description`'ına yazılır (ör. `{minimum: 0, maximum: 1}`). Geçit yanıtı her zaman özgün Pydantic modeliyle doğrular.

Kurallar:

- Yalnız sayı ve dize sınırları izdüşümle giderilebilir. `oneOf`, özyineleme, dizi sınırı, `additionalProperties`, regex ve `allOf` sorunları giderilemez; o şema gönderilmez.
- Onay listesinde olmayan bir çıkarma, şemada artık bulunmayan bir onay satırı veya izdüşümden sonra kalan uyumsuzluk `SchemaProjectionError` verir. Hata ağdan önce gelir. CI'daki `python -m scripts.anthropic_schema_compat --check` aynı nedenle kırılır.
- Yeni bir Pydantic kısıtı eklenirse şema Anthropic'e gönderilmez. Bu ADR'ye bir satır eklenmeden çalışmaz.

Sınanan geçersiz yanıtlar şunlardır:

- aralık dışı `confidence` (1,5 ve −0,1)
- negatif `question_count`
- boş `latex`
- eksik alan
- geçersiz enum
- ek alan
- bozuk iç içe nesne
- sağlayıcının gönderdiği `revision` (sunucuya ait)
- geçersiz bölge türü
- alanlar arası kural ihlali

Hepsi `ai_invalid_output` olur. Kabul edilen yanıttaki sıralı olmayan veya 0–1 dışı bölge, `SourceRegion` tarafından atılır ve kaynak sayılmaz.

## 3. Hata sınıflandırması

Kaynaklar 24 Kasım 2026'da okundu: https://platform.claude.com/docs/en/api/errors, …/build-with-claude/context-windows, …/handling-stop-reasons.

| HTTP / durum | `error.type` | Kanonik neden (`ProviderFailure`) | Vision | Ders | Etkileşim |
| --- | --- | --- | --- | --- | --- |
| 401 | authentication_error | `authentication` | 503 `provider_not_configured` | 503 `lesson_provider_not_configured` | 503 `interaction_provider_unavailable` |
| 402 / 403 / 404 | billing / permission / not_found | `billing` / `permission` / `model_not_found` | aynı | aynı | aynı |
| 400 | invalid_request_error, "prompt is too long" | `context_window_exceeded` | 502 `invalid_provider_response` | **tek acil bağlam denemesi**, sonra 422 `lesson_context_too_large` | **tek acil bağlam denemesi**, sonra 422 `interaction_context_too_large` |
| 400 | invalid_request_error (diğer) | `invalid_request` | 502 `invalid_provider_response` | 502 `invalid_lesson_plan` | 502 `invalid_interaction_response` |
| 413 | request_too_large | `request_too_large` | 502 | 502 | 502 |
| 429 | rate_limit_error | `rate_limited` | 503 `provider_unavailable` | 503 `lesson_provider_unavailable` | 503 |
| 529 | overloaded_error | `overloaded` | 503 | 503 | 503 |
| 500 | api_error | `provider_internal` | 503 | 503 | 503 |
| 504 veya 500 + timeout_error | timeout_error | `provider_timeout` | 504 `provider_timeout` | 504 `lesson_timeout` | 503 |
| bağlantı hatası | — | `connection` | 503 | 503 | 503 |
| istemci zaman aşımı | — | sonuç `timeout` | 504 `ai_timeout` | 504 `ai_timeout` | 504 `ai_timeout` |
| `stop_reason: refusal` | — | sonuç `refusal` | 422 `ai_refused` | aynı | aynı |
| `max_tokens` veya `model_context_window_exceeded` | — | sonuç `incomplete_max_tokens` | 502 `ai_output_truncated` | aynı | aynı |
| `tool_use`, `pause_turn`, `stop_sequence`, eksik | — | `unexpected_stop` | 503 | 502 `ai_provider_error` | 503 |
| bilinmeyen | — | `unknown` | 503 | 502 `ai_provider_error` | 503 |

Notlar:

- `model_context_window_exceeded`, TA-005B'de `incomplete_other` idi. Belge "yanıtı kesilmiş say" dediği için kesilme sınıfına alındı.
- Hata gövdesinden yalnız `error.type` okunur. `error.message` yalnız belgelenmiş "prompt is too long" ifadesi için okunur ve hiçbir yere yazılmaz.
- Anahtar, istem, görsel ve hata mesajı günlüğe girmez. Bunu sınayan bir test vardır.
- Bağlam yeniden denemesi yalnız sınıflanmış bağlam aşımında ve mantıksal istek tavanında hak kaldıysa yapılır. Deneme geçitte sayılır. Gizli SDK yeniden denemesi yoktur: SDK kullanılmaz ve her HTTP isteği bir çağrıdır.
- Varsayılan etkileşim tavanı `TEACHERAI_INTERACTION_MAX_PROVIDER_CALLS=1`'dir. Bu yüzden varsayılan ayarla etkileşimde bağlam denemesi yapılmaz; doğrudan 422 `interaction_context_too_large` döner. Tavan yükseltilmedi. Ders tavanı (3) ilk çağrı, düzeltme ve bağlam denemesini birlikte kapsar.
- HTTP hatasında kullanım bilinmediği için rezervasyon korunur. Bu, TA-005B'deki OpenAI yolu ile aynıdır ve muhafazakârdır.

## 4. Muhasebe kapsamı zorunludur

TA-005B'de kapsam yoksa geçit sağlayıcıyı rezervasyonsuz ve tavansız çağırabiliyordu. TA-005C'de üç kural geçerlidir:

| Kapsam | Kim açar | Rezervasyon | Tavan | Ortam |
| --- | --- | --- | --- | --- |
| yok | — | — | çağrı `AccountingScopeRequired` ile reddedilir; adaptöre gidilmez; `ai_call_refused` günlüğü | her yer |
| `begin_accounting` (production) | `core/admission.py` (kimlik, kota, idempotency, hesap silme denetiminden sonra) | kullanıcı + küresel, her çağrıdan önce | `max_calls` ya da işlemin `provider_call_budget` değeri; asla sınırsız değil | her yer |
| `begin_offline_accounting` (değerlendirme/test) | `scripts/evaluate_models.py`, `scripts/eval_pack.py`, test fikstürü | yok (kullanıcı kotası yok) | zorunlu `max_calls`; isteğe bağlı `max_usd` | production/staging ve `K_SERVICE` varken **açılamaz** |

Offline USD tavanı tahminidir ve kesin bir harcama sınırı değildir. Maliyeti bilinmeyen bir çağrı (fiyatsız model veya eksik kullanım) sonraki çağrıyı durdurur; sıfır sayılmaz.

Uzlaştırma kuralları değişmedi ve testle gösterildi:

- Başarı, ret ve kesilmede kullanılmayan pay bir kez iade edilir.
- Zaman aşımında ve bilinmeyen kullanımda rezervasyon korunur.
- Fiyat yalnız üç kullanım alanı da biliniyorsa hesaplanır.

## 5. Dağıtımda ortam uzlaştırması ve Firebase web doğrulaması

`gcloud run deploy --set-env-vars/--set-secrets` servisin ortamını tümüyle değiştirir. TA-005B planı her Update'te yalnız 4 yönetilen değişkeni ve OpenAI secret'ını yazıyordu. Diğer bütün ayarlar silinecekti: model atamaları, bakım modu, bütçeler, App Check, geri bildirim, MathAI sınırları, Anthropic/Resend secret'ları.

Karar: açık yönetilen yapılandırma ve belgelenmiş uzlaştırma politikası (`scripts/deploy-production.json` → `runtime_env_policy`).

| Sınıf | Davranış |
| --- | --- |
| Yönetilen (4) | Betik yazar; eski değer farklıysa raporda `managed_changed` |
| `preserve_env` (50 ad) | Çalışan servisten aynen taşınır. Her ad `Settings`'te veya MathAI'de gerçekten okunan bir ayardır (testle denetlenir). |
| `preserve_secrets` (`ANTHROPIC_API_KEY`, `RESEND_API_KEY`) | Secret referansı (ad:sürüm) taşınır; değer okunmaz |
| `prohibited_env` | Düz metin anahtar, hizmet hesabı JSON'u, `TEACHERAI_DEBUG`: değişiklikten önce durdurur |
| Politikada olmayan ad | Ne korunur ne silinir: değişiklikten önce durdurur. Kaldırma yalnız `--drop-env AD` (`-DropEnv`). |

Değerler yazdırılmaz; rapor yalnız ad taşır. Virgüllü değerlerde gcloud'un `^ayraç^` sözdizimi kullanılır.

Firebase web yapılandırması iki düzeyde denetlenir.

- **Çevrimdışı (plan ve execute):**
  - `PROJECT_ID` hedefle aynı
  - `AUTH_DOMAIN` hedefin `firebaseapp.com`/`web.app` alanı veya `approved_auth_domains` listesinde
  - `APP_ID` web biçiminde
  - `API_KEY` biçimi
  - varsa `MESSAGING_SENDER_ID`'nin `APP_ID`'deki proje numarasıyla eşliği
  - varsa `STORAGE_BUCKET` hedefin kovası
- **Gerçek (yalnız `--execute`, değişiklikten önce, yalnız okuma):**
  - `firebase apps:list WEB --project teacherai-07 --json` içinde `APP_ID` bulunmalı
  - `firebase apps:sdkconfig WEB <APP_ID> --json` sonucundaki `sdkConfig` ile web paketindeki her alan eşleşmeli
  - CLI uygulamayı `projects/-` jokeriyle okuduğu için (firebase-tools 15.31.0 kaynağında doğrulandı) dönen `projectId` ayrıca denetlenir

Plan çıktısı yalnız çevrimdışı denetim yapıldığını açıkça yazar. Web build'den önce yapılandırmanın doğrulamadan beri değişmediği denetlenir.

Tutarlılık denetimleri:

- Cloud Run'a giden her Hosting rewrite'ı aynı servis ve bölgeyi gösterir.
- `.firebaserc` varsayılanı hedef projedir.
- `cloudbuild.api.yaml` image yolu `${_REGION}-docker.pkg.dev/$PROJECT_ID/teacherai/teacherai-api`'dir.

Firestore konumu ve Cloud Run bölgesi (K2) hâlâ karar bekler: `region: null`.

## 6. Geçişte eşzamanlılık ve çakışma

- Her yazma ve budama silmesi hedef belgeyi aynı Firestore işleminde yeniden okur. Yalnız karar anındaki özet hâlâ geçerliyse uygular. Yeni belgede beklenen durum "yok"tur.
- Kaynak belge yazmadan hemen önce yeniden okunur.
- Projeler arası tek işlem mümkün değildir. Kaynak tarafı için iki projenin `read_only` modunda olması gerekir (runbook ön koşulu 2).
- Budama manifesti tek başına eşzamanlı değişikliğe karşı koruma **sağlamaz**. Korumayı işlem içi yeniden okuma sağlar.
- Beklenmeyen çakışma kendiliğinden ezilmez. Ezme yalnız `--overwrite-from` raporundaki aynı hedef ve kaynak özetiyle yapılır. Rapordan sonra değişen hedef belge onaysız sayılır ve görünür kalır.
- Yetim alt koleksiyonlar `list_documents` (show_missing) ile bulunur (`orphan_parent`). Sahip bilgisi üst belgedeyse alt belgeler yazılmaz.
- İki tarafta sahibi farklı belge (`owner_mismatch`) hiçbir yöne yazılmaz. Silinmiş sahip her iki tarafta da önceliklidir.

## 7. MathAI hata sınıfları

`mathai_busy` (kuyruk dolu veya bekleme aşıldı, `Retry-After: 2`), `mathai_startup_timeout`, `mathai_timeout`, `mathai_error`.

Başlatma ile hesaplama arasındaki ayrım, worker'ın içe aktarmadan sonra yazdığı hazır satırına dayanır. Toplam sınır (8 sn) ve süreç izolasyonu değişmedi. Havuz yoktur (TA-005B §6). Cloud Run CPU ve eşzamanlılık önerisi hâlâ yük testi bekleyen bir hipotezdir.

## Reddedilenler

- Kısıtları sessizce atmak veya Pydantic modelini gevşetmek.
- Resmî Anthropic SDK'yı eklemek: gizli yeniden denemesi (varsayılan 2) çağrı tavanını delerdi ve yeni bağımlılık zinciri getirirdi.
- Testlerde kapsamsız çağrıya izin vermek: test fikstürü açık bir offline kapsam açar; kapsamsız ret ayrıca test edilir.
- Update'te bilinmeyen ayarı korumak veya silmek: ikisi de sessiz karar olurdu; dağıtım durur.
- Budama manifestini tek güvence saymak.
