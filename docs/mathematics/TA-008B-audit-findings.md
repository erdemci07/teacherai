# TA-008B denetim bulguları

Her bulgu kod değiştirilmeden önce TA-008 tabanında (`3a6a719`) yeniden üretilmeye çalışıldı. Sınıflar:
**yeniden üretildi**, **kısmen**, **üretilmedi** (davranış zaten doğruydu) ve **mevcut koruma** (başka bir katman
zaten engelliyordu). Üretilmeyen veya mevcut korumayla karşılanan durumda doğru kod değiştirilmedi; regresyon
testi eklendi. Doğrulanmış bir kusuru gizlemek için hiçbir beklenen test sonucu değiştirilmedi. Bilinçli olarak
güçlendirilen davranışlar için değişen eski beklentiler §"Değişen TA-008 beklentileri" bölümünde listelenmiştir.

Yeniden üretim betiği taban ağaçta süreç içinde çalıştırıldı. Ölçüm yalnız bu geliştirme makinesindedir.

## Özet

| No | Spesifikasyon | Bulgu | Taban sonucu | Sınıf |
| --- | --- | --- | --- | --- |
| F1 | §4 | Sadeleştirme tanım kümesini genişletiyor | `x/x = 1`, `0·(1/x) = 0`, `x⁻¹·x = 1`, `x⁰ = 1` → bütün ℝ | Yeniden üretildi |
| F2 | §5 | Küme gösterimi sessizce kesiliyor | 32 öğeden sonrası işaretsiz atılıyordu (kod incelemesi) | Kısmen (inceleme ile) |
| F3 | §6 | Meşru durum ayrımı ve yabancı kök elemesi başarısız sayılıyor | Doğru `\|x−2\| = 4` ve `√(x+2) = x` dersleri `failed` | Yeniden üretildi |
| F4 | §7 | Sağlayıcının `stated`/`derived` etiketi olgu kuruyor | Kaynak metni olmadan AC = 5 `determined`; kanıtsız benzerlik kabul | Yeniden üretildi |
| F5 | §8 | Yardımcı çizim aşan olguyla sonucu kirletiyor | Yükseklik "H, BC parçası üzerinde" kuruyor; ayak uzantıda olabilir | Yeniden üretildi |
| F6 | §9 | Doğrusal = arada; yozlaşmış nesne; teğet ön koşulu | Doğrusal A, B, C; AB = 2, AC = 5 → yalnız BC = 7 `determined` (doğrusu {3, 7}); çembersiz teğet ve AAB üçgeni kabul | Yeniden üretildi |
| F7 | §10 | Teoremin yerel olmayan uygulanışı, döngüsel kanıt | Teorem denetimi yerel (mevcut koruma); türetme kaydı yoktu | Kısmen |
| F8 | §11 | Geometri hedefi son cevapla karşılaştırılmıyor | Model AC = 5, cevap AC = 7 → çelişki yok | Yeniden üretildi |
| F9 | §12 | Sözel problem: kısıt ezme, hedef ↔ cevap, değer anlamı | `2n = 7` tam sayı + pozitif → 3,5 kabul | Yeniden üretildi |
| F10 | §13 | Uzmanlık çelişkisi düzeltme akışını tetiklemiyor | Yalnız `verified → partially_verified`; çözüm kümesi dışı alanlar hiç | Yeniden üretildi |
| F11 | §14 | Uzmanlık istisnası sessizce yutuluyor | `except Exception: return result` | Yeniden üretildi |
| F12 | §14 | `checks[:64]` maddi başarısızlığı düşürebiliyor | Kesme sırası ekleme sırası | Kısmen (inceleme ile) |
| F13 | §15 | `f(3)` hedefi `f·3` çarpımı sanılıyor | Hedef türü `product`; `f(3) = 8` yanlış cevabı yakalanmıyor | Yeniden üretildi |
| F14 | §18 | Grafikte delik/asimptot ayrımı yok; doğrulanmış parçalar kullanılmıyor | Tahta denklem dışlamalarını grafiğe uyguluyor | Yeniden üretildi |
| F15 | §19 | Tahta reddedilen olguyu "verilen" gösteriyor | Etiket sağlayıcı kökeninden | Yeniden üretildi |
| F16 | — (TA-008B sırasında) | Alternatif yol üretimi rasyonel denklemde çöküyor | `PolynomialError` → denklem analizi `analysis_unsupported` | Yeniden üretildi |
| F17 | §20 | İşçi süresi yalnız toplam/başlatma olarak ölçülüyor | Çekirdek/uzmanlık/serileştirme ayrımı yok | Yeniden üretildi (ölçüm eksikliği) |

## Ayrıntılar

### F1 — Özgün tanım kümesi (§4)

- **Sorun:** `mathematics.expr.build` SymPy ifadesini kurarken otomatik sadeleştirir (`x/x → 1`, `0·(1/x) → 0`,
  `x⁻¹·x → 1`, `x⁰ → 1`). Tanım kümesi sadeleşmiş ifadeden (`continuous_domain`) hesaplandığı için `x = 0` kayboluyordu.
- **Yeniden üretim:** dört denklem tabanda `kind = all` (bütün ℝ). `(x²−1)/(x−1)`, `(x²−4)/(x−2) = 4`, logaritma ve iç içe
  kök durumları zaten doğruydu (mevcut koruma: SymPy bu ifadeleri sadeleştirmez).
- **Kök neden:** tanım kümesinin kaynağı sadeleşmiş nesneydi.
- **Düzeltme:** `features/mathematics/domain.py` koşulları özgün ayrıştırma ağacından toplar (payda, negatif/sıfır üs,
  çift kök, kesirli üs, logaritma argümanı ve tabanı, `tan`/`cot`). `sets.solve_equation`, `solve_inequality`,
  `transforms.compare`, `functions.analyze` ve `functions.evaluate` aynı mekanizmayı kullanır; SymPy yalnız işçide çalışır.
  Karmaşık kümede gerçel kısıtlar uygulanmaz. Görünüm koşulları (`conditions`) taşır.
- **Regresyon:** `test_simplification_never_widens_the_original_domain`, `test_domain_conditions_are_collected_from_the_unsimplified_tree`,
  `test_complex_domain_has_no_real_restrictions`; derlem `dom_self_division`, `dom_zero_times_reciprocal`, `dom_negative_power`,
  `dom_zero_power`, `dom_cancelled_root_excluded`, `dom_complex_no_real_restriction`.
- **Çalışma zamanı:** `x/x = 1` → `(−∞, 0) ∪ (0, ∞)`, dışlama `0`, koşul `x ≠ 0`.
- **Sınır:** `tan(x) = tan(x)` gibi periyodik dışlamalı kümeler `unsupported` kalır (dürüst).

### F2 — Küme bütünlüğü (§5)

- **Sorun:** `sets.view` öğe/aralık listesini sınırda kesiyordu ama kaydı `exact` bırakıyordu.
- **Düzeltme:** `truncated = true`, `exact = false`; dışlama listesi de işaretlenir. Kesilmiş küme sayı doğrusuna
  çizilmez (tahta yalnız `exact` kümeyi çizer).
- **Mevcut koruma:** çözücünün açık sonuç verememesi (`ConditionSet`) zaten `conditional`; doğal sayı kümesi yalnız
  açık `domain` parametresiyle seçilir; `x⁵ + x + 3 = 0` için `CRootOf` sonucu kesindir, kusur değildir. Karmaşık kümede
  `x² = −1` tabanda da `{−i, i}` idi (üretilmedi); karmaşık yol TA-008B'de ortak AST tanım kümesine taşındı ve gerçel
  kısıt uygulamadığı `1/x = x` ile sınanır.
- **Regresyon:** `test_large_solution_lists_are_marked_truncated_not_silently_cut`.

### F3 — Dönüşümler ve durum ayrımı (§6)

- **Sorun:** (a) Çekirdek, her biri tek dal içeren ardışık `case` adımlarını ayrı ayrı önceki kümeyle karşılaştırıp
  `solution_lost` veriyordu. (b) Kare almadan sonra yabancı kökün elenmesi (`(x−2)(x+1) = 0 → x = 2`) kayıp sayılıyordu.
  (c) Uzmanlık raporu aynı adımdaki iki dalı ikili karşılaştırıyordu. Sonuç: doğru ders `failed` → düzeltme → red.
- **Yeniden üretim:** tabanda doğru `|x − 2| = 4` (iki ardışık durum adımı) ve `√(x + 2) = x` dersleri `failed`
  (performans ölçümünde de görülür).
- **Mevcut koruma:** `x² = x → x = 1` (değişkene bölme), negatifle çarpmada yön, işaretsiz çarpan ve genişleten dönüşüm
  zaten doğru sınıflanıyordu; değiştirilmedi.
- **Düzeltme:** `transforms.compare` yeni `eliminates` ilişkisi (yalnız önceki adım genişlemişse ve özgün çözümlerin
  tamamı korunuyorsa). Çekirdek `_step_checks` ardışık durum adımlarını gruplar, dalların birleşimini önceki *veya*
  özgün kümeyle karşılaştırır, ayrımdan sonra her adımı bir dalın içinde denetler (`_branch_step`). Uzmanlık raporu aynı
  kuralı uygular (`_split_check`).
- **Regresyon:** `test_case_analysis_is_judged_by_branch_union`, `test_extraneous_elimination_after_squaring_is_not_a_loss`;
  derlem `alg_extraneous_elimination`, `alg_lost_root_not_elimination`; mevcut `test_absolute_value_multiple_solutions`.
- **Sınır:** ayrımdan sonra dal içi adımlar yalnız küme düzeyinde denetlenir; dal koşulunun (ör. `x ≥ 2`) adımda
  yazılı olup olmadığı denetlenmez.

### F4 — Geometri kanıt zinciri (§7)

- **Sorun:** sağlayıcının `origin = "stated"` etiketi kaynakta bulunmasa da olgu kuruyordu; `derived` olgu öncülsüz
  ve kuralsız kabul ediliyordu.
- **Yeniden üretim:** soru metni olmadan Pisagor modeli `determined [5]`; kanıtsız `similar` olgusu kısıt oldu.
- **Düzeltme:** `GeometryFact.evidence/premises/rule`; `geometry.Source(text, has_figure)`; sınıflandırma
  (`source_text`, `diagram_interpreted`, `validated_derivation`, `construction_defined`) ve ret nedenleri
  (`provider_proposed`, `unsupported_derivation`, `missing_premise`, `rule_not_applicable`, `circular_derivation`).
  Yalnız kabul edilmiş olgular kısıt olur. İstem `evidence/premises/rule` alanlarını ister; golden istek yeniden üretildi.
- **Regresyon:** derlem `geo_no_source_provider_label`, `geo_fabricated_evidence`, `geo_marked_without_figure`,
  `geo_underived_similarity`, `geo_circular_derivation`, `geo_isosceles`.
- **Sınır:** metin görselden AI ile okunmuş olabilir; `source_text` görselin doğru okunduğunu kanıtlamaz (TA-003).

### F5 — Yardımcı çizimler (§8)

- **Sorun:** yükseklik "ayak BC *parçası* üzerinde" olgusunu kuruyordu (geniş açılı üçgende ayak uzantıdadır). Aşan
  olgu reddedilse de çizim desenleri gevşekti.
- **Yeniden üretim:** tabanda `BH = HC` çizimin `establishes` listesindeyken BH = 5 hesaplanabiliyordu.
- **Düzeltme:** çizim desenleri (yükseklik: dik açı, diklik, doğrusallık; aradalık yok), yeni noktanın modelde
  olmaması, aşan olguların reddi ve geçerli kısmın korunması.
- **Regresyon:** derlem `geo_construction_contamination`, `geo_altitude_valid`, `geo_construction_overreach`.

### F6 — Kısıt sağlamlığı (§9)

- **Sorun:** `collinear` tek bir nokta sırası varsayıyordu; A, B, C doğrusal, AB = 2, AC = 5 iken tabanda BC yalnız 7
  (`determined`) çıktı, oysa sıra bilinmediğinden BC ∈ {3, 7}'dir (yanlış teklik). Çembersiz teğet
  `theorem_preconditions_met`, tekrarlı noktalı (AAB) üçgen kabul ediliyordu.
- **Düzeltme:** doğrusal noktaların sırası bilinmez; bütün sıralar (≤ 27 durum) ayrı çözülür ve sonuç birleştirilir
  (`ambiguous` / `determined` / `inconsistent`). `point_on_segment` açık aradalıktır. `degenerate_object`,
  `tangent_preconditions_unmet`. Kapsam `universal` yerine `model`.
- **Regresyon:** derlem `geo_collinear_order_unknown`, `geo_between_explicit`, `geo_tangent_preconditions`, `geo_repeated_points`.
- **Sınır:** Öklid düzleminde gerçekleşebilirlik (varlık) kanıtlanmaz; yalnız kısıt sisteminin tutarlılığı ve model içi teklik.

### F7 — Yerel teorem uygulaması ve döngüsel kanıt (§10)

- **Mevcut koruma:** teorem denetimi (Pisagor için dik açının *aynı üçgende* olması) tabanda yereldi.
- **Kısmen:** türetilmiş olgu kaydı olmadığından döngüsel türetme ifade edilemiyordu. TA-008B türetme grafiğini
  doğrular (öncüllerin kabulü, kuralın yerel uygulanabilirliği, döngü).
- **Regresyon:** `geo_pythagoras_wrong_triangle`, `geo_circular_derivation`.

### F8 — Geometri hedefi ↔ son cevap (§11)

- **Sorun:** belirlenen hedef değer son cevapla karşılaştırılmıyordu.
- **Düzeltme:** `specialist._answer_check`; hedef etiketi soru metninde geçiyorsa bağlı sayılır ve uyuşmazlık maddi
  çelişkidir (`geometry_answer_mismatch`); bağlanamıyorsa `model_answer_disagreement` (kısmi, maddi değil).
- **Regresyon:** `test_wrong_geometry_answer_is_detected_corrected_once_rechecked_and_drawn`,
  `test_unresolved_geometry_contradiction_is_rejected_after_one_correction` (OpenAI ve Anthropic yolları).

### F9 — Sözel problemler (§12)

- **Sorun:** aynı sembolün ikinci kısıtı birincisini eziyordu (sözlük); hedef son cevapla karşılaştırılmıyordu; sayının
  metinde geçmesi anlamı bağlıyormuş gibi raporlanıyordu; toplanan birimler denetlenmiyordu.
- **Düzeltme:** kısıtlar küme olarak birlikte uygulanır; `evidence` alıntısı (`values_anchored_relations_unverified`)
  ile yalnız sayı eşleşmesi (`value_meaning_unanchored`) ayrılır; `unit_mismatch`; hedef ↔ cevap (bağlıysa
  `word_answer_mismatch`, değilse `model_answer_disagreement`).
- **Regresyon:** derlem `word_two_constraints_same_symbol`, `word_value_unanchored`, `word_value_anchored`, `word_unit_mismatch`;
  `test_word_answer_mismatch_without_bound_target_is_not_material`.
- **Sınır:** ilişkilerin soruya sadakati otomatik kanıtlanmaz; `model_fidelity` hiçbir zaman `passed` değildir.

### F10 — Çelişki sınıfları (§13)

- **Mevcut koruma:** çekirdek son cevap çelişkisi (`x² = x → x = 1`) tabanda `failed` ve düzeltmeyi tetikliyordu.
- **Sorun:** uzmanlık raporundaki çelişki yalnız `solution_set`/`inequality` alanlarında ve yalnız
  `verified → partially_verified` zayıflatmasıydı; yanlış geometri/sözel/f(a) cevabı düzeltmeyi hiç tetiklemiyordu.
- **Düzeltme:** `MathCheck.material`, `MATERIAL_REASONS`; `MathAIService.verify` maddi çelişkide `failed`,
  `contradiction`, `final_answer_verified = false` ve `mathematics_specialist` denetimi ekler. `LessonService`
  yapılandırılmış geri bildirim (`correction_feedback`) gönderir; düzeltilmiş ders yalnız başarısız denetim kalmadıysa
  ve son cevap bağımsız doğrulandıysa (`correction_resolved`) kabul edilir. Pedagojik uyuşmazlık MethodPolicy v2'de kalır.
- **Regresyon:** `test_missing_root_is_material_and_feedback_is_structured`, `test_valid_lesson_makes_exactly_one_provider_call`,
  `test_unsupported_model_stays_unsupported_without_extra_call`, `test_noncontradictory_partial_checks_never_become_material`.

### F11–F12 — Hata yayılımı (§14)

- **F11 düzeltme:** uzmanlık çökmesi `specialist_status = "unavailable"`, not ve uyarı; günlükte yalnız hata türü.
  Çekirdek kanıtı ayrı olduğundan çekirdek durumu korunur. Zaman bütçesi aşımı `partial` ve `verified → partially_verified`.
- **F12 düzeltme:** maddi başarısızlıklar kesmeden önce `material_failures`/`material_count` içinde tutulur; kesmede
  maddi ve başarısız denetimler öne alınır.
- **Regresyon:** `test_specialist_crash_is_reported_as_unavailable_not_hidden`, `test_material_failure_survives_check_truncation`.

### F13 — Fonksiyon değeri ve dar çalışma zamanı dağıtımı (§15)

- **Sorun:** `f(x) = 2x + 1 ise f(3)` hedefi çarpım (`f·3`) olarak okunuyor, yanlış `f(3) = 8` yakalanmıyordu.
- **Düzeltme:** uzmanlık raporu `f(x) = …` tanımını ve `f(a)` isteğini tanır, `functions.evaluate` ile bağımsız hesaplar
  (`function_value_mismatch` maddi). İkinci derece `y = f(x)` ve en büyük/en küçük hedefi için tepe noktası; değişkensiz
  trigonometrik istenen ifade (radyan) kesin hesaplanır.
- **Çevrimdışı kalanlar (gerekçe):** bileşke/ters fonksiyon, işaret aralıkları, kesişimler, trigonometrik aralık denklemi,
  sayma, olasılık, istatistik, limit, türev, belirsiz/belirli integral ve alan. Bunlar için AnswerTarget'ta yapısal hedef
  türü yoktur; hedef yalnız sözcükle tanınabilir ve yanlış eşleme yanlış "doğrulandı" üretebilirdi. Derece işareti (`°`)
  ayrıştırıcıda yoktur.
- **Regresyon:** `test_function_evaluation_target_is_not_read_as_a_product`.

### F14 — Grafik süreksizliği (§18)

- **Sorun:** delik (kaldırılabilir) ve düşey asimptot ayrılmıyor; uzmanlık raporunun doğrulanmış parçaları tahtaya
  gitmiyor; tahta denklem dışlamalarını fonksiyon grafiğine uyguluyordu. Çekirdek `analyze_function` rasyonel/köklü
  fonksiyonda hata verdiğinden grafik çizilmiyordu (mevcut koruma: yanlış grafik yerine grafik yok).
- **Düzeltme:** `functions.analyze` tek yanlı limitlerle delik `(x, limit)` ve asimptot ayırır; açık uç noktada da
  (ör. `ln x`, `x = 0`) asimptot. Rapor parçaları, örnek noktaları (tanımsız noktalar dışlanarak), delikleri ve
  asimptotları taşır; `GraphData.segments/holes/asymptotes`; `GraphView` parça sınırında böler, delik açık daire, asimptot
  kesikli çizgi, kapalı uç dolu nokta; çok büyük değer dikey birleştirme çizgisi oluşturmaz.
- **Regresyon:** `test_discontinuities_are_classified_for_rendering`, `test_board_graph_uses_verified_segments_and_excludes_undefined_points`;
  derlem `fn_hole_vs_asymptote`, `fn_reciprocal_asymptote`, `fn_log_open_endpoint`, `fn_sqrt_closed_endpoint`;
  `tests/ta008b-math-board.test.ts`.

### F15 — Tahta tutarlılığı (§19)

- **Düzeltme:** `MathematicsReport.geometry_facts` (sunucu kararı ve kanıt sınıfı/ret nedeni); tahta etiketi bu karardan
  gelir ("metinde verilen", "şekilde işaretli (görselden okundu)", "kullanılmadı: kaynakta bulunamadı"…). Şematik uyarısı
  korunur; son cevap işareti `final_answer_verified` ile tutarlıdır.
- **Regresyon:** `test_unsupported_model_stays_unsupported_without_extra_call`, `test_wrong_geometry_answer_is_detected_…`.

### F16 — Alternatif yol çökmesi

- **Sorun:** `x²` içeren her denklemde `alternatives.quadratic` çağrılıyor, rasyonel denklemde `PolynomialError` bütün
  denklem analizini `analysis_unsupported` yapıyordu.
- **Düzeltme:** yalnız polinom denklem; payda temizlenip tanım kümesi kaybedilmez.
- **Regresyon:** `test_rational_equation_does_not_break_the_specialist_through_alternatives`.

### F17 — MathAI güvenilirliği (§20)

- **Düzeltme:** işçi zarfı içe aktarma, çekirdek, uzmanlık ve serileştirme sürelerini taşır (`IsolatedMathAI.last_phases`;
  `last_timing` sözleşmesi değişmedi). Zaman aşımı, eşzamanlılık ve bellek sınırları değiştirilmedi. Ölçüm:
  [TA-008B performans karşılaştırması](TA-008B-performance.md).
- **Yinelenen ayrıştırma:** uzmanlık raporu kaynak ifadeleri yeniden ayrıştırır. cProfile ölçümünde (üç tipik ders)
  `integrity.expression.parse` 126 çağrıda uzmanlık süresinin yaklaşık %1,5'iydi; SymPy çözümü baskındır. Bu yüzden
  önbellek eklenmedi (gereksiz altyapı eklenmez).

## Değişen TA-008 beklentileri

Yalnız bilinçli güçlendirme nedeniyle; hiçbiri bir kusuru gizlemek için değil:

| Vaka/test | TA-008 | TA-008B | Neden |
| --- | --- | --- | --- |
| Geometri derlem vakaları (`geo_pythagorean_marked`, `geo_angle_sum`, `geo_impossible_triangle`, `geo_mismatched_similarity`, `geo_underdetermined`, `geo_coordinate_distance`, `geo_isosceles`) | Kaynak metni olmadan | Aynı beklenen sonuç; girdiye soru metni ve alıntı eklendi | F4: kaynaksız etiket artık olgu kurmaz. Kaynaksız biçim ayrı vaka olarak (`geo_no_source_provider_label`) ret bekler. |
| `geo_construction_overreach` | `construction_defined` + `construction_overreach` | yalnız `construction_overreach` | F5: yüksekliğin "ayak parça üzerinde" olgusu tanımdan izlemez. Geçerli yükseklik `geo_altitude_valid` ile ayrıca sınanır. |
| `test_provider_model_is_validated_and_invalid_model_is_dropped` | Yük `evidence/premises/rule` taşımıyordu | Alanlar açıkça `null`/boş | Katı yapılandırılmış çıktı şeması yeni alanları zorunlu kılar. |
| Sözel derlem `fidelity` nedeni | `values_grounded_relations_unverified` | `value_meaning_unanchored` / `values_anchored_relations_unverified` | F9: sayı eşleşmesi anlam bağlamaz. |
