# TA-008 matematiksel doğrulama anlamları

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
| `universal` | Modelin bütün kabul edilebilir yapılandırmaları için (kısıt sistemi bütün çözümleriyle çözüldü). |
| `configuration` | Tek bir yapılandırma için (genelleme değildir). TA-008'de kullanılmaz. |
| `sampled` | Örneklenmiş değerler (grafik noktaları). Kanıt değildir; yetkili iddia üretmez. |

## Önemli ayrımlar

- Bir önerilen kökün denklemi sağlaması tam denklem doğrulaması değildir: çözüm *kümesi* karşılaştırılır
  (`claimed_set_complete`, `missing_solutions`, `extraneous_or_wrong_claim`).
- Dönüşümler özgün tanım kümesinde karşılaştırılır: `equivalent` (geçti), `gains` (kısmi; adaylar özgün denklemde elenmeli),
  `loses`/`changed` (hata). Tehlike adları: `division_by_expression_with_zero`, `unknown_sign_multiplier`,
  `inequality_not_reversed`.
- Doğru aritmetik yanlış modeli doğrulamaz: sözel problemde `model_fidelity` en iyi `partially_checked`'tir.
- Geometride `target_determined` evrenseldir (modelin bütün çözümleri); `target_underdetermined` ve `target_ambiguous`
  hatadır; `inconsistent_constraints` ve `triangle_inequality_violated` tutarsız modeldir.
- Türevin sıfır olması ekstremum değildir (`no_extremum`); işaretli integral alan değildir; tek yönlü limit iki yönlü
  limit değildir; tanımsız noktalı aralıkta integral `improper`'dır.
- Trigonometride birim belirtilmeden açı yorumlanmaz (`angle_unit_unknown`); aralıksız denklem `periodic`
  (`partially_checked`) kalır.
- Uzmanlık raporu çekirdek MathAI durumunu yalnız zayıflatır; `verified` yalnız çekirdek denetimden gelir.
