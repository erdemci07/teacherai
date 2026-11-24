# Mobil öncelikli arayüz mimarisi (TA-006)

Durum: uygulandı (temel). Yerel Capacitor kabuğu, yerel izin akışları ve yerel Firebase Auth TA-016'ya aittir.

## İlkeler

- **Statik dışa aktarım korunur.** `next.config.ts` `output: 'export'` değişmedi; SSR, server action veya çalışma zamanı Next.js sunucusu yoktur. FastAPI arka ucu ayrıdır; sağlayıcı anahtarları yalnız arka uçtadır.
- **Aynı ders durumu, farklı düzen.** Görünüm değiştirmek (tahtayı büyütmek, yan yana düzene geçmek) yalnız sunum durumudur; yeni ders üretmez, istek veya sağlayıcı çağrısı yapmaz (`solve/LearningWorkspace.tsx`, test: `tests/learning-ui.test.ts`).
- **Fare/hover varsayılmaz.** Yeni stil dosyasında `:hover` yoktur; dokunma hedefleri en az 44 px'tir (`--ta-touch`).
- **Yalnız çalışan işlemler etkin.** Gezinme yalnız mevcut ekranları gösterir. FKB'de soru çözümü ve konu anlatımı devre dışı düğme olarak, planlandığı fazla birlikte görünür (`lib/learning.ts → subjectActions`).

## Tasarım belirteçleri (`app/design-system.css`)

| Belirteç | Açık | Koyu (`data-theme="dark"`) |
| --- | --- | --- |
| `--ta-cream` (zemin) | #f6f1e7 | #161917 |
| `--ta-surface` | #fffdf8 | #1f2320 |
| `--ta-charcoal` (metin) | #1f2421 | #ece8df |
| `--ta-green` (vurgu) | #2f6b4f | #84c8a0 |
| `--ta-muted` | #555d57 | #b7bcb5 |

- Kontrast (hesaplanan): yeşil metin/krem zemin ≈ 5,5:1, beyaz/yeşil düğme ≈ 6,2:1, kömür/krem ≈ 14:1 (WCAG AA metin eşiği 4,5:1). Gerçek cihazda ölçülmedi.
- Eski değişkenler (`--bg`, `--brand`, `--ink`, `--muted`) yeni paletle eşlenir; `var(--brand)` kullanan bileşenler doğal yeşile geçer.
- **Bilinen sınır:** eski çözüm ekranlarında doğrudan yazılmış mor/mavi renkler (globals.css, ~30 kullanım) henüz taşınmadı. Bu nedenle koyu tema sistem temasına göre kendiliğinden açılmaz; belirteçler hazırdır ve `:root[data-theme="dark"]` ile seçilir. Eski renkler taşındıkça otomatik koyu tema açılacaktır.
- Boşluk (`--ta-space-1…6`), yarıçap (`--ta-radius-*`), güvenli alan (`--ta-safe-*`) ve yazı tipi (`--ta-font`) belirteçleri tanımlıdır. Matematik: KaTeX blokları yatay kaydırılabilir, sayfa taşmaz.

## Düzen

| Cihaz | Gezinme | Öğrenme alanı |
| --- | --- | --- |
| Telefon (< 1024 px) | Alt gezinme (Ana sayfa, Konular, Soru çöz, Geçmiş, Panel), güvenli alan payıyla | Tek sütun; tahta "Tahtayı büyüt" ile tam ekran (`100dvh`), Esc ile kapanır |
| Tablet dikey | Alt gezinme | Tek sütun, büyütülebilir tahta |
| Tablet yatay (≥ 900 px, landscape) | Alt gezinme | Tahta ve etkileşim yan yana (`data-layout="split"`), tahta yapışkan |
| Masaüstü (≥ 1024 px) | Daraltılabilir kenar çubuğu (tercih `localStorage`'da) | ≥ 1200 px'te yan yana |

Alt gezinme ve kenar çubuğu yalnız oturum açık öğrenciye gösterilir. Çözüm ekranındaki yapışkan "Soruyu Çöz" çubuğu alt gezinmenin üstünde konumlanır.

## Capacitor hazırlığı

| Gereksinim | Uygulama |
| --- | --- |
| Görünüm alanı | `layout.tsx → viewport`: `viewport-fit=cover`, `interactive-widget=resizes-content`, tema rengi; yakınlaştırma kapatılmadı |
| Güvenli alan | `env(safe-area-inset-*)` üst başlıkta, alt gezinmede, tam ekran tahtada |
| Dinamik yükseklik | Tam ekran tahta `100vh` yedeğiyle `100dvh` |
| Ekran klavyesi | `interactive-widget=resizes-content`; giriş alanları sabit konumlu öğelerle örtülmez |
| Odak | `:focus-visible` halkası; büyütülen tahta `role="dialog"`, odak düğmeye taşınır |
| Kamera/dosya | Mevcut `capture="environment"` ve dosya seçici korunur (sözleşme testleri) |
| Yerel eklentiler | Kurulmadı. Mikrofon, kamera, bildirim ve yerel Firebase Auth bağdaştırıcıları TA-016 |

## Konu gözatma (`/konular`)

`GET /api/v1/curriculum/catalog`, `/programs/{id}/grades/{n}` ve `/resolve` uçlarını kullanır. Sınıf, öğrenci/mezun durumu, öğretim yılı ve sınav hedefi öğrencinin seçimidir (başlangıç değeri profilden). Resmî kazanım metni gösterilmez; resmî kod, başlık, PDF sayfası ve varsa "taslak betimleme" rozeti gösterilir.

## Bilimsel görsel sözleşmesi

`KnowledgeEntry.visuals` şu türleri temsil eder: denklem, türetme, geometri, koordinat grafiği, vektör ve serbest cisim diyagramı, devre, kimyasal denklem, molekül yapısı, etiketli yapı, süreç diyagramı, veri tablosu, deney grafiği. Bugün yalnız mevcut BoardPlanner/KaTeX/GraphView çizimi çalışır. Sağlayıcıdan gelen betik, HTML veya SVG çalıştırılmaz; yeni çizimler yapılandırılmış veriden güvenli SVG/Canvas ile TA-008–TA-014'te eklenecektir.

## Doğrulama

- Otomatik: başsız Edge + DevTools protokolü ile `/`, `/login`, `/register`, `/solve`, `/konular` (oturumsuz → `/login`), `/privacy`, `/about` sayfaları 320, 390, 768, 1024, 1440 px'te yatay taşma için ölçüldü (TA-006 raporu).
- Oturum gerektiren ekranlar (alt gezinme, kenar çubuğu, konu ağacı, gerçek dersle yan yana düzen) tarayıcıda **çalıştırılmadı**; Firebase yapılandırması olmadan oturum açılamıyor. Bunlar sunucu tarafı çizim testleri ve kaynak düzeyinde doğrulandı.
- Gerçek iOS/Android cihaz veya Capacitor kabuğunda test yapılmadı; masaüstü emülasyonu mobil uyumluluk kanıtı sayılmaz.
