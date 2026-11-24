# Öğretmen katkıları

Öğretmen katkı dosyaları (`teacherai.teacher_contribution`) buraya konur ve `python -m scripts.teacher_contributions validate <dosya>` ile denetlenir. Şablonlar: [docs/teachers/](../../docs/teachers/). Katkı taslak olarak içeri alınır; onay ayrı bir inceleme kaydı ister ve bu dizindeki hiçbir dosya ders üretimi bağlamına doğrudan girmez.

TA-007: Word formu `python -m scripts.teacher_forms convert <form.docx>` ile dönüştürülür. Aşama kayıtları `register.json` dosyasındadır (`python -m scripts.teacher_contributions status`); bkz. [inceleme akışı](../../docs/governance/TA-007-review-workflow.md). Uygulama içi kullanım izni model eğitimi izni değildir.
