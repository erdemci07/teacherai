# ADR TA-003 — Soru bütünlüğü, görsel zekâ ve maliyet duyarlı çözümleme

Durum: kabul edildi (TA-003). Kod: `apps/api/app/features/integrity/`, sözleşmeler: `apps/api/app/features/education/source.py`. Sonuçlar ve ölçümler [TA-003 raporunda](../phase-reports/TA-003.md).

Temel sorun şudur: yanlış tanınmış bir soru için matematiksel olarak kusursuz bir çözüm üretilebilir. Matematik doğrulaması görselin doğru anlaşıldığını kanıtlamaz. Bu kayıt, sorunun kendisinin bütünlüğünü kaynak gözleminden çözüme kadar nasıl ele aldığımızı anlatır. Yalnızca çalışan kodu anlatır.

## 1. Konum ve sınır

- `features/integrity/` sağlayıcıdan bağımsız, saf Python bir modüldür. Ayrı servis değildir. `education/source.py` alandan bağımsız sözleşmeleri taşır: bölge, belirsizlik, alternatif, seçenek, ifade, amaç, karar ve revizyon. Fizik birimi, kimya alt simgesi veya biyoloji etiketi belirsizlikleri aynı kavramları kullanabilir. Bu alanlar için tanıma veya çözüm açılmadı.
- Temel tipler (`Contract`, `Subject`, `Identifier`) döngüsel içe aktarmayı önlemek için `education/base.py` içine taşındı. `domain.py` bunları yeniden dışa aktarır.

## 2. Karar durumları ve önemlilik

`IntegrityReport.decision`: `ready`, `ready_with_noncritical_uncertainty`, `targeted_recheck` (yalnızca istek içinde ara durum), `clarification_required`, `retake_required`, `incomplete`, `unreadable`, `no_question`, `unsupported_subject`. Yalnızca ilk ikisi çözülebilir. Şema, çözülmemiş kritik belirsizlik varken "hazır" kararını reddeder.

Belirsizliklerin etkisi üç düzeydedir:

| Etki | Örnek | Davranış |
| --- | --- | --- |
| `noncritical` | yazım, dekoratif görsel, eski serbest metin notu, desteklenmeyen gösterim, eşdeğer alternatif | devam edilir, ek çağrı yapılmaz, öğrenciye sorulmaz |
| `material` | kök/üs/kesir kapsamı, eksi işareti, ondalık konumu, olumsuzluk çelişkisi, seçeneğe bağlı soruda eksik seçenek, belirsiz şekil ölçüsü, yapısal olarak geçersiz ifade, birden fazla olası hedef soru | yerel çözüm → en çok bir hedefli yeniden okuma → son çare öğrenci açıklaması |
| `fatal` | kesik/okunamaz kaynak, soru yok, metin ve ifade ikisi de yok | anlaşılır kurtarma eylemi, ders üretilmez |

Belirleyici kurallar:

- Güven puanı karar girdisi değildir.
- Görüntü kalite göstergeleri tavsiye niteliğindedir ve tek başına karar değiştirmez.
- `unsupported` ayrıştırma (integral, derece, birim, çok harfli etiket) soruyu reddetmez. `invalid` (dengesiz ayraç, eksik pay/payda/kök içi) çıkarım hatası kanıtıdır.
- Seçenek sorunlarının etkisi soru amacına bağlıdır. Bağımsız çözülebilir sorularda eksik etiket önemsizdir. "Hangisi yanlıştır" gibi seçeneğe bağlı sorularda kritiktir.
- Kullanılan neden kodları `ReasonCode` listesindedir.

## 3. Belirlenimci yerel zekâ

- **İfade ağacı** (`expression.py`): özyinelemeli inişli, dengeli ve sınırlı bir ayrıştırıcıdır: 400 karakter, 160 token, 32 derinlik, 240 düğüm, 8 sembol, 15 basamak. Desteklenenler: sayı, sembol (alt simge dahil), sabit π, tekli eksi, +, −, ±, ×/·/\cdot, ÷, /, `\frac` (iç içe), tam sayılı kesir, üs (sağdan birleşimli, üst simge rakamlar), `\sqrt`, `\sqrt[n]`, `√`, mutlak değer, ayraçlar, sin/cos/tan/cot/log/ln, eşitlik ve tek yönlü eşitsizlik zinciri. `eval`, `exec`, `ast.parse` ve `sympify` kullanılmaz.
- **Yapı ve görüntü:** Ağaç kaynak gösterimini korur (`Group`, `Frac`, `Root` ayrı düğümlerdir). `shape()` anlam karşılaştırması için gruplamayı yapıya gömer. `sqrt(5 + sqrt(9))` ile `sqrt(5) + sqrt(9)`, `(2 + 4)/3` ile `2 + 4/3`, `-(2^2)` ile `(-2)^2`, `sin(x^2)` ile `sin(x)^2` farklıdır. Görüntü LaTeX'i ağaçtan üretilir, kesir ve kök gösterimi korunur. Kanonik ASCII biçim ile LaTeX çıktısının yeniden ayrıştırılması aynı yapıyı verir. Bu, bir testle sınanır.
- **Normalleştirme:** Unicode eksi, çarpma ve bölme işaretleri, üst simge, LaTeX boşlukları ve `\dfrac` dönüşür. Her dönüşüm `NormalizationNote` olarak kaydedilir ve özgün okuma `source` alanında kalır. Virgül, yalnızca rakamlar arasında ve tek ayırıcı olarak kullanılıyorsa ondalıktır. `(2,3)` nokta ya da aralık olabileceğinden ondalık sayılmaz. `1,250` binlik ayırıcıyla karışabileceğinden kritik belirsizliktir ve iki belirlenimci alternatif üretir.
- **Kesin değer:** `exact_value` yalnızca `Fraction` kullanır, üs ve bit uzunluğu sınırlıdır. SymPy FastAPI sürecinde pahalı işlem yapmaz. Hesap için SymPy dönüşümü (`mathai/parser.py`) eski bütçeleri (4 sembol, 12 basamak, 100 düğüm, |üs| ≤ 10) korur ve yalıtılmış işçide çalışır.
- **Türkçe amaç** (`language.py`): değildir, olamaz, yanlıştır, doğrudur, en az, en çok, yalnızca, kesinlikle, olabilir, farklı, eşit, toplamı, farkı, kaç tanedir işaretleri ile I/II/III öncülleri çıkarılır. Metin değiştirilmez. Tam doğal dil ayrıştırıcısı değildir.
- **Seçenekler:** Basılı etiket ile içerik arasındaki ilişki kaynak verisidir. Sıraya göre etiket uydurulmaz veya yeniden etiketleme yapılmaz. Eşdeğer değerli seçenekler hata sayılmaz.

## 4. Hedefli yeniden okuma

- Yalnızca görsel olarak çözülebilir kritik belirsizlikte ve `POST /vision/analyze` isteğinin içinde yapılır. Bu sayede görsel kalıcı olarak saklanmaz ve örnekler arası geçici dosyaya bağımlılık oluşmaz.
- Varsayılan sınır 1'dir (`TEACHERAI_VISION_MAX_RECHECKS`, 0–2). 0 değeri ek okumayı kapatır.
- En çok 3 belirsiz parça tek çağrıda sorulur. Tek parça ve geçerli bölge varsa pay bırakılmış kırpıntı gönderilir. Düşük kontrast veya pozlama tavsiyesinde ek olarak gri ton, ölçülü kontrastlı bir kopya eklenir. Keskinleştirme ve eşikleme uygulanmaz.
- Yanıt ilk okumayla karşılaştırılır. Aynı veya anlamca eşdeğer okuma "teyit" sayılır. Bu, iki okumanın uyumudur, doğrulama değildir. Farklı okuma, iki okumayı da öğrenciye seçenek olarak sunar. Son yanıt kendiliğinden doğru kabul edilmez.
- Çağrı mevcut `OpenAIVisionProvider` → `parse_response` (gateway) yolundan geçer. Çıktı rezervasyonu, kullanıcı kotası, küresel bütçe ve `ai_usage` kaydı (`purpose: vision.recheck`) aynen uygulanır. Bütçe, kota veya sağlayıcı hatası çözümü durdurmaz; kontrollü olarak açıklamaya düşer.

## 5. Mantıksal istek başına çağrı tavanı

`Accounting.max_calls` kabul aşamasında atanır ve gateway, tavan dolunca rezervasyondan **önce** `ProviderCallBudgetExhausted` (503 `ai_call_budget_exhausted`) fırlatır.

| HTTP işlemi | Tavan | Ayar |
| --- | --- | --- |
| analyze | 1 + `vision_max_rechecks` (varsayılan 2) | `TEACHERAI_VISION_MAX_RECHECKS` |
| generate | 3: ilk ders, düzeltme ve bağlam yeniden denemesi toplamda | `TEACHERAI_LESSON_MAX_PROVIDER_CALLS` (1–4) |
| interact | 1 | `TEACHERAI_INTERACTION_MAX_PROVIDER_CALLS` (1–2) |

TA-003 öncesinde ders üretimi, iç içe bağlam yeniden denemesiyle en çok 4 çağrı yapabiliyordu. Olağan temiz yol 1 Vision + 1 ders çağrısıdır. Tek mantıksal sorunun en kötü sınırı 2 + 3 = 5 çağrıdır. Öğrenci yeni bir istek başlatırsa bu ayrı bir ücretli işlem olarak kotaya sayılır.

## 6. Öğrenci açıklaması ve revizyonlar

- `POST /api/v1/vision/analyses/{analysis_id}/clarification`, gövde `{expected_revision, uncertainty_id, selection}` alır. `selection` bir alternatif kimliği, `recognized` (ilk okumayı onayla) veya `none` (hiçbiri) olabilir. Sağlayıcı çağrılmaz. Yazma mevcut `lesson_analyses/{id}` belgesinde ve tek Firestore işleminde yapılır: hesap silme işareti, sahiplik ve süre işlem içinde okunur, `expires_at` uzatılmaz. Eşzamanlı iki açıklamadan biri kazanır, diğeri 409 `stale_question_revision` alır. Aynı isteğin ağ yeniden denemesi aynı revizyonu döndürür.
- Seçilen alternatif yalnızca belirsizliğin bağlı olduğu öğede, tek geçen parçada uygulanır: ifade, seçenek, soru kökü veya şekil olgusu. `Correction` kaydı (özgün → düzeltilmiş, kaynak revizyon) tutulur ve ders bağlamına "öğrencinin onayladığı okuma" olarak girer. Bu bağımsız doğrulama değildir.
- `POST /lessons/generate` çözülemeyen soruda sağlayıcı çağrılmadan 409 `question_clarification_required` döner. İsteğe bağlı `expected_revision` alanı güncel revizyonla eşleşmezse 409 `stale_question_revision` döner. Ders kaydı kabul edilmiş revizyonu `source_analysis` içinde taşır. Etkileşimler, ipuçları ve benzer örnekler aynı kaydı kullanır.
- Yeni koleksiyon yoktur. Görsel baytı veya base64 Firestore'a yazılmaz (`normalized_preview_url` hariç tutulur).

## 7. Seçenek uzlaştırması

- Önce bağımsız sonuç belirlenir. Kaynakta tek bilinmeyenli tek bir "verilen" denklem varsa MathAI bunu çözer. Yoksa sağlayıcının önerdiği sonuç kullanılır ve köken `provider` olarak kaydedilir.
- Eşleşme yalnızca kesin eşdeğerlikle yapılır (`simplify(a − b) == 0`): 1/2 ↔ 0,5, √8 ↔ 2√2. En yakın değer seçilmez. Bağımsız sonuç ile önerilen sonuç çelişirse etiket değiştirilmez; doğrulama sınırlı düzeltme turunu tetikler.
- `VerificationResult.choice_match` alanının durumları: `matched`, `multiple_equivalent` (ilki sessizce seçilmez), `no_match` (yanlış etiket kaldırılır, sonuç etiketsiz gösterilir, ders başarısız sayılmaz), `choice_dependent`, `unsupported` (ör. etiketsiz seçenekler).
- MathAI artık problemi tanımlayan denklemi rollerden seçer. Seçenekteki veya öncüldeki denklem problemi tanımlamaz. Eski analizlerde önceki "=" içeren ifade kuralı korunur.
- **Önce çöz:** Amaç bir değer bulmaksa, seçenekler sayı veya ifadeyse ve kaynakta tek değişkenli tek denklem varsa (`solve_first_hidden`) seçenek değerleri ders bağlamına gönderilmez, yalnızca sayıları gönderilir. Etiketi MathAI sonradan belirler. Diğer durumlarda seçenekler korunur ve istem önce türetmeyi, sonra seçmeyi ister. Bu talimat bağımsızlığı garanti etmez. En güçlü bağımsızlık belirlenimci hesaplamadan gelir.

## 8. Bağlam sıkıştırma

Soru metni, ifadeler, seçenekler, öncüller, temel görsel olgu ve ilişkileri ile onaylanmış düzeltmeler karakter dilimlemesiyle kısaltılmaz. Yalnızca boşluk normalleşir. Sığmazsa mevcut bütçe denetimi `lesson_context_too_large` kurtarma hatası üretir. Bozulmuş bir soru gönderilmez. İsteğe bağlı açıklama metinleri (belirsizlik notları, dekoratif betimleme) sıkıştırılabilir.

## 9. Uyumluluk

- v1 API eklemelidir. `VisionAnalysis` için `source`, `revision` ve `integrity`; `VerificationResult` için `choice_match`; `GeneratedLesson` için `education_context`; `GenerateLessonRequest` için `expected_revision` eklendi. Mevcut alanların anlamı değişmedi.
- Eski analiz ve ders kayıtları okunabilir kalır. Bütünlük kararı olmayan eski analizde karar, sağlayıcı çağrılmadan yerinde hesaplanır (`revision_origin: legacy`). Eski serbest metin belirsizlikleri önemsiz sayılır, böylece eski kayıtlar yeni engellere takılmaz.
- LessonPlan v2 artık 2.1.0'dır. İsteğe bağlı `source_revision` ve `source_decision` alanları eklendi. 2.0.0 belgeleri geçerlidir ancak bu alanları taşıyamaz. Ders yalnızca çözülebilir bir karara dayanabilir. `verification.source_consistency`, bütünlük kararı varsa `partially_checked` olur: yapısal kaynak tutarlılığı denetlenmiştir, görselin doğru okunduğu kanıtlanmamıştır. Bilimsel, müfredat, yöntem ve pedagoji durumları değişmedi.
- Eğitim bağlamında öğrencinin profil hedefi `exam`, sorunun benzediği sınav türü ise `source_exam` (`inferred`) alanındadır. Eski derslere bugünkü profil geriye dönük yazılmaz.
- Vision tel şemasına sınırlı `SourceProposal` (soru sayısı, öncüller, bölgeler, en çok 8 yapılandırılmış belirsizlik) ve ilgili istem satırları eklendi. Model varsayılanları değişmedi. İstemin gerçek modelle etkisi **ölçülmedi**.

## Reddedilen yaklaşımlar

- Güven eşiği ile reddetme, her belirsizlikte öğrenciye sorma ve her soruda ikinci Vision çağrısı.
- Sağlayıcıya özyinelemeli ifade ağacı ürettirme: tel biçimi düz kalır, ağacı Python kurar.
- Görseli yeniden okuma için bulutta saklama ve OpenCV ya da OCR modeli ekleme.
- Ayrı bir soru veritabanı.
