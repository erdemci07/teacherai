# TA-007 değerlendirme hazırlığı

Bu belge ölçüm *yapılmadığını* ve hangi girdilerin hazır olduğunu kaydeder. TA-007'de ücretli çağrı yapılmadı; doğruluk iddiası yoktur.

## Girdiler

| Öğe | Durum | Kaynak |
| --- | --- | --- |
| 24 özgün soru görseli | 24/24 yerel (Git dışı) | `Codex_29_gorsel_cevapsiz.zip`, `python -m scripts.eval_import import` |
| OCR varyantları | 5 (M01_light_blur, M01_missing_expression, B01_light_blur, C04_low_contrast, P02_slight_rotation) | Aynı paket; `evals/ocr_variants/manifest.json` |
| Manifest | ad + sha256 + soru kimliği + tür | `evals/datasets/original-24.images.json` |
| Bağımsız öğretmen cevap anahtarı | **0/24** | `evals/datasets/original-24.answers.json` yok; şablon hazır |
| Branş dengesi | 6/6/6/6 | soru paketi |

## Güvenli içe aktarma (`scripts/eval_import.py`)

Arşiv çıkarılmadan denetlenir: mutlak/Windows yolu, `..`, sembolik bağ, şifreli giriş, izinli yol listesi, giriş sayısı (≤ 64), dosya (≤ 8 MB) ve toplam (≤ 96 MB) boyut, sıkıştırma oranı (≤ 60, zip bombası), PNG imzası/IHDR boyutu/IEND, manifest ↔ içerik sha256, paketteki 24 kimlikle birebir eşleşme, varyantların özgün soruya bağlanması, soru kayıtlarında cevap alanı bulunmaması. Yazma yalnız denetimden sonra ve yeniden kurulan adla `evals/local/images` içine yapılır.

## Ayrım ve sızıntı

- Soru kayıtları (`sorular.jsonl`) cevap alanı taşımaz; içe aktarma bunu denetler. Depoya soru metni kopyalanmadı (paket fikstürü zaten vardır).
- Varyantlar ayrı örnek değildir: `eval_pack.plan` yalnız özgün görselleri koşu sayar, varyantları özgün sorunun altında `variants` olarak taşır (TA-007 düzeltmesi; önceden 29 ayrı koşu sayılırdı).
- Değerlendirme verisi alıştırma havuzundan ve ders bağlamından ayrıdır: `python -m scripts.dataset_manifest --check`.
- Cevap anahtarı modelden, çözümden veya varyantlardan türetilmez.

## Ölçüm boyutları

| Boyut | Durum |
| --- | --- |
| Görsel okuma (kaynak bütünlüğü) | görseller hazır; ücretli koşu onayı gerekli |
| İstenen cevap doğruluğu | öğretmen anahtarı gerekli |
| OCR dayanıklılığı | varyantlar hazır; anahtar gerekli |
| Yöntem uygunluğu | insan değerlendirmesi (onaylı politika 0) |
| Müfredat uyumu | çevrimdışı ölçülebilir (çözümleme + eşleme) — model gerektirmez |
| Açıklama/tahta tutarlılığı | kısmi (TA-004 blok kontrolleri) |
| Öğrenme etkisi | TA-012/TA-013 |

`python -m scripts.evaluate_models readiness` çağrı yapmadan güncel durumu yazar. Ücretli koşu yalnız proje sahibinin onayıyla: `python -m scripts.evaluate_models run --allow-paid --max-usd … --max-calls …`.
