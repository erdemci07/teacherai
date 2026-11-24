# Öğretmen katkı şablonları (TA-006 → TA-007)

Bu klasör, öğretmenlerin TeacherAI'ye yöntem, yaygın hata ve özgün soru katkısı vermesi için boş şablonları içerir. Şablonlar TA-007'deki öğretmen incelemesine hazırlıktır; burada tam bir yönetim paneli yoktur.

| Şablon | Kimin için |
| --- | --- |
| [matematik.md](matematik.md) | Matematik öğretmenleri (geometri dahil) |
| [fizik.md](fizik.md) | Fizik öğretmenleri |
| [kimya.md](kimya.md) | Kimya öğretmenleri |
| [biyoloji.md](biyoloji.md) | Biyoloji öğretmenleri |
| [ortaokul-fen.md](ortaokul-fen.md) | Ortaokul fen bilimleri öğretmenleri |
| [contribution.template.json](contribution.template.json) | İçe aktarma biçimi (makinece okunur) |

## Nasıl işler?

1. Öğretmen ilgili Markdown şablonunu doldurur veya JSON biçimini kullanır.
2. Proje sahibi katkıyı `data/contributions/<takma-ad>-<tarih>.json` olarak kaydeder ve doğrular:
   `python -m scripts.teacher_contributions validate data/contributions/<dosya>.json`
3. Katkı **taslak** olarak içeri alınır. Onay ayrı bir inceleme kaydı ister: inceleyen öğretmen veya alan uzmanının kararlı başvurusu (`teacher:<takma-ad>`), tarih, incelenen sürüm, karar ve gerekçe.
4. AI tarafından yazılmış taslak kendini onaylayamaz. Öğretmen tercihi yerleşik bilimsel gerçeği değiştiremez; bilimsel ifade değişikliği ayrıca bilimsel inceleme ister.

## Kurallar

- Ad, e-posta, okul adı gibi kişisel bilgi yazılmaz; yalnız takma ad kullanılır.
- Örnek sorular **özgün** olmalıdır. Yayınevi, ÖSYM veya MEB sorusu kopyalanmaz.
- Her örnek sorunun **bağımsız cevap anahtarı** öğretmenin kendi çözümüdür; modelden türetilmez.
- Örnek sorular alıştırma havuzuna aittir; bağımsız değerlendirme setine (`evals/datasets`) karıştırılmaz.
- `consent_use: true` içeriğin TeacherAI'de kullanılmasına izin verir. Model eğitimi ayrı izindir (`consent_model_training`, varsayılan `false`).

## Katkı türleri (`kind`)

| Tür | Anlamı |
| --- | --- |
| `unfamiliar_question_approach` | İlk kez görülen bir soruya nasıl yaklaşılır |
| `common_error` | Öğrencilerin sık yaptığı hata |
| `preferred_strategy` | Tercih edilen çözüm stratejisi |
| `class_level_method` | Sınıf düzeyine uygun yöntem (ve uygun olmayan) |
| `alternative_explanation` | Aynı fikri farklı anlatma yolu |
| `visual_strategy` | Tahta, şema, grafik kullanımı |
| `scientific_condition` | Önemli bilimsel koşul ve istisna |
| `example_question` | Özgün soru ve bağımsız cevap anahtarı |
| `scientific_exception` | İstisna, karşı örnek, sınır (TA-007; koşuldan ayrı) |

TA-007: doldurulmuş Word formlarının dönüştürülmesi ve yönetişim aşamaları için [içe aktarma kılavuzu](TA-007-import-guide.md) ve [inceleme akışı](../governance/TA-007-review-workflow.md).
