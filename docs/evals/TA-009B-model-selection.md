# TA-009B model seçimi

**Durum: beklemede.** Gerçek ölçüm yapılmadı; varsayılan modeller değiştirilmedi.

Eksik ön koşullar (27 Kasım 2026):

- `evals/datasets/original-24.answers.json` yok. Yalnız şablonu var. Cevapları Erdem doldurur; kod ve ajan yazmaz.
- `evals/local/images/` içinde 29 görsel var. sha256 eşleşmesini koşucu her koşuda yeniden denetler.
- Bu oturumda tutar yazılarak verilmiş bütçe onayı yok.

Ön koşullar tamamlanınca önce kuru koşu yapılır, ardından onaylanan tutarla ücretli koşu:

```
python -m scripts.evaluate_models matrix --dry-run
python -m scripts.evaluate_models matrix --allow-paid --max-usd <onaylı USD> --max-calls <üst sınır> [--pack-images-to-anthropic]
```

Ham çıktılar `evals/runs/matrix-<zaman>/` altına yazılır ve Git dışında kalır. Bu belgeye yalnız özet tablo eklenir.

## Aday matrisi

| İşlem | Aday | Not |
| --- | --- | --- |
| Vision (iki kez; ikincisi yalnız Vision) | gpt-6-luna medium, gpt-6-luna low, gpt-6.1-terra low, claude-haiku-5-5, claude-sonnet-5-5 | Ders modeli sabit: varsayılan (gpt-5.6-terra) |
| Ders | gpt-5.6-terra, gpt-6.1-terra medium, gpt-6.2-sol low, claude-sonnet-5-5 | Vision sabit: varsayılan (gpt-4.1-mini) |
| Etkileşim | gpt-6-luna low, claude-haiku-5-5 | Sentetik smoke seti; ipucunda cevap sızıntısı ölçülür |

Anthropic Vision adayları yalnız `--pack-images-to-anthropic` bayrağıyla koşulur. Bu bayrak yalnız Erdem'in kendi soru görsellerini kapsar. Production izni (`TEACHERAI_ALLOW_STUDENT_IMAGES_TO_ANTHROPIC`) bu bayrakla açılmaz; öğrenci verisi kullanılmaz. Bayrak verilmezse bu adaylar "gizlilik kapısı kapalı" olarak atlanır.

Anthropic `thinking` parametresi değiştirilmedi. Katalogda Claude modellerinin `reasoning_efforts` alanı boştur; adaptör düşünme parametresi göndermez. Claude adayları bu nedenle düşünme kapalı ölçülür.

## Karar kuralı (koşudan önce yazıldı; değiştirilmez)

Koşucu bu bölümün sha256 özetini koddaki sabitle karşılaştırır (`scripts/eval_matrix.py`, `RULE_SHA256`). Özet uyuşmazsa ücretli koşu başlamaz.

<!-- karar-kurali:basla -->
1. **Geçerlilik kapıları.** Aday, aşağıdakilerin hepsini sağlamazsa seçilemez:
   - Paketteki bütün sorular koşuldu ve koşu bütçe nedeniyle durmadı.
   - Sağlayıcı çağrılarının en az %95'i `success` sonucuyla bitti.
   - Vision adayının iki koşusu, soruların en az %90'ında aynı bütünlük kararını ve aynı okuma puanlarını verdi. İkinci koşu yalnız Vision'dır; ders üretmez.
   - Etkileşim adayında ipucu cevap sızıntısı oranı 0 oldu.
2. **Birincil ölçüt: emin-yanlış oranı.** Netleştirme istemeden ve çekimser kalmadan, öğretmen anahtarından farklı şık seçilen soruların anahtarlı sorulara oranı (`confident_wrong_rate`). En düşük oran kazanır. Vision adayında oran, ders üreten ilk koşudan alınır.
3. **Eşitlik.** En iyiye 1 soru (1/24) veya daha az uzaklıktaki adaylar eşit sayılır. Eşitlik şu sırayla bozulur:
   1. öğretmen anahtarıyla cevap doğruluğu (yüksek),
   2. kör öğretmen puanı ortalaması (yüksek; yalnız ders ve etkileşim),
   3. soru başına tahmini USD (düşük),
   4. p95 gecikme (düşük).
4. **Netleştirme tavanı.** Netleştirme oranı 0,25'i aşan aday seçilemez. Çekimserlik emin-yanlış sayılmaz.
5. **Etkileşim.** Öğretmen anahtarı yoktur. Kapıları geçen adaylar arasında sıra: kör öğretmen puanı, USD, gecikme.
6. **Karar yok.** Hiçbir aday kapıları geçemezse varsayılan değişmez ve karar Erdem'e bırakılır. Model tahminle seçilmez. gpt-4.1-mini Vision ve etkileşim varsayılanı 14 Ocak 2027'de kapanır; bu tarihten önce Erdem'in kararı gerekir.
7. **Uygulama.** Kazanan aday varsayılan yapılmadan önce Erdem onaylar. Varsayılan değişikliği ayrı bir commit'tir; ölçüm özeti ve bu kuralın özeti commit mesajına yazılır.
<!-- karar-kurali:bitir -->

## Sonuçlar

Ölçüm yapılmadı.

## Gerileme koşusu

Tek komutla seçili varsayılan yapılandırma yeniden ölçülür ve son sonuçla farkı raporlanır:

```
python -m scripts.evaluate_models regress --dry-run
python -m scripts.evaluate_models regress --allow-paid --max-usd <onaylı USD> --max-calls <üst sınır>
```
