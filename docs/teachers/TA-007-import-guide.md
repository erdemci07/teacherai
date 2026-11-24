# Öğretmen katkısı içe aktarma kılavuzu (TA-007)

Bu kılavuz proje sahibi içindir. Doldurulmuş Word formunu kanonik katkı taslağına çevirmeyi ve yönetişim kaydını anlatır. Katkı **onay değildir**.

## 1. Formu almadan önce

- Öğretmene yalnız kendi branşının formunu gönderin (`matematik`, `fizik`, `kimya`, `biyoloji`, `ortaokul fen`).
- Formda ad, okul, telefon, e-posta veya öğrenci bilgisi istenmez. Takma ad `teacher:<ad>` / `expert:<ad>` biçimindedir.
- Yayınevi, ÖSYM veya MEB sorusu kopyalanmaz; yalnız özgün soru ve öğretmenin kendi çözümü.

## 2. Dönüştürme

```sh
python -m scripts.teacher_forms convert form.docx                 # çıktıyı ekrana yazar, kaydetmez
python -m scripts.teacher_forms convert form.docx --topic dogrusal_denklemler --write
```

Araç yalnız `word/document.xml` metnini okur; makro, gömülü nesne veya dış bağlantı izlenmez. Dönüşüm şu durumlarda **durur** ve sorunları listeler:

| Durum | Neden |
| --- | --- |
| Takma ad birden çok / biçimsiz, tarih yok | kimlik belirsiz |
| Kullanım izni satırında "Evet" ve "Hayır" ikisi de duruyor | izin belirsiz → katkı alınmaz |
| E-posta veya telefon görüldü | kişisel bilgi |
| Konu tek anlamlı eşlenemedi | `--topic` ile taksonomi anahtarı verin (`curriculum/data/topics.json`) |
| Özgün soru var, bağımsız cevap yok | örnek soru öğesi oluşturulmaz; cevap türetilmez |
| Hiç alan doldurulmamış | katkı yok |

Model eğitimi izni yalnız açık "Evet" ile `true` olur; formdaki varsayılan "Hayır"dır. Boş alan (`[Buraya yazınız.]`) öğe üretmez. Mevcut dosyanın üzerine yazılmaz; düzeltme yeni dosyadır.

## 3. Alan eşlemesi

| Form alanı | Katkı türü |
| --- | --- |
| İlk inceleme ve çözüm planı | `unfamiliar_question_approach` |
| Sık hata → nedeni → soru | `common_error` |
| Tercih edilen yöntem ve gerekçesi | `preferred_strategy` |
| Hangi sınıfta hangi yöntem | `class_level_method` |
| İkinci anlatım | `alternative_explanation` |
| Tahta çizim sırası | `visual_strategy` |
| Kural/yasa ve koşulları | `scientific_condition` (+ kaynak notu) |
| İstisna, karşı örnek | `scientific_exception` (+ kaynak notu) |
| Özgün soru + bağımsız cevap | `example_question` (alıştırma havuzu; değerlendirme setine girmez) |

## 4. Sonraki adımlar

1. `python -m scripts.teacher_contributions validate data/contributions/<dosya>.json`
2. `data/contributions/register.json` içine `submitted` aşamasını katkının içerik özetiyle ekleyin (özet: `teacher_contributions.contribution_digest`).
3. Aşamalar ve yetki kuralları: [inceleme akışı](../governance/TA-007-review-workflow.md). `python -m scripts.teacher_contributions status` engelleri gösterir.
4. Yayımlanan katkı bilgi girdisine dönüştürülecekse `rights.source_use="teacher_original"` ve `contribution_id` taşır; yine bilimsel onay ister.
