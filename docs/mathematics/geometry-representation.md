# TA-008 geometri temsili ve teorem kaydı

Sözleşme: `apps/api/app/features/education/mathematics.py` (`GeometryModel`, `GeometryFact`, `Construction`,
`GeometryTarget`). Denetim: `features/mathematics/geometry.py`. Teorem kaydı: `features/mathematics/theorems.py`.

## Olgu kökenleri

| Köken | Dayanak olur mu? | Örnek |
| --- | --- | --- |
| `stated` | evet | "AB = 3 cm" metinde |
| `marked` | evet | Dik açı işareti, eşitlik çizgisi |
| `derived` | evet | Önceki adımdan türetilmiş |
| `construction` | yalnız çizimin `establishes` listesindeyse | Yükseklik → dik açı |
| `visual_uncertain` | **hayır** | Dik *görünen* açı, eşit *görünen* kenar |

Şekil varsayılan olarak `schematic: true`'dur: görünen orantılar veri değildir. Tahtada "ölçekli değil" uyarısı gösterilir.

## Olgu türleri

`segment_length`, `angle_measure`, `equal_segments`, `equal_angles`, `parallel`, `perpendicular`, `right_angle`,
`collinear`, `midpoint`, `point_on_segment`, `triangle`, `polygon`, `circle`, `point_on_circle`, `tangent`, `similar`,
`congruent`, `coordinate`, `area`. Benzerlik/eşlikte `points` ve `other` sırası karşılıklı köşeleri verir.

## Doğrulama

Olgular sembolik kısıtlara çevrilir (`L_AB`, `a_ABC` derece) ve önkoşulu karşılanan teoremler denklem ekler; sistem
SymPy ile bütün çözümleriyle çözülür (en çok 14 sembol, 40 denklem):

| Sonuç | Anlamı |
| --- | --- |
| `determined` | Hedef tek değerli (evrensel) |
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

## Yardımcı çizimler

`altitude`, `segment`, `extension`, `parallel_line`, `midpoint`, `radius`, `perpendicular`, `angle_bisector`. Her çizim
başvurduğu noktaları, yeni noktaları, tanımı gereği kurduğu olguları (`establishes`), kanıt gerektiren iddiaları ve amacını
taşır. Çizim türünün kuramayacağı olgu (ör. yükseklikten "BH = HC") reddedilir.
