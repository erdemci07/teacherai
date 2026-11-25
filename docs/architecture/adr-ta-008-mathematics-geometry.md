# ADR TA-008: İleri matematik ve geometri zekâsı

- Durum: kabul edildi (TA-008, 2026-11-25)
- Önceki kararlar: [ADR TA-004](adr-ta-004-reasoning-verification.md), [ADR TA-007](adr-ta-007-expert-teacher-intelligence.md)
- İlgili: [yetenek matrisi](../mathematics/TA-008-capability-matrix.md), [doğrulama anlamları](../mathematics/verification-semantics.md),
  [geometri temsili ve teorem kaydı](../mathematics/geometry-representation.md), [strateji seçimi](../mathematics/strategy-selection.md),
  [TA-007 denetim düzeltmeleri](../governance/TA-008-audit-corrections.md)

## Bağlam

TA-004'ün MathAI'si tek değişkenli gerçel denklem, eşitsizlik ve istenen hedefi denetliyordu; geometri, sözel problem,
trigonometri, olasılık ve kalkülüs için belirlenimci denetim yoktu. TA-008'in amacı ikinci, uyumsuz bir motor kurmak
değil, aynı yalıtılmış işçiyi ve aynı ifade ayrıştırıcısını kullanan sınırlı bir uzmanlık katmanı eklemektir.

## Karar

### 1. Ayrılmış sorumluluklar

| Aşama | Modül | Not |
| --- | --- | --- |
| Problem temsili | `integrity.expression` (AST), `education.mathematics` (WordProblemModel, GeometryModel) | Model sağlayıcıdan *önerilir*; sunucu doğrular |
| Konu tanıma | `curriculum.topics` (75 konu) | Yalnız AST yapısı kesin; sözcük eşlemesi zayıf |
| İstenen hedef | `reasoning.target`, `mathai.targets` (TA-004) | Değişmedi; ara değer hedef sayılmaz |
| Modelleme | `mathematics.word_problems`, `mathematics.geometry` | Model sadakati ayrı boyut |
| Strateji | `mathematics.strategies` (+ MethodPolicy v2) | Öneri; kısıt yalnız onaylı politikadan |
| Hesap | `mathematics.sets/functions/trig/probability/calculus` | Kesin aritmetik, açık sayı kümesi |
| Bağımsız doğrulama | `mathematics.transforms/specialist` | Durumu yalnız zayıflatır |
| Müfredat/yöntem | `curriculum.methods` (TA-007) | Değişmedi |
| Açıklama | Sağlayıcı (geçit üzerinden, ek çağrı yok) | |
| Sunum | `board.planner` (sayı doğrusu, kesintili grafik, şema uyarısı) | Değerler doğrulanmış temsilden |

### 2. Güvenli sembolik hesap

- İfadeler yalnız `integrity.expression` ağacından kurulur (`mathematics.expr`: `sin/cos/tan/cot/ln/log` eklendi; bütçeler
  korundu). `eval`/`exec`/`sympify`/`parse_expr` yoktur; sağlayıcı kodu çalıştırılmaz.
- SymPy kullanan bütün uzmanlık modülleri yalnız MathAI'nin yalıtılmış işçisinde, mevcut `verify` çağrısının içinde
  çalışır (yeni süreç, yeni çağrı veya yeni eşzamanlılık yok). Rapor 2,5 sn iç zaman bütçesiyle sınırlıdır; aşılırsa
  `time_budget` ile `unsupported` olur. İşçi zaman aşımı (8 sn) ve eşzamanlılık sınırı değişmedi.
- `ConditionSet`, değerlendirilmemiş kesişim, periyodik `ImageSet` veya kapalı biçimsiz integral *başarılı doğrulama
  değildir*.

### 3. Doğrulama durumları

`MathCheck.status` ∈ `passed | failed | partially_checked | not_checked | unsupported`, `scope` ∈
`exact | universal | configuration | sampled | not_applicable`. Uzmanlık raporu `VerificationResult.mathematics`
alanındadır ve çekirdek durumu yalnız **zayıflatabilir** (`verified` → `partially_verified`). Ayrıntı:
[doğrulama anlamları](../mathematics/verification-semantics.md).

### 4. Yapılandırılmış model önerisi

`LessonContent.mathematical_model` (isteğe bağlı): sağlayıcı yanıtında kısıtsız düz tiplerle (`MathematicalModelResponse`;
Anthropic izdüşümü gerektirmez) gelir, sunucuda özgün sözleşmeyle doğrulanır; geçersiz model dersi düşürmez, yalnız atılır.
Ders isteğinin şeması ve istemi bu yüzden değişti; altın istek fikstürü yeniden üretildi (`test_gateway_golden --write`).

### 5. Üretim öncesi ipucu

`mathematics.guidance` (SymPy'siz, süreç içinde) kaynak ifadelerden tanım kümesi koşullarını çıkarır ve yalnız koşul varsa
isteme `mathematics_hints` olarak ekler. Bu doğrulama değildir.

### 6. Alternatif yollar

İkinci derece denklem için çarpanlara ayırma (yalnız rasyonel köklerde), tam kareye tamamlama ve kök formülü
belirlenimci üretilir ve özgün çözüm kümesine karşı denetlenir. Ek sağlayıcı çağrısı yoktur.

## Gerçek ve hedef

- **Gerçek:** Ders akışında (canlı) denklem/eşitsizlik çözüm kümesi, adım denkliği, tanım kümesi, fonksiyon grafiği
  kesintisi, ikinci derece alternatifleri, sağlayıcı modeli varsa geometri ve sözel problem denetimi çalışır.
  Trigonometri/olasılık/kalkülüs çözücüleri çevrimdışı ve regresyonda çalışır; canlı yolda yalnız ifade ayrışırsa ve
  ilgili kalıp varsa kullanılır. Bağımsız öğretmen anahtarıyla hiçbir konu değerlendirilmedi.
- **Hedef:** TA-009 fizik bu çözümleri (denklem sistemleri, aralıklar, grafik, koordinat, sayısal/sembolik denetim)
  yeniden kullanır; öğretmen onaylı stratejiler MethodPolicy v2 ile kısıta dönüşür.

## Sonuçlar

- Sağlayıcı yanıt şeması genişledi (geriye uyumlu, isteğe bağlı alan). Eski dersler okunabilir.
- MathAI işçisinde hesap süresi ders başına ≈ 0,5–0,7 sn arttı (yerel ölçüm); başlatma süresi baskındır.
- Olağan yolda sağlayıcı çağrı sayısı değişmedi; ödemeli gömme veya çift sağlayıcı denetimi yoktur.
