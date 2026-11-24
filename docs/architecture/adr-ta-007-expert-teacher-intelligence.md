# ADR TA-007: Uzman öğretmen zekâsı, bilimsel bilgiye dayandırma ve denetimli geri getirme

- Durum: kabul edildi (TA-007, 2026-11-24/25)
- Önceki kararlar: [ADR TA-006](adr-ta-006-curriculum-knowledge.md), [bilimsel bilgi mimarisi](adr-ta-006-scientific-knowledge-architecture.md), [ADR TA-005C](adr-ta-005c-provider-completion.md)
- İlgili: [geri getirme mimarisi](ta-007-retrieval.md), [inceleme akışı](../governance/TA-007-review-workflow.md), [hak uygulaması](../sources/TA-007-rights-enforcement.md), [değerlendirme hazırlığı](../evals/TA-007-readiness.md)

## Bağlam

TA-006 müfredat kaydını, taslak bilgi kaydını ve ders bağlamının ilk sürümünü kurdu; ama ders akışı hâlâ v1 yöntem/müfredat denetimini kullanıyordu, onay sözdizimi (ör. `teacher:...`) yetki kanıtı sayılabiliyordu, bilgi koşulları bağlamda kırpılıyordu (`conditions_tr[:6]`) ve sağlayıcının acil sıkıştırmada bağlamı düşürüp düşürmediği kayda geçmiyordu.

## Karar

### 1. Ayrı motorlar, sabit oran yok

| Motor | Modül | Ne belirler | Ne belirleyemez |
| --- | --- | --- | --- |
| Müfredat | `curriculum/registry_v2.py` | Hangi program, sınıf, izlek, sınav kapsamı | Yöntemin uygunluğu, bilimsel doğruluk |
| Konu taksonomisi | `curriculum/topics.py` | Sorunun aday konuları ve kanıt düzeyi | Konunun kesin olduğu (yalnız yapısal kanıt) |
| Bilimsel bilgi | `knowledge/registry.py`, `knowledge/retrieval.py` | Hangi onaylı ve hakları açık girdinin bağlama girebileceği | Onay; bilimsel doğrulama |
| Öğretmen uzmanlığı | `curriculum/methods.py` (MethodPolicy v2), katkı yönetişimi | Bu sınıf/program/konuda hangi yöntemin uygun olduğu | Bilimsel geçersizlik |
| Python akıl yürütme | `mathai`, `reasoning`, `integrity` | Hesap, hedef, kaynak tutarlılığı | Öğretimsel uygunluk |
| AI akıl yürütme | geçit üzerinden sağlayıcı | Taslak anlatım | Doğrulama, müfredat, onay durumu |
| Sunum | `education/presentation.py`, web | Gösterim ve aşamalı köken | Kontrol sonucu |

Motorların ağırlığı sabit bir yüzdeyle karıştırılmaz: her boyut ayrı sonuç üretir (CLAUDE.md'deki beş boyut).

### 2. Yetki kaydı ve bayat onay

- Onay yalnız proje sahibinin `knowledge/data/reviewers.json` kaydında, ilgili **aşama, alan, rol ve tarih** için yetkili bir inceleyenden geçerlidir. Üretim kaydı boştur. Sentetik yetkiler yalnız yalıtılmış testlerde fikstürdür.
- Bilgi girdisi onayı içerik özetini (`content_digest`, bilimsel alanların sha256'sı) taşır; içerik değişirse onay `stale_approval` olur.
- Yöntem politikası onayı `approved_on` + `approval_digest` (politika içeriğinin özeti) taşır; eksikse `approval_incomplete`, uyuşmazsa `stale_approval`.
- Hak kararı ayrı bir kapıdır (`RightsRecord.decision`, yalnız `owner:` ve `rights` yetkisi).

### 3. MethodPolicy v2 ders akışında

`LessonService` artık `curriculum.methods.method_check` ve `curriculum_check` kullanır; v1 işlevleri yalnız geriye dönük testler ve v1 kayıt için kalır. Politika seçimi: alan + çözümlenmiş program + sınıf + konu. Belirsizlik kuralları:

- Program belirsizse yasak işlem yalnız bütün aday programlarda yasaksa `failed` üretir.
- Konu yalnız AST yapısından gelirse kesindir; sözcük eşlemesinde konu politikası `passed` üretmez, yasaklar yalnız bütün aday konularda ortaksa uygulanır.
- Açık ileri yöntem isteği (`advanced_method_requested`) yasak işlemi `partially_checked` yapar; düzeltme turu yok.
- Kanıt sınıfları adım başına kaydedilir: `used` (güçlü), `mentioned` (zayıf), `rejected` (olumsuzlanmış söz), `identifiable`, `unparsed`. Yalnız gösterilen adımlar incelenir; MathAI'nin iç çözücü işlemleri yöntem kanıtı değildir.
- Müfredat boyutu yöntem politikasından bağımsızdır: `passed` yalnız çözümlenmiş program + yapısal kesin konu + kazanımın kendi konu anahtarı/takma adıyla eşleşme. Taksonomi deseni veya sözcük eşlemesi `partially_checked`; programda bulunamayan konu `failed` değil `partially_checked` (eşleme incelenmedi).

Aynı `PolicySet` hem denetimde hem köken kaydında kullanılır; v1/v2 çelişkili karar üretilemez.

### 4. Denetimli geri getirme (RAG)

Vektör veritabanı, gömme veya ek model çağrısı yoktur. Ayrıntı: [ta-007-retrieval.md](ta-007-retrieval.md). Kayıt bütünüyle paketlenir; koşul/varsayım/istisna kırpılmaz, sığmayan kayıt dışarıda bırakılır ve nedeni kaydedilir.

### 5. Köken: seçilen ve gerçekten gönderilen

`LessonProviderResult.context_level` sağlayıcının gerçekten gönderdiği bağlam düzeyini bildirir (`normal`/`emergency`). `EducationalProvenance` seçimi (`knowledge_ids`, `knowledge_refs` sürüm+özet, dışlananlar, sıkıştırılanlar, politika kimlikleri, doğrulayıcı kapsamı) ve iletimi (`transmission`, `transmitted_knowledge_ids`) ayrı tutar. Düzey bildirilmezse `transmission` uydurulmaz (`null`). Köken ders oluşturulurken bir kez yazılır, sonradan değişmez.

### 6. İzlek ve sınav hedefi

Okul izleği (`general`, `science_high_school`, `basic_level`) yalnız açık beyandır (profil `school_track` veya istek). Beyan yoksa genel program kullanılır ve gerekçe yazılır. Sınav hedefleri Türkçe ekleriyle ayrıştırılır ("LGS'ye", "YKS" = TYT+AYT); birden çok hedef kaybolmaz. "Mezunum" beyanı öğrenci durumunu belirleyebilir; görselden çıkarılmaz.

### 7. Öğretmen katkısı

Katkı dosyası yalnız girdidir; aşamalar ayrı `register.json` kaydındadır (çevrimdışı araç, çalışma zamanı okumaz). Ayrıntı: [inceleme akışı](../governance/TA-007-review-workflow.md).

## Teacher AI ile genel LLM uygulaması arasındaki fark

| Konu | Genel LLM uygulaması | Teacher AI (bugünkü gerçek durum) |
| --- | --- | --- |
| Sınıf ve program | Modelin tahmini | Beyan + resmî takvim kuralları; belirsizlik açık |
| Bilgi | Modelin parametrik belleği | Yalnız yetkili onaylı, hakları açık girdiler (bugün 0); koşullarıyla bütün |
| Yöntem | Modelin seçimi | Onaylı politika varsa sunucu denetimi (bugün onaylı politika 0) |
| Doğruluk | Modelin kendi beyanı | MathAI/FKB belirlenimci denetimleri; sağlayıcı çıktısı onay belirleyemez |
| Köken | Yok | Sürüm, seçim, dışlama ve gerçek iletim kaydı |

## Gerçek ve hedef mimari

- **Gerçek:** Bütün mekanizmalar çalışıyor ve testli; ancak üretim verisinde yetkili inceleyen, onaylı bilgi girdisi, onaylı yöntem politikası ve yayımlanmış öğretmen katkısı **0**'dır. Bu yüzden derslerde bilgi ve yöntem bağlamı fiilen boştur; müfredat kodu/başlığı bağlamı çalışır.
- **Hedef:** Proje sahibi öğretmen/uzmanları yetkilendirdikçe ve hak kararları verildikçe aynı kod yolu ek değişiklik olmadan onaylı içeriği bağlama alır.

## Sonuçlar

- v1 yöntem denetimi ders akışından çıktı; v1 kayıt (`lgs-matematik-8.json`) korunur ve çağrı anında v2'ye taşınır.
- `curriculum_check` artık resmî programla eşleşmeyi raporlar (TA-005'te politika gerektiriyordu); bu bilinçli bir anlam değişikliğidir ve testlerde gerekçesiyle güncellendi.
- Ek sağlayıcı çağrısı yoktur; mevcut çağrı tavanı değişmedi.
