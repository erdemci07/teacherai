# TA-009B kör öğretmen puanlaması

**Durum: beklemede.** Puanlanacak çıktı yok; ücretli ölçüm yapılmadı.

## Nasıl üretilir

`python -m scripts.evaluate_models matrix` ücretli koşusu iki dosya yazar. İkisi de Git dışında kalır:

- `evals/runs/matrix-<zaman>/blind.csv`: puanlanacak çıktılar. Her satırda rastgele bir kod, soru kimliği ve işlem (ders veya etkileşim) bulunur. Model adı, sağlayıcı ve reasoning düzeyi yoktur. Satırlar karıştırılmıştır.
- `evals/runs/matrix-<zaman>/blind_key.json`: kod → aday eşlemesi. Puanlama bitene kadar puanlayan öğretmenle paylaşılmaz.

Eşleme anahtarı puanlama dosyasıyla aynı klasörde durur. Puanlayana yalnız `blind.csv` verilir.

## Ölçek (1–5)

| Sütun | Anlam |
| --- | --- |
| `dogruluk_1_5` | Açıklama matematiksel ve bilimsel olarak doğru; istenen hedefe gidiyor. |
| `yontem_1_5` | Yöntem bu sınıf ve sınav düzeyine uygun. |
| `aciklik_1_5` | Adımlar açık ve sıralı; gereksiz uzun değil. |
| `turkce_1_5` | Türkçe doğal ve öğrenci diline uygun. |
| `cevabi_vermeme_1_5` | Yalnız etkileşim: ipucu cevabı söylemeden yönlendiriyor. |

`degerlendiren` sütununa puanlayanın kısa adı yazılır. `not` sütunu serbesttir.

## Birleştirme

Puanlanmış CSV aynı klasöre `blind_scored.csv` adıyla konur. `python -m scripts.evaluate_models matrix-score evals/runs/matrix-<zaman>` puanları eşleme anahtarıyla adaylara bağlar ve aday başına ortalamayı yazar. Sonuç karar kuralının 3.2 ve 5. maddelerinde kullanılır ([model seçimi](TA-009B-model-selection.md)).

Puanlar öğretmen onayı veya yetkili inceleme değildir. Bilgi kaydına ve `reviewers.json` dosyasına yazılmaz.
