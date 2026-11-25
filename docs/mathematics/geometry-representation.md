# TA-008/TA-008B geometri temsili, kanıt zinciri ve teorem kaydı

Sözleşme: `apps/api/app/features/education/mathematics.py` (`GeometryModel`, `GeometryFact`, `Construction`,
`GeometryTarget`). Denetim: `features/mathematics/geometry.py`. Teorem kaydı: `features/mathematics/theorems.py`.

## Olgu kökenleri ve kanıt zinciri (TA-008B)

Sağlayıcının `origin` etiketi tek başına doğruluk kurmaz. Sunucu her olguyu sınıflar; yalnız kabul edilen olgular
kısıt olur ve tahtada da yalnız sunucu kararı gösterilir (`MathematicsReport.geometry_facts`).

| Köken (sağlayıcı) | Sunucunun kabul koşulu | Kanıt sınıfı | Ret nedeni |
| --- | --- | --- | --- |
| `stated` | `evidence` soru metninde birebir geçer **ve** olgunun noktalarını/değerini içerir | `source_text` | `provider_proposed` |
| `marked` | Kaynakta şekil var (`has_geometry_figure`/`has_diagram`) | `diagram_interpreted` | `provider_proposed` |
| `derived` | `premises` kabul edilmiş olgulardır, `rule` desteklenen bir kuraldır, kural yerel olarak uygulanabilir ve bağımlılık grafiğinde döngü yoktur | `validated_derivation` | `unsupported_derivation`, `missing_premise`, `rule_not_applicable`, `circular_derivation` |
| `construction` | Olgu geçerli bir yardımcı çizimin `establishes` listesindedir ve çizim türünün tanımından izler | `construction_defined` | `construction_overreach` |
| `visual_uncertain` | hiçbir zaman | — | `visual_fact_not_given` |

Ek retler: tekrarlı/çakışık noktalı nesne (`degenerate_object`), çember, merkez ve değme noktası kurulmamış teğet
(`tangent_preconditions_unmet`). Reddedilen olgu hiçbir sonucu etkilemez.

Desteklenen türetme kuralları: `triangle_angle_sum`, `isosceles_base_angles`, `pythagorean` (dik açı *aynı üçgende* ve
değerler tutarlı olmalı), `similar_aa`, `midpoint_halves`. Kuralın adının geçmesi yetmez; öncüllerin yerel olarak kuralı
sağlaması gerekir.

Sınır: metin görselden AI ile okunmuş olabilir. `source_text` olgunun *okunan metinde* geçtiğini kanıtlar; görselin
doğru okunduğunu kanıtlamaz (TA-003). `diagram_interpreted` de görselden AI yorumudur.

Şekil varsayılan olarak `schematic: true`'dur: görünen orantılar veri değildir. Tahtada "ölçekli değil" uyarısı gösterilir.

## Kısıt anlamları (TA-008B)

- `collinear`: üç nokta aynı doğrudadır; **sıra bildirmez**. Bütün sıralar (en çok 27 durum) ayrı çözülür; hedef
  durumlarda farklıysa `ambiguous` döner (ör. AB = 2, AC = 5 ⇒ BC ∈ {3, 7}).
- `point_on_segment`: açık aradalık (B, AC parçası üzerinde ⇒ AB + BC = AC).
- Tekrarlı nokta ve aynı adlı iki nokta yozlaşmış nesnedir.
- Sonuç kapsamı `model`'dir: temsil edilen kısıtların bütün çözümleri. Tutarlılık, Öklid düzleminde varlık, teklik ve
  ispat ayrı şeylerdir; yalnız ilk ikisinin model içi biçimi hesaplanır.
- Hedef değer yalnız hedef etiketi soru metninde geçiyorsa AnswerTarget'a bağlıdır ve son cevapla karşılaştırılır
  (`geometry_answer_mismatch` maddi çelişkidir); bağlanamazsa sonuç kısmidir.
- Soru metninden alınan olgular kendi aralarında çelişirse `source_constraints_contradictory` (maddi) döner.

## Olgu türleri

`segment_length`, `angle_measure`, `equal_segments`, `equal_angles`, `parallel`, `perpendicular`, `right_angle`,
`collinear`, `midpoint`, `point_on_segment`, `triangle`, `polygon`, `circle`, `point_on_circle`, `tangent`, `similar`,
`congruent`, `coordinate`, `area`. Benzerlik/eşlikte `points` ve `other` sırası karşılıklı köşeleri verir.

## Doğrulama

Kabul edilmiş olgular sembolik kısıtlara çevrilir (`L_AB`, `a_ABC` derece) ve önkoşulu karşılanan teoremler denklem ekler; sistem
SymPy ile bütün çözümleriyle çözülür (en çok 14 sembol, 40 denklem):

| Sonuç | Anlamı |
| --- | --- |
| `determined` | Hedef bütün durumlarda tek değerli (kapsam `model`) |
| `underdetermined` | Hedef serbest; bilgi eksik |
| `ambiguous` | Birden çok değer |
| `inconsistent` | Çözüm yok veya üçgen eşitsizliği ihlali |
| `unsupported` | Sistem çok büyük veya çözücü tamamlanamadı |

Ayrıca: köşe eşlemesi uyuşmazlığı (`correspondence_mismatch`), çakışık noktalar, yardımcı çizimin tanımından izlemeyen
olgu (`construction_overreach`), açıklamada adı geçen ama önkoşulu olmayan teorem (`theorem_preconditions_unmet`).

Rastgele bir uygun şekil üretilmez; sayısal örnekleme kanıt sayılmaz.

## Teorem kaydı

| Teorem | Yürütülür | Önkoşul |
| --- | --- | --- |
| Üçgen iç açıları toplamı | evet | üçgen olgusu |
| Dış açı | evet (açı toplamı üzerinden) | kenar uzatma |
| Pisagor | evet | verilen/işaretli dik açı |
| Pisagor karşıtı | evet (adlandırma) | üç kenar |
| Üçgen eşitsizliği | evet | üç kenar |
| İkizkenar | evet (eş açı/kenar olgusuyla) | verilen/işaretli eşitlik |
| Eşlik, benzerlik | evet | açık köşe eşlemesi |
| Teğet–yarıçap | evet | verilen teğet |
| Koordinat uzaklığı, orta nokta | evet | verilen koordinatlar |
| Açıortay, paralel açılar, dörtgen özellikleri, çevre açı | **hayır** (yalnız tanınır) | — |

Evrensel otomatik teorem ispatı yapılmaz; eksik ispatın denetlenen ve denetlenmeyen kısımları ayrı raporlanır.

## Yardımcı çizimler (TA-008B)

`altitude`, `segment`, `extension`, `parallel_line`, `midpoint`, `radius`, `perpendicular`, `angle_bisector`. Her çizim
başvurduğu noktaları, yeni noktaları, tanımı gereği kurduğu olguları (`establishes`), kanıt gerektiren iddiaları ve
amacını taşır. Yeni nokta modelde zaten varsa çizim geçersizdir.

| Çizim | Tanımından izleyen olgular | İzlemeyen (reddedilir) |
| --- | --- | --- |
| `altitude` A'dan BC'ye, ayak H | H'de dik açı (A,H,B veya A,H,C); AH ⟂ BC; H, B, C doğrusal | H'nin BC *parçası* üzerinde olması (geniş açılı üçgende uzantıdadır); BH = HC |
| `perpendicular` P'den AB'ye | H'de dik açı; H, A, B doğrusal | aradalık, uzunluk |
| `midpoint` AB'nin, M | M orta noktadır | başka eşitlikler |
| `extension` AB'nin uzantısı | doğrusallık | uzunluk |
| `parallel_line` P'den AB'ye | paralellik | açı eşitliği (ayrı türetme gerekir) |
| `radius` O merkezli | P çember üzerindedir | teğet |
| `angle_bisector` B'den | iki açının eşitliği | açıortay teoremi oranları |
| `segment` | hiçbir şey | her şey |

Aşan olgular reddedilir ve hesaba girmez; çizimin geçerli kısmı korunur. Reddedilen bir çizim olgusu (ör. BH = HC)
hedefi belirleyemez: `geo_construction_contamination` vakası bunu sınar.
