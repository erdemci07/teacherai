# Google Forms yanıtlarını içe aktarma hazırlığı (TA-008)

Proje sahibinin branşa özgü pedagojik formunun yanıtları sonradan Google Sheets/CSV olarak verilecek. Bu belge
dönüştürme adımlarını anlatır. Proje sahibinin Google hesabına erişilmedi; hiçbir yanıt veya onay uydurulmadı.

## 1. Başlıkları görün (varsayım yok)

```sh
python -m scripts.forms_import inspect yanitlar.csv
```

Çıkan başlıkları `docs/teachers/forms-mapping.example.json` kopyasındaki sağ taraflara yazın. Eşlemede olmayan sütun
okunmaz; eşlenen ama CSV'de olmayan sütun hatadır.

| Eşleme anahtarı | Anlamı | Katkı türü |
| --- | --- | --- |
| `timestamp` | Form zaman damgası | `submitted_on` |
| `alias` (isteğe bağlı) | `teacher:…`/`expert:…` | `contributor`; yoksa `teacher:form-<özet>` takma başvurusu |
| `subject` + `subject_values` | Branş | `subject` |
| `experience`, `grades_exams` | Deneyim, sınıf/sınav deneyimi | `experience_tr` (kimlik değildir) |
| `misconceptions` | Sık hatalar | `common_error` |
| `strategies` | Anlatım stratejileri | `preferred_strategy` |
| `alternatives` | Alternatif yöntemler | `alternative_explanation` |
| `visual` | Görsel/tahta | `visual_strategy` |
| `curriculum` | Sınıf düzeyi | `class_level_method` |
| `general` | Genel öneri | `general_pedagogy` (konu `genel`; kazanım uydurulmaz) |
| `consent_use` | Kullanım izni | Açık "evet" değilse satır alınmaz |
| `consent_training` | Model eğitimi izni | Yalnız açık "evet" ile true |

## 2. Kuru çalıştırma, sonra yazma

```sh
python -m scripts.forms_import convert yanitlar.csv --mapping esleme.json            # yazmaz, rapor verir
python -m scripts.forms_import convert yanitlar.csv --mapping esleme.json --write --register
```

Atlanan satırlar nedeniyle listelenir: izin yok/belirsiz, e-posta veya telefon görüldü, alan eşlenemedi, takma ad biçimi
hatalı, boş katkı, yinelenen satır. `--write` her kabul edilen satırı `data/contributions/forms-<özet>.json` olarak yazar
ve satır özetini `data/contributions/forms-ledger.json` defterine ekler (artımlı içe aktarma). `--register` yalnız
`submitted` aşamasını ekler.

## 3. İnsan incelemesi

Sonraki aşamalar (normalleştirme, kaynak doğrulama, bilimsel ve öğretimsel inceleme, hak kararı, yayın) yetkili
inceleyenlerle yapılır: [inceleme akışı](../governance/TA-007-review-workflow.md). Yayın anlık görüntüsü
`python -m scripts.teacher_contributions snapshot --write` ile üretilir; çalışma zamanı yalnız bu anlık görüntüyü okur
ve geri çekilen katkı bir sonraki ders üretiminde kullanılmaz.
