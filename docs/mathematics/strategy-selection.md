# TA-008 matematik strateji seçimi

Kayıt: `apps/api/app/features/mathematics/data/strategies.json` (21 strateji, hepsi `draft`). Modül:
`features/mathematics/strategies.py`. Ders akışında `LessonService.with_strategies` raporun `strategies` alanını doldurur.

## İlkeler

- Strateji **önerisidir**; kısıt değildir. Kısıtlar yalnız yetkili öğretmen onaylı MethodPolicy v2'den gelir (TA-007).
- Uygulanabilirlik anahtar sözcükle değil, kaynak ifadelerin yapısal özelliklerinden (`linear_equation`, `quadratic`,
  `absolute_value`, `linear_inequality`, `rational_or_polynomial_inequality`, `linear_system`, `proportion`, `function`,
  `trigonometry`) ve sağlayıcı modelinin türünden (`word_problem`, `geometry`) belirlenir.
- Her stratejide konu, önkoşul, uygulama koşulu, sınıf aralığı, avantaj, sınırlılık, alternatifler ve durum vardır.
- Sınıf uygunluğu (`suitable_for_grade`) ayrı işaretlenir; sınıf bilinmiyorsa `None` (tahmin yok). Onaylı politikanın
  yasakladığı yapıya dayanan strateji (`quadratic_formula`, `derivative_test`) `forbidden_by_approved_policy` olur.
- Kayıttaki stratejiler AI taslağıdır; öğretmen deneyimi olarak sunulmaz. Kayıt yükleyicisi `approved` durumu reddeder:
  onay yalnız öğretmen inceleme akışıyla gelebilir.

## Alternatif yollar

`mathematics.alternatives.quadratic`: çarpanlara ayırma (yalnız rasyonel köklerde), tam kareye tamamlama, kök formülü.
Her yol özgün denklemin çözüm kümesiyle karşılaştırılır (`verified`). Aynı çözümün başka sözlerle yazılması alternatif
sayılmaz. Ek sağlayıcı çağrısı yapılmaz.

## Öğretmen katkısı

Google Forms'tan gelecek öğretmen deneyimleri (bkz. [içe aktarma](../teachers/TA-008-google-forms-import.md)) önce taslak
katkıdır; yayımlanıp onaylanmadan strateji kaydını veya politikayı değiştirmez.
