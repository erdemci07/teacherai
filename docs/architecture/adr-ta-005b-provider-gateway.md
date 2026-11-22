# ADR TA-005B: Sağlayıcıdan bağımsız AI geçidi, Anthropic adaptörü ve TA-006 bağlantısı

Durum: kabul edildi (kod). Canlı ortamda hiçbir sağlayıcı ayarı değişmedi; varsayılan sağlayıcı her işlemde `openai`'dir. Gerçek Anthropic çağrısı yapılmadı.

## Bağlam

TA-005'e kadar `core/gateway.py` doğrudan OpenAI Responses gövdesine göre yazılmıştı. Kota, çağrı tavanı, rezervasyon ve günlük kodu, sağlayıcıya özgü sınıflandırmayla aynı fonksiyondaydı. İkinci bir sağlayıcı eklemek bu güvenceleri kopyalamayı gerektiriyordu.

## Kararlar

### 1. Dar port ve ortak katman

`core/ai_port.py` şunları tanımlar:

- **İstek:** işlem, model, sistem metni, kullanıcı içeriği (metin ve görsel parçaları), hedef Pydantic şeması, zaman aşımı. Çıktı sınırı ve reasoning düzeyi ortak katmanda işleme göre doldurulur.
- **Sonuç:** `completed`, `incomplete_max_tokens`, `incomplete_other`, `refusal`, `invalid_output`, `timeout`, `provider_error`.
- **Normalize kullanım:** `input`, `cached_input`, `output`, `reasoning`. Sağlayıcının vermediği alan `None` kalır.

Adaptörün dışında, ortak katmanda kalanlar şunlardır: kota ve idempotency (`core/admission.py`, `core/usage.py`), hesap silme denetimi, küresel bütçe, çağrı tavanı, token rezervasyonu ve iadesi, şema doğrulaması, fiyat ve `ai_usage` günlüğü.

**Atlanamazlık.** `ProviderAdapter.send` yalnız geçidin o istek için ürettiği, tek kullanımlık bir `Admission` ile çalışır. Geçit bu belgeyi çağrı tavanı denetimi ve rezervasyondan **sonra** üretir.

Bunu sınayan testler (`test_provider_config.py`), kayıtlı her adaptör için şunları gösterir:

- belgesiz çağrı reddedilir
- sahte belge reddedilir
- başka isteğin belgesi reddedilir
- ikinci kullanım reddedilir
- rezervasyon her zaman adaptörden önce yapılır
- tavan dolunca adaptöre hiç gidilmez

### 2. OpenAI adaptörü davranışı değiştirmez

Sınıflandırma ve gövde `core/openai_adapter.py`'ye birebir taşındı. Refactor'dan **önce**, gerçek SDK ve ağsız `httpx.MockTransport` ile üç işlemin altın istek gövdeleri üretildi (commit `f1e2ad1`). Refactor sonrası gövdeler bayt bayt aynıdır. `parse_response`, eski çağıranlar için bir uyum girişidir.

### 3. Sağlayıcı seçimi

`TEACHERAI_PROVIDER_VISION`, `TEACHERAI_PROVIDER_LESSON` ve `TEACHERAI_PROVIDER_INTERACTION` ayarları vardır; varsayılan `openai`'dir. **Fallback yoktur.**

Şu durumlarda uygulama başlamaz:

- desteklenmeyen bir işleme sağlayıcı atanması
- Anthropic'e atanmış bir işlemde model veya anahtar eksikliği
- production/staging'de OpenAI anahtarının eksikliği
- production'da fiyatı tanımsız model

### 4. Tek fiyat ve yetenek kaynağı

`apps/api/app/core/model_catalog.json` dosyası, eski `evals/config/models.json`'un yerine geçer. Uygulamadaki `Settings.model_prices`, reasoning düzeyleri ve `scripts/eval_pack.py` bu dosyayı okur. `TEACHERAI_MODEL_PRICES` yalnızca açık bir geçersiz kılmadır.

Fiyatı olmayan modelin maliyeti hesaplanmaz. Claude Haiku 5.5 kademeli fiyatlıdır (100.000 token üstü istem için farklı fiyat). Tek fiyatla gösterilemediği için fiyatsız bırakıldı.

### 5. Anthropic adaptörü

Aşağıdaki değerler 22 Kasım 2026'da resmî belgeden okundu. docs.claude.com adresi platform.claude.com'a yönleniyor.

| Konu | Değer | Kaynak |
| --- | --- | --- |
| Uç nokta ve başlıklar | `POST https://api.anthropic.com/v1/messages`, `x-api-key`, `anthropic-version` (belgedeki örnek: `2026-10-21`), `content-type: application/json` | https://platform.claude.com/docs/en/api/messages, örnek istekler: …/build-with-claude/structured-outputs |
| Gövde | `model`, `max_tokens`, `messages`; sistem istemi üst düzey `system` | aynı |
| Görsel bloğu | `{"type":"image","source":{"type":"base64","media_type":…,"data":…}}` | aynı |
| Yapılandırılmış çıktı | `output_config.format = {type: "json_schema", schema}`; JSON, yanıtın metin bloğunda | https://platform.claude.com/docs/en/build-with-claude/structured-outputs |
| Şema kısıtları | Desteklenmeyenler: özyinelemeli şema; `oneOf`; `not`; `type`/`properties` ile aynı nesnede `anyOf`; enum içinde karmaşık tip; dış `$ref`; `minimum`/`maximum`/`multipleOf`; `minLength`/`maxLength`; 0/1 dışında dizi sınırı; `false` dışında `additionalProperties`; geri başvuru veya bakınma içeren regex. Desteklenmeyen özellik 400 döner. | aynı |
| Görsel sınırları | `image/jpeg`, `image/png`, `image/gif`, `image/webp`; API'de görsel başına 10 MB (base64); en çok 8000×8000 px (20'den fazla görselde 3000 px); istek başına 100 görsel (200k bağlamlı modeller, diğerlerinde 600) | https://platform.claude.com/docs/en/build-with-claude/vision |
| `stop_reason` | `end_turn`, `max_tokens`, `stop_sequence`, `tool_use`, `pause_turn`, `refusal`, `model_context_window_exceeded` | https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons |
| usage | `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`; düşünme tokenı `output_tokens_details.thinking_tokens` | Messages API başvurusu (bu alanlar belge özetinden okundu, birebir alıntı değil) |
| Model kimlikleri | `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` | https://platform.claude.com/docs/en/about-claude/models/overview |
| Fiyat (USD / milyon token: girdi, önbellek okuma, çıktı) | Fable 5.2: 8 / 0,20 / 40. Opus 5.5: 4 / 0,20 / 20. Sonnet 5.5: 2 / 0,10 / 10. Haiku 5.5 kademeli. | https://platform.claude.com/docs/en/about-claude/pricing |

**Doğrulanamayanlar.**

- Messages başvuru sayfası kesildiği noktaya kadar okundu. Gövde alanlarının zorunluluğu ve `anthropic-version` kuralları o bölümde yazmıyordu.
- Şema kısıt listesi ve usage alan listesi, belge aracının özetinden alındı; birebir alıntı değildir.
- Belgedeki kısıt listesi dışında şema karmaşıklık sınırları olup olmadığı doğrulanamadı.

**Bağımlılık.** Resmî SDK eklenmedi. `httpx` kilit dosyasında zaten hash'li olarak bulunuyor (openai bağımlılığı olarak). Adaptör tek uç noktaya tek POST atar. Yeni bir kilitli paket ve geçişli bağımlılıkları eklenmedi; CI kurulumu değişmedi.

**Sonuç eşlemesi:**

| `stop_reason` | Sonuç |
| --- | --- |
| `end_turn` | `completed` (metin yoksa `invalid_output`) |
| `max_tokens` | `incomplete_max_tokens` |
| `model_context_window_exceeded` | `incomplete_other` |
| `refusal` | `refusal` |
| `stop_sequence`, `tool_use`, `pause_turn`, eksik veya bilinmeyen değer | `provider_error` |

Adaptör araç, durdurma dizisi, önbellek ve düşünme parametresi **göndermez**; bu yüzden son satırdaki değerler beklenmez. HTTP hatası `provider_error` (`http_<kod>`), zaman aşımı `timeout` olur.

**Kullanım.** Kanonik girdi, `input_tokens` + önbellek okuması + önbellek yazımı toplamıdır; `cached_input` önbellek okumasıdır. Önbellek yazımı 1,25×/2× fiyatlıdır ve tek fiyatla gösterilemez. Bu yüzden yazım görülürse `cached_input` bilinmez sayılır ve maliyet hesaplanmaz.

**Şema uyumu (çevrimdışı, `python -m scripts.anthropic_schema_compat --check`, CI'da):**

| İşlem | Şema | Sonuç |
| --- | --- | --- |
| ders | `LessonDraftResponse` | uyumlu → **desteklenir** |
| vision | `VisionProviderAnalysis` (`minimum` ×2, `maximum` ×1), `RecheckResponse` (uyumlu) | uyumsuz → **desteklenmez** |
| etkileşim | `AdaptiveDraft` (`minLength` ×1) | uyumsuz → **desteklenmez** |

Kısıtlar sessizce atılmaz. Şemayı Anthropic'e uygun bir varyanta çevirip doğrulamayı yalnız sunucuda yapmak ayrı bir karardır (TA-005C).

### 6. Öğrenci görselleri

Vision için Anthropic seçilebilmesi iki koşula bağlıdır: `TEACHERAI_PROVIDER_VISION=anthropic` ve `TEACHERAI_ALLOW_STUDENT_IMAGES_TO_ANTHROPIC=true`. Bayrak yoksa uygulama başlamaz. Adaptör de bayrak olmadan hiçbir görseli göndermez ve belge sınırlarını (tür, 10 MB, adet) istemci tarafında uygular.

**Bu bayrağın açılması bir hukuk ve ürün kararıdır.** Şunlar tamamlanmadan bayrak açılamaz:

- gizlilik metninin (`docs/privacy/gizlilik-metni-taslak.md`) ikinci alt işleyeni, yurt dışı aktarım dayanağını ve saklama koşullarını kapsayacak şekilde güncellenmesi
- Anthropic ile veri işleme sözleşmesinin değerlendirilmesi

Karar Erdem'indir. Bugün Vision şeması da uyumsuz olduğu için bayrak açılsa bile Vision Anthropic'e atanamaz.

### 7. Doğrulama zinciri sağlayıcıdan bağımsızdır

Question Integrity sağlayıcıdan önce çalışır. AnswerTarget, MathAI, LessonPlan ve yöntem denetimi sağlayıcıdan sonra, aynı kodla çalışır. Sahte (OpenAI olmayan) adaptörle sınandı: yanlış cevap MathAI düzeltmesini tetikler, şemaya uymayan çıktı `invalid_output` olur, netleştirme gereken soruda adaptör hiç çağrılmaz.

Uyum testi, dokuz fikstürü iki adaptörün sahte yanıtlarından geçirir: iç içe kök, kesir çizgisi, negatif işaret, gizli şık, istenen hedef, birimli fizik, kimyasal formül, öncül, eksik bilgi. Aynı kanonik ders ve aynı doğrulama sonucu üretildiği gösterilir. **Bu bir kalite ölçümü değildir.**

## TA-006 bağlantısı (yalnızca tasarım; bu fazda şema veya modül açılmadı)

Mevcut `CurriculumRegistry` (`features/education/curriculum.py`) bugün yalnız `mathematics` + sınıf + konu + kazanım + yöntem politikası taşır. TA-006'da aynı kayıt şu alanlarla genişler:

- **Branş:** `subject`, matematiğin yanında fizik, kimya ve biyolojiyi **birinci sınıf** branş olarak alır. Fen dersleri ayrı bir yan model değil, aynı kayıttır.
- **Sınav hedefi:** LGS, TYT, AYT gibi sınav hedefleri, sınıf düzeyinden ayrı ve isteğe bağlı bir eksen olur.
- **Program sürümü:** MEB 2018 ve Türkiye Yüzyılı Maarif Modeli ayrı sürümler olur. Kazanım hangi sürüme aitse onunla kaynaklanır. 8. sınıfta 2026–27'de hangi programın okutulduğu bugün doğrulanamadı.
- **Alt kazanım ve ön koşul:** Kazanımlar ağaç yapısında tutulur. Ön koşul ilişkisi ayrı, yönlü bir bağdır.
- **Yöntemin geçerlilik koşulları:** Politika satırı sınıf, konu, sınav hedefi ve program sürümüyle koşullanır. İzinli ve yasak işlemler TA-005B'deki güçlü kanıt (AST, sunucu sınıflandırması) üzerinden denetlenir.
- **Öğretmen değerlendirmesi kaydı:** Kim, ne zaman, hangi kanıtla değerlendirdi; ayrı ve değiştirilemez kayıtlar olarak tutulur. Öğretmen görüşü uydurulmaz. Bu fazda hiçbir öğretmen değerlendirmesi kaydedilmedi.
- **Onay durumu:** `draft` / `approved` korunur. Onay yalnızca kayıtlı bir öğretmen değerlendirmesiyle verilir. Sağlayıcı çıktısı onay belirleyemez.
- **Kanıt düzeyi:** kaynaklı (resmî belge ve sayfa), öğretmen incelemeli ve taslak ayrımı her satırda görünür.

FKB (fizik, kimya, biyoloji) denetimleri öğrenciye kapalı kalır. Bu branşlarda üretim açılmadan önce TA-009–TA-011 alan motorları gerekir.

## Reddedilenler

- Otomatik fallback: maliyet ve gizlilik sınırlarını öngörülemez hâle getirir.
- Uyumsuz şemadan kısıtları sessizce atmak.
- Anthropic için varsayılan model seçmek: model varsayılanları değiştirilmez.
- Isıtılmış MathAI süreç havuzu: görev başına `RLIMIT_CPU`/`RLIMIT_AS` kurulamaz (Bölüm 6, TA-005B raporu).
