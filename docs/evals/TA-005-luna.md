# TA-005 · gpt-4.1-mini → gpt-6-luna değerlendirmesi

**Gerçek model değerlendirmesi yapılmadı.** Bu oturumda proje sahibinden tutar belirten bir bütçe onayı gelmedi. Ayrıca görseller (`evals/local/images/`) ve öğretmen cevap anahtarı (`evals/datasets/original-24.answers.json`) henüz yok. Hiçbir sağlayıcı çağrısı yapılmadı.

Bu nedenle aşağıdaki sorular **yanıtsız** kalıyor:

- Hangi model hangi tuzakta hata yapıyor?
- Geçiş güvenli mi?
- gpt-6-luna için hangi reasoning effort önerilmeli?

Sentetik ve sahte sağlayıcılı testler bu soruları yanıtlamaz.

## Doğrulanan model bilgileri (resmî belgeler, 21 Kasım 2026)

| Model | Girdi / önbellekli girdi / çıktı (USD, 1M token) | Not |
| --- | --- | --- |
| gpt-4.1-mini | 0,40 / 0,10 / 1,60 | `gpt-4.1-mini-2025-04-14` için kapanış: **14 Ocak 2027**. Önerilen yerine geçen model gpt-6-luna. |
| gpt-6-luna | 0,10 / 0,01 / 0,50 | Görsel girdi ve structured outputs destekleniyor. `reasoning.effort` değerleri: none, low, medium (varsayılan), high, xhigh, max. |
| gpt-5.6-terra (ders) | 2,00 / 0,20 / 12,00 | Mevcut ders modeli |

Kaynaklar:

- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/deprecations
- https://developers.openai.com/api/docs/models/gpt-6-luna

Değerler `evals/config/models.json` dosyasındadır, kodda yer almaz.

## Kuru koşu çıktısı

```
$ python -m scripts.evaluate_models pack --dry-run --model gpt-4.1-mini
Plan: 0 soru, en çok 0 çağrı, üst tahmin ≈0.0000 USD (Vision gpt-4.1-mini, ders gpt-5.6-terra). Görseli eksik: B01 … P06 (24).
Bütün paket (24 görsel) gelirse üst tahmin ≈15.7271 USD, en çok 120 çağrı.
Öğretmen anahtarı: bekleniyor (cevap doğruluğu ölçülmeyecek)
Kuru koşu: sağlayıcı çağrısı yapılmadı.

$ python -m scripts.evaluate_models pack --dry-run --model gpt-6-luna
… Bütün paket (24 görsel) gelirse üst tahmin ≈15.4509 USD, en çok 120 çağrı.
```

Üst tahmin bilerek kötümserdir. Her çağrının tam çıktı sınırını kullandığını (Vision 4096, ders 16384 token) ve her sorunun azami çağrı sayısına ulaştığını (2 Vision + 3 ders) varsayar.

Tahminin büyük bölümü `gpt-5.6-terra` ders çağrılarından gelir. Fizik, kimya ve biyolojideki 18 soru ders üretimine yönlendirilmediği (`unsupported_subject`) için gerçek harcamanın tahminden belirgin biçimde düşük olması beklenir. Bu beklenti ölçülmedi.

## Onaydan sonra çalıştırılacak komutlar

Ön koşullar:

1. 29 görsel `evals/local/images/` altına konur. Dosya adı soru kimliğiyle başlar (ör. `M03_kok.png`). Ardından `python -m scripts.answer_key manifest` çalıştırılır.
2. `evals/datasets/original-24.answers.template.json` doldurulur ve `original-24.answers.json` adıyla kaydedilir. Ardından `python -m scripts.answer_key validate` çalıştırılır.
3. Değerlendirme için ayrı bir OpenAI projesi açılır, harcama limiti konur ve `OPENAI_API_KEY` ortamda tanımlanır.

Önerilen sıra (her biri ayrı onay ister):

```
python -m scripts.evaluate_models pack --allow-paid --max-usd <USD> --max-calls 120 --model gpt-4.1-mini
python -m scripts.evaluate_models pack --allow-paid --max-usd <USD> --max-calls 120 --model gpt-6-luna --reasoning-effort none
python -m scripts.evaluate_models pack --allow-paid --max-usd <USD> --max-calls 120 --model gpt-6-luna --reasoning-effort low
python -m scripts.evaluate_models pack --allow-paid --max-usd <USD> --max-calls 120 --model gpt-6-luna --reasoning-effort medium
```

Ders modeli her koşuda mevcut ayardaki modeldir (`--lesson-model` verilmez).

Tavan çalışma sırasında uygulanır:

- Her sorudan önce soru başına üst tahminle kalan bütçe denetlenir. Aşılacaksa koşu durur ve çıkış kodu 4 olur.
- Çağrı sayısı da aynı şekilde denetlenir.

Ham çıktılar `evals/runs/<zaman>/` altına yazılır ve Git dışında kalır. Özet bu belgeye işlenir.

## Ölçülecekler

| Ölçüt | Tanım |
| --- | --- |
| Okuma doğruluğu | Paket `reading` referansına göre, alan türüyle: kök kapsamı, üs, kesir çizgisi, diğer ifade, seçenekler. Grafik ekseni için yapısal referans olmadığından "ölçülmedi" yazılır. |
| Cevap doğruluğu | Yalnızca öğretmen anahtarına göre. Türetilmiş cevap ölçüt yapılmaz. |
| Netleştirme ve çekimserlik | `clarification_required` oranı ve seçilen etiket olmayan soru oranı |
| Çağrı ve sonuç | Soru başına sağlayıcı çağrısı. `completed` / `invalid_output` / `refusal` / `incomplete_*` dağılımı. |
| Maliyet ve gecikme | Soru başına tahmini USD (gateway `ai_usage`). p50 ve p95 gecikme. |
| Tuzak dökümü | Öğretmen anahtarındaki `trap_tags` alanına göre yanlış cevaplar |
