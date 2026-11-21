# 8. sınıf (LGS) Matematik: yöntem politikası taslağı

Durum: **taslak** (`status: draft`, `authored_by: claude-draft`). Taslak hiçbir derste kısıtlama uygulamaz. Onay Erdem'e aittir.

Makine kaydı: [`apps/api/app/features/curriculum/data/lgs-matematik-8.json`](../../apps/api/app/features/curriculum/data/lgs-matematik-8.json). Şema: `features/education/curriculum.py`. Bir satırı onaylamak için kayıtta o politikanın şu alanları değiştirilir:

- `status: "approved"`
- `authored_by: "teacher"`
- `approved_by: "<onaylayan>"`

Kayıt doğrulayıcısı, onaylayanı olmayan onaylı kaydı reddeder.

## Program sürümü

Kazanımlar **MEB 2018 Matematik Dersi Öğretim Programı**'ndan (İlkokul ve Ortaokul 1–8) birebir alındı:

- Program sayfası: http://mufredat.meb.gov.tr/ProgramDetay.aspx?PID=329
- Sayfa aralığı: PDF s. 73–75, basılı s. 71–73
- Erişim tarihi: 21 Kasım 2026
- M.8.1.3.3'teki kök işareti PDF metin çıkarımında kayboldu; `a√b` olarak yazıldı.

**Doğrulanamadı:** 8. sınıfın 2026–2027 öğretim yılında hangi programla okutulduğu ve Türkiye Yüzyılı Maarif Modeli'nin 8. sınıf ve LGS için hangi yıldan itibaren geçerli olduğu. tymm.meb.gov.tr ana sayfası, `/surec` ve `/ogretim-programlari` sayfalarında bir geçiş takvimi bulunamadı. Maarif Modeli 8. sınıfa geçtiğinde kazanım kodları ve metinleri değişecektir. O zaman yeni program ayrı kayıtla eklenmelidir.

## Kazanımlar (kaynaklı)

Kayıtta 29 kazanım var, hepsinin `source_status` değeri `sourced`. Kazanımlar şu altı alt öğrenme alanından alındı:

- Çarpanlar ve Katlar (M.8.1.1)
- Üslü İfadeler (M.8.1.2)
- Kareköklü İfadeler (M.8.1.3)
- Cebirsel İfadeler ve Özdeşlikler (M.8.2.1)
- Doğrusal Denklemler (M.8.2.2)
- Eşitsizlikler (M.8.2.3)

Geometri, veri ve olasılık alanları bu dilimde yoktur.

## Konu nasıl belirlenir

Konu, sağlayıcının yazdığı `topic` etiketinden **alınmaz**. Kaynak ifadelerin yapısından belirlenimci olarak çıkarılır (`curriculum/registry.py: topic_of`):

| Kaynak | Konu |
| --- | --- |
| Tek değişkenli, birinci dereceden tek eşitlik | `dogrusal_denklemler` |
| Tek değişkenli, birinci dereceden tek eşitsizlik | `esitsizlikler` |
| Değişkensiz ifade, kök içeriyor | `karekoklu_ifadeler` |
| Değişkensiz ifade, üs içeriyor (kök yok) | `uslu_ifadeler` |
| Diğer (ikinci derece, çok değişken, belirsiz) | yok. Yöntem ve müfredat `not_checked` kalır. |

`carpanlar_ve_katlar` ve `cebirsel_ifadeler` için kazanım var ama yapısal konu tanıyıcısı yok. Bu yüzden bu iki konuda politika satırı da yazılmadı.

## Onaylanacak satırlar

Her satır ayrı onaylanır. "Yasak" sütunundaki işlemler, adım ifadelerinde veya açıklamada belirlenimci olarak tanınır (`CONSTRUCTS`). Örnekler: `\frac{d}{dx}`, `\log`, `\Delta`, "türev", "diskriminant".

| Kimlik | Konu | İzinli işlemler | Yasak işlemler ve gerekçe | Tercih edilen gösterimler | Kazanımlar | Onay |
| --- | --- | --- | --- | --- | --- | --- |
| `lgs8.genel` | bütün 8. sınıf konuları | — | türev, integral, limit, logaritma: ortaöğretim konuları. Trigonometrik fonksiyonlar programda yok. Karmaşık sayı: sayı kümesi gerçek sayılarla sınırlı (M.8.1.3.8). İkinci derece kök formülü ve diskriminant: denklemler birinci dereceden (M.8.2.2.1). | — | — | ☐ |
| `lgs8.uslu_ifadeler` | Üslü ifadeler | evaluate, rewrite, state_result, explain | — | üs kurallarıyla denk ifade; 10'un kuvvetleriyle çözümleme; bilimsel gösterim | M.8.1.2.1–5 | ☐ |
| `lgs8.karekoklu_ifadeler` | Kareköklü ifadeler | evaluate, rewrite, factor, state_result, explain | — | a√b biçimi; tam kare çarpanlara ayırma; kare modeli | M.8.1.3.1–8 | ☐ |
| `lgs8.dogrusal_denklemler` | Doğrusal denklemler | add/subtract/multiply/divide_both_sides, expand, isolate_variable, substitute, evaluate, rewrite, state_result, explain | square_both_sides: gerekmez ve yabancı kök üretebilir | terazi modeli; iki tarafa aynı işlem; tablo ve grafik | M.8.2.2.1 | ☐ |
| `lgs8.esitsizlikler` | Eşitsizlikler | add/subtract/multiply/divide_both_sides, isolate_variable, compare, evaluate, rewrite, state_result, explain | square_both_sides: yönü bozabilir ve gerekmez | sayı doğrusu; eşitsizlik yönü kuralı | M.8.2.3.2, M.8.2.3.3 | ☐ |

## Denetim anlamı

**`method`** şu durumlardan birini alır:

- `failed`: onaylı bir yasak işlem bir adımda bulundu. Adım ve neden yazılır, tek bir hedefli düzeltme turu yapılır.
- `passed`: bütün adımlar sunucu tarafından sınıflandırıldı ve hepsi konunun izinli listesinde.
- `partially_checked`: yasak işlem bulunmadı, ama bazı adımlar sınıflandırılamadı.
- `not_checked`: sınıf bilgisi yok, onaylı politika yok veya konu belirlenemedi.

**`curriculum`** şu durumlardan birini alır:

- `passed`: konu, onaylı politika üzerinden kaynaklı bir kazanıma eşlendi.
- `not_checked`: yukarıdaki eşleme kurulamadı.

Bu denetim matematiksel doğruluğu kanıtlamaz. Öğretim yönteminin bu öğrenciye uygunluğunu da (pedagoji) kanıtlamaz.
