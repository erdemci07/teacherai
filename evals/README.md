# Model değerlendirme

Bu dizin, mevcut modeller (`gpt-4.1-mini`) ile aday model (`gpt-6-luna`) arasında Vision ve Interaction için tekrar kullanılabilir bir karşılaştırma altyapısı içerir.

> **Durum (20 Kasım 2026):** 100 soruluk özgün öğretmen veri seti **henüz yoktur**. `datasets/original-100.jsonl` boş bir şablondur. 10 öğelik `datasets/smoke.jsonl` tamamen sentetiktir ve yalnızca hattın çalıştığını sınar. Model kalitesini ölçmez. Bu görevde ücretli koşu yapılmadı. Tam set ve insan değerlendirmesi olmadan model geçişi onaylanmaz.

## Komutlar

```sh
python -m scripts.evaluate_models                     # tüm veri setlerini ve fikstürleri doğrular, çağrı yapmaz
python -m scripts.evaluate_models validate evals/datasets/original-100.jsonl
python -m scripts.generate_smoke_set                  # sentetik smoke setini deterministik olarak yeniden üretir
python -m scripts.evaluate_models run --provider fake --reasoning-effort none low medium   # hattı sınar, ücretsiz
```

Ücretli koşu yalnızca proje sahibi bütçeyi onayladıktan sonra yapılır. Aşağıdaki değerler örnektir. 100 öğe, iki işlem ve üç reasoning düzeyiyle yaklaşık 1100 çağrı planlanır. Önce `--max-usd` olmadan sahte sağlayıcıyla ön tahmin çıktısına bakın.

```sh
python -m scripts.evaluate_models run --allow-paid --max-usd 20 --max-calls 1200 \
  --dataset evals/datasets/original-100.jsonl --candidate gpt-6-luna --reasoning-effort none low medium
```

- `--allow-paid`, `--max-usd` ve `--max-calls` birlikte verilmelidir. Ayrıca her model için `TEACHERAI_PRICING_VERSION` ve `TEACHERAI_MODEL_PRICES` doğrulanmış fiyatla tanımlanmalıdır. Biri eksikse koşu başlamaz.
- Koşu öncesinde üst maliyet yazdırılır. Tahmin her iki modeli, her işlemi, her reasoning düzeyini, görsel ve metin girişi tahminini (`--image-input-tokens`, varsayılan 1600), işlem çıktı sınırını ve etkileşimin izinli tek bağlam tekrarını kapsar. Tahmin `--max-usd` değerini aşarsa ya da hesaplanamazsa koşu başlamaz.
- Her çağrıdan önce kalan bütçe ve çağrı adedi denetlenir. Gerçekleşen tahmini maliyet sınıra ulaşınca kalan çağrılar yapılmaz.
- **Bu tahmin kesin bir harcama tavanı değildir.** Görsel ve giriş token sayıları tahmindir. Kesin sınır için OpenAI projesindeki bütçe ve limit ayarı kullanılmalıdır.
- Modelin desteklemediği reasoning düzeyi sağlayıcıya gönderilmeden reddedilir (`apps/api/app/core/operations.py`).

Çıktılar `eval-results/<zaman>/` altına yazılır ve Git dışında tutulur:

- `raw.jsonl`: istek başına ham sonuç
- `summary.md`: karşılaştırma özeti
- `rubric.csv`: insan değerlendirmesi için 1–5 ölçekli boş rubrik

## Otomatik metrikler

| Metrik | Tanım |
| --- | --- |
| Geçerli soru doğruluğu | `is_valid_question` kararı beklenenle aynı mı. Yanıt alınamayan öğe yanlış sayılır. |
| İfade eşdeğerliği | Çıkarılan ilk denklemin farkı, beklenen denklemin farkıyla sabit katsayıyla orantılı mı (SymPy, güvenli MathAI ayrıştırıcısı) |
| Kök kümesi eşleşmesi | Çıkarılan denklemin gerçel çözüm kümesi beklenen kümeyle aynı mı |
| Şema geçerliliği | Yanıt şemayı ve anlamsal doğrulamayı geçti mi |
| Sonuç dağılımı | Gateway sonuç sınıfları (`completed`, `incomplete_*`, `refusal`, `invalid_output`, `timeout`, `provider_error`) |
| Cevap sızıntısı | İpucunda `forbidden_in_hint` değerlerinden biri bağımsız sayı ya da `x = değer` olarak geçiyor mu (deterministik) |
| Gecikme | p50 ve p95 (ms) |
| Token ve maliyet | Giriş, çıkış ve akıl yürütme tokenları, yapılandırılmış fiyata göre tahmini USD |

Türkçe pedagoji kalitesi otomatik puanlanmaz. `rubric.csv` dosyasında pedagoji, açıklık, cevabı vermeme ve Türkçe doğallık 1–5 ölçeğiyle insan tarafından puanlanır.

## Karar kuralı (ilk taslak)

Aday model, **tam özgün sette** aşağıdaki koşulların hepsini sağlarsa *geçişe aday* sayılır:

1. Geçerli soru doğruluğu ve ifade eşdeğerliğinde mevcut modelden en çok 2 puan geride.
2. Cevap sızıntısı oranı ile refusal ve incomplete oranları mevcut modelden yüksek değil.
3. p95 gecikme mevcut modelin en çok 1,5 katı.

Bu eşikler ilk taslaktır. Son kararı proje sahibi ve öğretmen incelemesi verir. Sentetik smoke sonuçları bu kurala girdi olamaz. Geçiş işlem bazında, ortam değişkeniyle (`OPENAI_VISION_MODEL`, `OPENAI_INTERACTION_MODEL`) ve geri alınabilir biçimde yapılır.

## 100 soruluk özgün setin hazırlanması (öğretmen ve proje sahibi için)

1. **Kaynak ve telif:** Yalnızca öğretmenin kendi yazdığı (`original_author`) ya da hakkı açıkça devredilmiş (`teacher_contributed`) sorular kullanılır. ÖSYM, yayınevi veya kaynağı bilinmeyen sorular doğrulayıcı tarafından reddedilir. Her öğe için `license` (ör. “Proje içi değerlendirme için kullanım izni”) ve `author` doldurulur.
2. **Kapsam:** Konu dağılımı gerçek kullanıma benzemelidir: birinci ve ikinci dereceden denklemler, mutlak değer, kesirli ve köklü ifadeler, birkaç geometri ya da grafik sorusu ve en az 10 geçersiz görsel (matematik dışı, eksik ya da okunaksız).
3. **Çekim koşulları:** Telefonla, gerçek defter ve kitap sayfasında, farklı ışık ve açılarla çekilmelidir. Görselde kişisel veri (isim, okul, yüz) bulunmamalıdır. Gerekirse görsel kırpılır.
4. **Çift etiketleme:** Her soru iki öğretmen tarafından bağımsız olarak etiketlenir: `expected_expressions`, `expected_solutions` ve `forbidden_in_hint`. Uyuşmazlıklar üçüncü bir kişiyle çözülür ve uyum oranı kaydedilir.
5. **Biçim:** Her satır `schema/eval-item.schema.json` şemasına uyan bir JSON nesnesidir. Görsel yolu veri seti dosyasına görelidir. Doğrulayıcı beklenen çözümlerin beklenen denklemi gerçekten sağladığını da denetler.
6. **Doğrulama:** `python -m scripts.evaluate_models validate evals/datasets/original-100.jsonl` hatasız geçmeden koşu yapılmaz.

Örnek satır:

```json
{"id": "ogretmen-001", "source": "original_author", "license": "Proje içi değerlendirme için kullanım izni", "author": "[öğretmen adı]", "created_at": "2026-12-01", "image": "original/ogretmen-001.jpg", "is_valid_math_question": true, "question_text": "2x + 5 = 11 ise x kaçtır?", "topic": "Birinci dereceden denklem", "variable": "x", "expected_expressions": ["2x + 5 = 11"], "expected_solutions": ["3"], "forbidden_in_hint": ["3", "x = 3"]}
```
