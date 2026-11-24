# TA-007 kaynak hakları uygulaması

Hak durumu iki düzeyde tutulur ve çalışma zamanında birlikte uygulanır (`knowledge/registry.py → runtime_eligibility`, `_rights_reasons`). Bu belge hukuki görüş değildir; hiçbir lisans veya izin onayı uydurulmadı.

## 1. Kaynak düzeyi (`SourceRecord.permissions`)

Dört ayrı izin: akademik başvuru, içeri alma/dönüştürme, öğrenciye yeniden dağıtım, model eğitimi. Lisans doğrulanmadan izin `allowed` olamaz; satın alınan kitap içeri alma izni sayılmaz; share-alike yükümlülüğü koşul olarak yazılır. 34 kaynak; ayrıntı: [bilgi kapsam raporu](../knowledge/TA-007-knowledge-coverage.md).

## 2. Girdi düzeyi (`KnowledgeEntry.rights: RightsRecord`)

| Sınıf | Anlamı | Çalışma zamanı koşulu |
| --- | --- | --- |
| `independent_fact` | Bilimsel olgunun özgün anlatımı; kaynak yalnız doğrulama başvurusu | Kaynakta akademik başvuru izni; erişim kısıtlı/erişilmemiş değil |
| `teacher_original` | Öğretmenin özgün açıklaması | `contribution_id` + yetkili hak kararı. Hak kararı katkı yayımlandıktan sonra verilir; bu çevrimdışı denetlenir (`teacher_contributions status`), çalışma zamanı katkı dosyası okumaz |
| `licensed_adaptation` | Lisanslı kaynağın uyarlaması | İçeri alma izni + doğrulanmış lisans + `commercial_use="eligible"` + atıf |
| `direct_quotation` | Doğrudan alıntı | Yeniden dağıtım izni + doğrulanmış lisans + ticari uygunluk + atıf |
| `reference_citation` | Yalnız kaynak gösterimi | Metin kullanılmaz |
| `unresolved` | Hak durumu çözülmedi | **Hiçbir zaman** yetkili bağlama giremez |

Her kayıt ayrıca baskı (`source_editions`), lisans sürümü (`license_versions`), atıf, yeniden dağıtım notu, share-alike ve karar (`pending/approved/rejected`, `decided_by` yalnız `owner:`, `decided_on`) taşır. Karar, inceleyen kaydında `rights` yetkisine sahip proje sahibinden gelmedikçe `rights_decider_not_authorized` engeli oluşur.

## 3. Ticari olmayan lisanslar

OpenStax CC BY-NC-SA 4.0 ticari kullanım izni değildir. NC lisanslı kaynağın uyarlama veya alıntısı `commercial_use="eligible"` olarak işaretlenirse `noncommercial_license` engeli oluşur. Bugün OpenStax yalnız akademik başvurudur.

## 4. Bugünkü durum

- 202 girdinin hak kararı `pending`; sınıf dağılımı raporda. Yetkili hak kararı veren yok (`reviewers.json` boş).
- Çalışma zamanına uygun girdi: **0**.
- Lisans netleşmeden hiçbir kaynağın içeri alma/dağıtım izni açılmadı; yetkisiz kaynaktan kitap alınmadı.

## 5. Engel nedenleri (özet)

`status:*`, `reviewer_not_authorized`, `stale_approval`, `unsourced`, `unknown_source:*`, `locator_unverified:*`, `rights_unresolved`, `rights_decision:*`, `rights_decider_not_authorized`, `rights_restricted:*`, `adaptation_not_licensed:*`, `quotation_not_licensed:*`, `commercial_use:*`, `noncommercial_license:*`.
