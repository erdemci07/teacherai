# TA-007 inceleme ve katkı yönetişimi

Bu belge bilimsel bilgi girdileri, yöntem politikaları ve öğretmen katkıları için onay kapılarını tanımlar. AI ön incelemesi (ör. [TA-007 taslak denetimi](../../apps/api/app/features/knowledge/audit/TA-007-draft-audit.json)) hiçbir kapıyı geçirmez.

## 1. İnceleyen yetkilendirmesi (proje sahibi)

`apps/api/app/features/knowledge/data/reviewers.json` — üretimde **boş**.

```json
{"reviewer": "teacher:takma-ad", "roles": ["teacher"], "subjects": ["mathematics"],
 "stages": ["scientific", "pedagogical"], "valid_from": "2026-12-01", "valid_until": null, "revoked_on": null,
 "authorized_by": "owner:proje-sahibi", "authorized_on": "2026-12-01",
 "evidence_note_tr": "Kimlik ve yeterlik proje sahibince doğrulandı (kişisel bilgi burada tutulmaz)."}
```

- Yetkiyi yalnız `owner:` başvurusu verir. Hak kararı (`rights`) yalnız `project_owner` rolüyle.
- Ad, okul, e-posta, telefon tutulmaz; takma ad kararlı bir başvurudur.
- Geri alma: `revoked_on`; o tarihten sonraki kararlar geçersizdir. Süre: `valid_from`/`valid_until`.

## 2. Bilgi girdisi kapıları

| Kapı | Kim | Kayıt |
| --- | --- | --- |
| Kaynak doğrulama | `source_verification` yetkili | `ReviewRecord(decision="source_verified")` |
| Bilimsel inceleme ve onay | `scientific` yetkili öğretmen/uzman | `decision="approve"`, `stage="scientific"`, `reviewed_version`, `content_digest` |
| Hak kararı | `owner:` + `rights` | `RightsRecord.decision="approved"`, `decided_by`, `decided_on` |

Çalışma zamanına uygunluk (`runtime_eligibility`) hepsini aynı anda ister; ayrıca kaynak konumu doğrulanmış olmalıdır. Düzeltme yeni sürümdür (`revisions` önceki içeriği `previous_json` ile korur); eski onay `stale_approval` olur.

### CSV inceleme formları

```sh
python -m scripts.review_import export <klasör>          # güncel sürümlerle boş formlar
python -m scripts.review_import validate <form.csv>      # yetki, sürüm, tarih, karar denetimi
python -m scripts.review_import apply <form.csv> --write # yalnız geçerli satırlar
```

Reddedilenler: yetkisiz inceleyen, bayat sürüm (ör. TA-007'de düzeltilen 13 girdinin eski formu), tanımsız karar, gerekçesiz satır, düzeltme önerisiyle birlikte onay. Boş veya `not_reviewed` satır karar sayılmaz. Hak kararı bu formla verilmez.

## 3. Yöntem politikası kapıları

`matematik_5_yontem_politikasi.csv` biçimindeki form aynı araçla doğrulanır. Onay `pedagogical` yetkisi ister; uygulanınca v1 kayda `approved_by`, `approved_on`, `approval_digest` yazılır. Politika içeriği sonradan değişirse etkinliği düşer (`stale_approval`).

## 4. Öğretmen katkısı aşamaları

Katkı dosyası (`data/contributions/<dosya>.json`) yalnız girdidir. Aşamalar `data/contributions/register.json` dosyasındadır:

```
submitted → normalized → source_verified → scientific_review → pedagogical_review → rights_approved → published
                ↘ revision_requested (sonrası yeniden başlar) · rejected · superseded · withdrawn (son durum)
```

- Her aşama kaydı katkının o anki içerik özetini taşır; katkı değişirse eski aşamalar bayattır.
- Bilimsel ve öğretimsel inceleme katkı sahibinden bağımsızdır (`not_independent`).
- Her aşamayı yapan ilgili yetkiye sahiptir (`not_authorized`).
- Geri çekilen katkı yayımlanmaz ve model eğitimi izni de düşer. Uygulama içi kullanım izni (`consent_use`) model eğitimi izni (`consent_model_training`) değildir; TeacherAI bugün model eğitimi yapmaz.
- Durum: `python -m scripts.teacher_contributions status` (CI'da). Bugün kayıt yok: yayımlanmış katkı 0.

Word formlarının dönüştürülmesi: [içe aktarma kılavuzu](../teachers/TA-007-import-guide.md).
