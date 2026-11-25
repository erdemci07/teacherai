# TA-008B MathAI performans karşılaştırması (TA-008 tabanına göre)

Bu ölçüm **yalnız bu geliştirme iş istasyonundadır**; bulut kapasitesi veya üretim gecikmesi iddiası değildir. Zaman
aşımı (8 sn), eşzamanlılık (`max_processes` = CPU sayısı), kuyruk ve bellek sınırları **değiştirilmedi**.

## Ortam

| Öğe | Değer |
| --- | --- |
| İşletim sistemi | Windows 11 (10.0.26100), Intel64 Family 6 Model 142, 8 mantıksal çekirdek |
| Python / SymPy | 3.12.16 / 1.14.0 |
| Taban | `3a6a719` (TA-008, ayrı git çalışma ağacı) |
| Ölçülen | `ta-008b` çalışma ağacı (bu dal) |
| Yöntem | `IsolatedMathAI.verify` (gerçek alt süreç), 11 ders planı × 5 tekrar, ısınma koşusu sonrası; sonra 8 iş parçacığıyla eşzamanlı patlama. İki ağaç sırayla, aynı makinede, başka yük yokken ölçüldü. |

Ders planları: doğrusal (doğru/yanlış), ikinci derece (tam/eksik kök), mutlak değer (ardışık durum adımları), rasyonel
(sadeleşen kök), köklü (kare alma + eleme), x'e bölme, `x/x = 1`, delikli fonksiyon grafiği, yapılandırılmış geometri.

## Sonuç

| Ölçü | TA-008 | TA-008B |
| --- | --- | --- |
| Uçtan uca ortanca (ms) | 2287 | 2283 |
| Uçtan uca p95 (ms) | 2805 | 3072 |
| En yavaş (ms) | 2841 | 3137 |
| Başlatma ortanca / p95 (ms) | 1804 / 1921 | 1848 / 1950 |
| Hesaplama ortanca / p95 (ms) | 466 / 1030 | 476 / 1163 |
| Zaman aşımı | 0 | 0 |
| `unsupported` sonuçlu plan | 3 | 2 |
| 8 eşzamanlı istek: toplam süre (ms) | 4772 | 4527 |
| 8 eşzamanlı istek: p95 (ms) | 4767 | 4522 |

TA-008B işçi içi fazlar (ortanca, ms): içe aktarma 1582, çekirdek doğrulama 105, uzmanlık raporu 367. Serileştirme yalnız
`reconcile_verify` işleminde ölçülür (bu ölçümde `verify` kullanıldı). Başlatma süresinin büyük bölümü yorumlayıcı ve
SymPy/Pydantic içe aktarmasıdır; hesaplama değil.

### Plan bazında

| Plan | TA-008 durum | TA-008B durum | TA-008 ortanca (ms) | TA-008B ortanca (ms) | TA-008B hesaplama (ms) |
| --- | --- | --- | --- | --- | --- |
| doğrusal (doğru) | verified | verified | 2289 | 2315 | 465 |
| doğrusal (yanlış) | failed | failed | 2271 | 2251 | 466 |
| ikinci derece (tam) | verified | verified | 2260 | 1970 | 200 |
| ikinci derece (eksik kök) | failed | failed | 2193 | 2205 | 410 |
| mutlak değer (doğru durum ayrımı) | **failed** | verified | 2617 | 2084 | 200 |
| rasyonel (sadeleşen kök cevap) | failed | failed | 2474 | 2607 | 691 |
| köklü (doğru eleme) | **failed** | verified | 2814 | 3075 | 1167 |
| x'e bölme | failed | failed | 2413 | 2429 | 495 |
| `x/x = 1`, cevap `x = 1` | unsupported | failed (eksik çözüm: ℝ∖{0}) | 2184 | 2331 | 488 |
| delikli grafik | unsupported | unsupported | 2265 | 2477 | 681 |
| geometri | unsupported | unsupported | 2177 | 2159 | 373 |

Kalın değerler TA-008'in doğru dersleri yanlış başarısız saydığı durumlardır (F3). `x/x = 1` için `x = 1` cevabı
eksiktir; TA-008 bunu göremiyordu (F1).

## Yorum

- Ortanca değişmedi. p95 artışı esas olarak köklü denklemden gelir: TA-008B adım zincirini sonuna kadar denetliyor
  (eleme ve dal denetimi) ve dersi doğruluyor; TA-008 ilk yanlış "kayıp"ta duruyordu.
- Uzmanlık raporu çekirdek doğrulamadan uzundur (≈ 367 ms ortanca), ama dış zaman aşımına (8 sn) göre geniş pay vardır;
  zaman bütçesi (2,5 sn) işlemler arasında denetlenir ve tek bir SymPy çağrısını kesmez.
- Yeniden ayrıştırma uzmanlık süresinin ≈ %1,5'idir (cProfile); önbellek eklenmedi.
- Eşzamanlı patlamada zaman aşımı veya `mathai_busy` görülmedi; bu, yalnız bu makinedeki 8 yuva içindir.

## Tekrarlama

Ölçüm betiği depo dışında tutuldu (geçici araç). Aynı ölçüm, her ağacın kökünde `IsolatedMathAI().verify(plan)` ile
yukarıdaki planlar × 5 tekrar ve `last_timing`/`last_phases` alanlarının toplanmasıyla yeniden yapılabilir. Derlem
düzeyindeki süreç içi ölçüm: [TA-008B derlem ölçümü](TA-008B-corpus-benchmark.md); TA-008 tabanı:
[TA-008 performans](TA-008-performance.md).
