# ADR TA-002 — Ortak eğitim çekirdeği ve LessonPlan v2

Durum: kabul edildi (TA-002). Kod: `apps/api/app/features/education/`. Üretilen sözleşme: `docs/contracts/education-v2.schema.json`, `apps/web/app/lib/education.generated.ts`.

Bu kayıt altı kararı birlikte tutar. Her karar yalnızca bugün çalışan kodu anlatır. Planlanan yetenekler ayrıca işaretlenmiştir.

## 1. Kanonik eğitim alanı

**Karar.** Alan kimlikleri `Subject` enum’udur: `mathematics`, `geometry`, `physics`, `chemistry`, `biology`, `science`, `unknown`. Etiket eşlemesi `domain.canonical_subject` içindedir ve yalnızca enum değerlerini ve şu Türkçe etiketleri tanır: Matematik, Geometri, Fizik, Kimya, Biyoloji, Fen Bilimleri, Fen Bilgisi (büyük/küçük harf ve İ duyarsız). Diğer her etiket `unknown` olur.

**Tek istisna.** v1 görsel istemi yalnızca matematik sorusunu `valid_math_question` olarak kabul eder ve `subject` alanını serbest Türkçe metin olarak döndürür (“Cebir”, “Temel Matematik”). Bu durumda `math_adapter.understand` alanı `mathematics` yapar. Kanıt etiket değil, matematik kapısıdır. Kanonik olarak başka bir alana eşlenen etiket (ör. “Fizik”) matematik sayılmaz.

**Bağlam kaynağı.** `EducationContext` alanları köken taşır: `declared` (öğrenci beyanı), `profile` (sunucudaki profil), `inferred` (AI çıkarımı). `Grade` yalnızca `declared` veya `profile` olabilir. Sınıf düzeyi yüklenen sorudan çıkarılamaz. Bilinmeyen değer `null` kalır. `TeachingPolicy.exam_context` profil değeri varken AI çıkarımını kullanmaz.

**Referanslar.** `Reference(kind, key, review)` kavram, kazanım, yöntem, ön koşul, müfredat sürümü, kaynak ve öğrenci bağlamı için ortak tiptir. `review` alanının tek değeri `unreviewed`’dır. Yetkili kayıt defteri (TA-004) gelene kadar hiçbir referans resmî müfredat onayı ifade edemez.

**Reddedilen.** Serbest metin alan adları kimlik olarak kullanılmadı. Bilinmeyen etiketi matematiğe düşürmek reddedildi.

## 2. LessonPlan v2

**Karar.** `LessonPlanV2` şema kimliği `teacherai.lesson_plan` / `2.0.0`’dır. Başka sürüm reddedilir. Sorumluluklar ayrı tiplerdir:

| Tip | Sahibi | İçerik |
| --- | --- | --- |
| `EducationalDraft` | Sağlayıcı taslağı | etkinlik, hedefler, referanslar, bloklar, cevap, özet |
| `VerificationReport` | Sunucu | boyut bazında doğrulama durumu |
| `Provenance` | Sunucu | sağlayıcı ve model adı |
| `LessonPlanV2` | Sunucu | kimlik, kaynak, bağlam, taslak, köken, doğrulama |
| `LessonView` | Sunum | ders + BoardPanel listesi + oluşturulma zamanı |

Tüm modeller `extra="forbid"` ve `allow_inf_nan=False` kullanır. Taslakta sahip, onay, doğrulama, abonelik veya kullanım alanı yoktur. Bu alanları içeren girdi doğrulamadan geçemez.

**Bloklar** (`kind` ayırıcılı birlik): `explanation`, `definition`, `warning`, `hint`, `checkpoint`, `result`, `summary` (ortak metin bloğu), `expression` (LaTeX), `calculation` (ifade + tipli sonuç), `worked_example` (soru, açıklama, cevap ayrı), `table`, `visual`. Görsel türleri izin listesindedir: `number_line` (artan, benzersiz, en çok 16 sonlu konum), `source_figure` (kaynak şekle atıf), `unsupported` (açıkça gösterilemeyen tür). SVG, HTML, JavaScript, CSS veya çizim komutu taşıyan alan yoktur.

**Cevaplar** (`kind` ayırıcılı): `math`, `number`, `quantity` (değer, birim, etiket), `choice` (seçenekler + geçerli dizin), `text`, `table`. Soru çözümü cevap ister. Konu dersi cevapsız geçerlidir.

**Sınırlar** (kasıtlı, `domain.py`): metin 8192, etiket 256 karakter. Kimlik `^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$`. En çok 256 blok, 32 hedef, ders başına 64 ve blok başına 16 referans, blok başına 16 ilişki. Tablo 1–12 sütun, 1–40 satır ve dikdörtgen olmalı. Seçenek 2–12, matematik cevabında en çok 64 ifade. Sayılar sonlu ve sıkı (`strict`) olmalı. Blok kimlikleri benzersizdir. `relates_to` var olan başka bir bloğu göstermelidir. Geçersiz içerik sessizce düşürülmez, reddedilir.

**Reddedilen.** Serbest `dict`/JSON içerik, v1 alanlarını genişletmek ve her alan için ayrı ders tipi.

## 3. Alan yeteneği çözümü

**Karar.** `domain.capabilities(subject)` sunucuda sabit bir fonksiyondur. Sağlayıcı veya istemci değiştiremez.

| Alan | Temsil | Tanıma | Üretim | Doğrulama | Pratik | Sunum |
| --- | --- | --- | --- | --- | --- | --- |
| mathematics, geometry | evet | evet (v1 görsel istemi) | evet | `bounded_math` (MathAI) | evet | evet |
| physics, chemistry, biology, science | evet | hayır | hayır | `unsupported` | hayır | evet (çevrimdışı fikstürler) |
| unknown | hayır | hayır | hayır | `unsupported` | hayır | hayır |

Üretimi olmayan alan `/lessons/generate` içinde sağlayıcı ve MathAI çağrılmadan 422 `subject_generation_unavailable` alır. Geometri, matematik hattını kullanır ve MathAI’nin geometri doğrulaması sınırlıdır. Tablo “yetenek var” demektir, kapsamın tam olduğunu söylemez.

**Reddedilen.** Eklenti sistemi ve altı boş motor.

## 4. Doğrulama semantiği

**Karar.** `VerificationReport` boyutları: `structural`, `scientific`, `calculation`, `source_consistency`, `curriculum`, `method`, `pedagogy`. Durumlar: `passed`, `failed`, `partially_checked`, `unsupported`, `not_checked`, `not_applicable`.

- `structural` yalnızca `passed` olabilir. Yapısal olarak geçersiz ders oluşmaz.
- `scientific: passed` bu sürümde hiçbir derste kabul edilmez. Tam bilimsel doğrulayıcı yoktur.
- Doğrulama motoru olmayan alanda `scientific` ve `calculation` `passed` veya `partially_checked` olamaz.
- `curriculum`, `method`, `pedagogy` yalnızca `not_checked` olabilir.
- MathAI uyarlaması (`math_adapter.verification_report`): `verified` → `calculation: passed`, `scientific: partially_checked`. `partially_verified` → ikisi de `partially_checked`. `unsupported` → ikisi de `unsupported`. `failed` veya çelişki → `VerificationContradictionError`. Başarısız ders sunulmaz. MathAI algoritmaları, artı-eksi ve çözüm kümesi kuralları, düzeltme döngüsü ve yalıtılmış işçi değişmedi.

Güven puanı yoktur. Kalibre edilmemiş sayı olasılık gibi sunulmaz.

## 5. v1/v2 uyumu

**Karar.** Yetkili kayıt Firestore’daki v1 `GeneratedLesson`’dır. v2 kalıcı olarak saklanmaz. `validated_math_lesson(plan, verification)` her istekte belirlenimci bir projeksiyon üretir. Aynı mantıksal ders için iki yetkili kayıt yoktur.

- `POST /api/v1/lessons/generate` yanıtı ve kayıt biçimi değişmedi. Üretim sırasında da projeksiyon kurulur ve BoardPlanner son cevabı ondan alır. Projeksiyon kurulamazsa ders kaydedilmez.
- `GET /api/v1/lessons/{lesson_id}/v2` yalnızca oturum sahibinin sunucuda üretilmiş dersini döndürür (`StudentService.owned`). Başka kullanıcı ve eski doğrulanmamış (`server_generated=false`) kayıt 404 alır. Yanıt `Cache-Control: private, no-store` taşır. Sağlayıcı çağrısı, kota tüketimi, olay veya yazma yapılmaz.
- v2’den v1’e ters dönüşüm yoktur. Matematik dışı v2 dersi v1 olarak temsil edilemez.
- Geri alma: v2 rotası ve geçmişteki “Ders anlatımını aç” düğmesi kaldırılırsa veri değişikliği gerekmez.
- Paylaşım sözleşmesi değişmedi. Özel `LessonPlanV2` herkese açık yanıt olarak kullanılmaz. Matematik dışı paylaşım, inceleme ve yayın sınırı tanımlanmadan açılmayacak.

## 6. Sözleşme üretimi

**Karar.** Kaynak Pydantic modelleridir. `python -m scripts.education_contracts` `LessonView`, `QuestionUnderstanding` ve `Capabilities` köklerinden JSON Schema (2020-12, sıralı anahtarlar) ve TypeScript tipleri üretir. `--check` eski dosyada hata verir. CI’da ve `test_generated_contracts_are_current` testinde çalışır. Üretici yalnızca kapalı nesneleri (`additionalProperties: false`) dönüştürür, `any` üretmez. Yeni bağımlılık eklenmedi.

- Sağlayıcı yapılandırılmış çıktı şeması bu sözleşmeden ayrıdır. Mevcut OpenAI v1 `LessonDraftResponse` şeması değişmedi. Gelecekteki v2 sağlayıcı adaptörü düz bir tel biçimini açık bir dönüştürücüyle `EducationalDraft`’a çevirmelidir, çünkü ayırıcılı birlikler her sağlayıcıda desteklenmeyebilir.
- Mevcut v1 TypeScript tipleri (`lesson-api.ts` vb.) elle yazılıdır ve bu fazda üretime taşınmadı.

## Sonuçlar

- TA-003 sağlayıcı adaptörleri aynı `EducationalDraft`’ı üretmeli. Çekirdek OpenAI SDK tipine bağlı değildir.
- TA-004 `Reference` anahtarlarını yetkili kayıtlara karşı çözecek ve `review` durumunu genişletecek. `curriculum` ve `method` boyutları ancak o zaman `not_checked` dışında bir değer alabilir.
- Yeni alan motoru eklemek için `capabilities` tablosu, bir anlama adaptörü ve gerçek bir doğrulayıcı gerekir. Doğrulayıcısız alan `unsupported` kalır.
