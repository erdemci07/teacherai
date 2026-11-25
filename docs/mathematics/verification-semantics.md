# TA-008/TA-008B matematiksel doğrulama anlamları

Bu belge her durumun neyi kanıtladığını ve neyi kanıtlamadığını tanımlar. Boyutlar birbirinin kanıtı sayılmaz:
kaynak bütünlüğü, matematiksel model, hesap, adım doğruluğu, son hedef, müfredat uyumu, yöntem uygunluğu, sunum
tutarlılığı ve pedagojik kalite ayrı değerlendirilir.

## Durumlar

| Durum | Anlamı |
| --- | --- |
| `passed` | Belirtilen kapsamda belirlenimci ve kesin denetim başarılı. |
| `failed` | Kesin çelişki bulundu (ör. kök kaybı, yanlış aralık, tutarsız kısıtlar). |
| `partially_checked` | Bir bölüm denetlendi (ör. model değerleri metinde var ama ilişkiler kanıtlanmadı; genişletici dönüşüm). |
| `not_checked` | Bilinçli olarak dayanak yapılmadı (ör. yalnız görünüşe dayanan geometri olgusu). |
| `unsupported` | Denetleyici yok, çözücü tamamlanamadı, koşullu/parametreli sonuç veya zaman bütçesi aşıldı. Asla başarı sayılmaz. |

## Kapsam (`scope`)

| Kapsam | Anlamı |
| --- | --- |
| `exact` | Kesin sembolik/rasyonel sonuç (yaklaşık değer değil). |
| `universal` | Gerekçesi olan genel sonuç. TA-008B'de geometri bu kapsamı kullanmaz. |
| `model` | Temsil edilen kısıt sisteminin bütün çözümleri için (TA-008B). Öklid düzleminde gerçekleşebilirlik ayrıca kanıtlanmadı; doğrusal noktaların sırası bilinmiyorsa bütün sıralar ayrı durum olarak çözülür. |
| `configuration` | Tek bir yapılandırma için (genelleme değildir). TA-008'de kullanılmaz. |
| `sampled` | Örneklenmiş değerler (grafik noktaları). Kanıt değildir; yetkili iddia üretmez. |

## Önemli ayrımlar

- Bir önerilen kökün denklemi sağlaması tam denklem doğrulaması değildir: çözüm *kümesi* karşılaştırılır
  (`claimed_set_complete`, `missing_solutions`, `extraneous_or_wrong_claim`).
- Dönüşümler özgün tanım kümesinde karşılaştırılır: `equivalent` (geçti), `gains` (kısmi; adaylar özgün denklemde elenmeli),
  `loses`/`changed` (hata). Tehlike adları: `division_by_expression_with_zero`, `unknown_sign_multiplier`,
  `inequality_not_reversed`.
- Doğru aritmetik yanlış modeli doğrulamaz: sözel problemde `model_fidelity` en iyi `partially_checked`'tir.
- Geometride `target_determined` model kapsamındadır (temsil edilen kısıtların bütün çözümleri); `target_underdetermined`
  ve `target_ambiguous` hatadır; `inconsistent_constraints` ve `triangle_inequality_violated` tutarsız modeldir.
  Tutarlılık (çözüm var), varlık (Öklid düzleminde gerçekleşir), teklik (hedef tek değerli) ve ispat ayrı şeylerdir;
  TA-008B yalnız tutarlılık ve model içi tekliği hesaplar.
- Türevin sıfır olması ekstremum değildir (`no_extremum`); işaretli integral alan değildir; tek yönlü limit iki yönlü
  limit değildir; tanımsız noktalı aralıkta integral `improper`'dır.
- Trigonometride birim belirtilmeden açı yorumlanmaz (`angle_unit_unknown`); aralıksız denklem `periodic`
  (`partially_checked`) kalır.
- Uzmanlık raporu çekirdek MathAI durumunu yalnız zayıflatır; `verified` yalnız çekirdek denetimden gelir.

## TA-008B eklemeleri

### Tanım kümesi

Tanım kümesi sadeleştirmeden *önce*, özgün ayrıştırma ağacından toplanır (`features/mathematics/domain.py`): payda ≠ 0,
negatif üssün tabanı ≠ 0, `0^0` tanımsız (okul kuralı), çift kök ve paydası çift kesirli üs ≥ 0, logaritma argümanı > 0,
taban > 0 ve ≠ 1, `tan` için `cos ≠ 0`, `cot` için `sin ≠ 0`. `x/x = 1`, `0·(1/x) = 0`, `x⁻¹·x = 1` ve `x^0 = 1` gerçel
eksenin tamamını değil `ℝ∖{0}` kümesini verir. Karmaşık sayı kümesinde gerçel kısıtlar (kök içi ≥ 0, logaritma > 0)
uygulanmaz; yalnız payda/üs koşulları kalır. Çözüm kümesi, dönüşüm denetimi ve grafik aynı mekanizmayı kullanır.

### Küme bütünlüğü

- Gösterim sınırı (32 öğe, 16 aralık, 16 dışlama) aşılırsa kayıt kesilir ama `truncated = true` ve `exact = false`
  ile eksik olduğu açıkça işaretlenir; kesilmiş küme doğrulanmış tam küme sayılmaz.
- Çözücünün açık sonuç verememesi (`ConditionSet`, değerlendirilmemiş kesişim) kanıtlanmış boş küme değildir:
  `conditional`/`unsupported` döner. Boş küme yalnız çözücü `EmptySet` verdiğinde `empty`'dir.

### Dönüşümler ve durum ayrımı

| İlişki | Anlamı | Durum |
| --- | --- | --- |
| `equivalent` | Özgün tanım kümesinde aynı çözüm kümesi. | `passed` |
| `gains` | Genişletici dönüşüm (kare alma, değişkenli ifadeyle çarpma). | `partially_checked` |
| `eliminates` | Önceki adım genişlemişti; yalnız özgün denklemi sağlamayan adaylar elendi, özgün çözümlerin tamamı korundu. | `passed` |
| `loses` | Geçerli bir çözüm kayboldu. | `failed` (maddi) |
| `changed` | Küme başka bir kümeye dönüştü. | `failed` (maddi) |

Durum ayrımı: ardışık `case` adımları (her biri tek dal olabilir) veya aynı adımda dallara ayrılan birden çok denklem
birlikte değerlendirilir. Tek bir dalın daha az çözümü olması meşrudur; dalların özgün tanım kümesindeki birleşimi
önceki adımın (veya özgün denklemin) çözüm kümesine eşit olmalıdır (`case_split_complete`). Eksik dal
`case_branch_invalid` / `case_missing_or_invalid`'dir. Ayrımdan sonraki adımlar dal içinde denetlenir: bir dalın kümesini
korumalı, yalnız yabancı adayı elemeli veya dalları birleştirmelidir. Doğru son cevap geçersiz bir ara adımı geçerli
yapmaz.

### Çelişki sınıfları

| Sınıf | Örnek neden kodları | Sonuç |
| --- | --- | --- |
| Maddi çelişki | `missing_solutions`, `extraneous_or_wrong_claim`, `claimed_interval_differs`, `solution_lost`, `step_changed`, `division_by_expression_with_zero`, `inequality_not_reversed`, `case_branch_invalid`, `geometry_answer_mismatch`, `word_answer_mismatch`, `function_value_mismatch`, `extremum_mismatch`, `constant_value_mismatch`, `source_constraints_contradictory`, `no_extremum_of_requested_kind` | `MathCheck.material = true`; doğrulama `failed`, `contradiction = true`, `final_answer_verified = false`. Ders akışı yapılandırılmış geri bildirimle **tek** düzeltme turu çalıştırır ve yeniden denetler; çözülmezse ders reddedilir (`VerificationContradictionError`). |
| Eksik doğrulama | `unsupported`, `not_checked`, `claim_unparsed`, `value_meaning_unanchored`, `target_underdetermined`, `model_answer_disagreement` (hedef kimliği kaynağa bağlanamadı) | Maddi değildir; `verified` en çok `partially_verified` olur. Düzeltme turu tetiklenmez. |
| Pedagojik uyuşmazlık | Yöntem/sınıf düzeyi | MethodPolicy v2 ile ayrı ele alınır; matematik doğruluğu sayılmaz. |

Düzeltilmiş ders yalnız başarısız denetim kalmadıysa ve son cevap bağımsız doğrulandıysa kabul edilir: ya çekirdek son
cevap doğrulaması ya da uzmanlık raporunda cevap düzeyinde geçen bir denetim (`*_answer`, `claimed_solution_set`,
`claimed_inequality_set`). Maddi çelişkiler denetim listesi kesilmeden önce ayrıca tutulur (`material_failures`,
`material_count`); 64 denetim sınırı maddi başarısızlığı düşüremez.

### Hedef ↔ son cevap

Geometri hedefi (ör. `AC`) yalnız hedef etiketi soru metninde geçiyorsa AnswerTarget'a bağlı sayılır. Bağlıysa
uyuşmazlık maddi çelişkidir; bağlı değilse `model_answer_disagreement` (model mi cevap mı yanlış, belirlenemez)
kısmi kalır. Sözel problemde hedef yalnız istenen ifade modelin `objective` alanıyla aynıysa bağlıdır.
`f(x) = …` tanımlanıp `f(a)` istenirse hedef çarpım (`f·a`) sanılmaz; `f(a)` bağımsız hesaplanır.

### Hata yayılımı

Uzmanlık denetimi beklenmedik biçimde çökerse sonuç sessizce düşmez: `specialist_status = "unavailable"`, açıklayıcı
not ve uyarı döner (günlüğe yalnız hata türü yazılır). Zaman bütçesi işlemler *arasında* denetlenir ve tek bir SymPy
çağrısını kesmez; aşıldığında `specialist_status = "partial"` olur ve `verified` `partially_verified`'a iner. Kesin
koruma yalıtılmış işçinin dış zaman aşımıdır.
