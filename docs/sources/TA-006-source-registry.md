# Bilimsel kaynak kaydı (TA-006)

Kaynak kaydı `apps/api/app/features/knowledge/data/sources.json` dosyasındadır; sözleşme `features/education/knowledge.py → SourceRecord`. Ayrıntılı tablo ve kullanım sayıları üretilen raporda: [TA-006-knowledge-coverage.md](../knowledge/TA-006-knowledge-coverage.md). Eksikler: [TA-006-missing-sources.md](TA-006-missing-sources.md).

## Alanlar

Kararlı kimlik, başlık, yazar/kurum, baskı ve yıl (yalnız doğrulandıysa), URL/DOI/ISBN (yalnız doğrulandıysa), tür, erişim durumu, ilgili alanlar, lisans ve hak sahibi, lisansın doğrulanıp doğrulanmadığı, doğrulama tarihi, baskının doğrulanıp doğrulanmadığı, not ve inceleme durumu.

Kesin konum bilgisi bilgi girdisinde (`Locator`) tutulur: kaynak kimliği, bölüm, adres, doğrulama tarihi. **Sayfa numarası yalnız gerçekten görüldüyse yazılır**; TA-006'da hiçbir girdiye sayfa numarası yazılmadı.

## Dört ayrı izin

| İzin | Anlamı | Varsayılan |
| --- | --- | --- |
| `academic_reference` | Uzmanın kaynağı okuyup kendi sözleriyle özgün bilgi yazması | Erişilebilen kaynakta `allowed` |
| `ingestion` | Metnin/verinin sisteme alınması ve dönüştürülmesi | Lisans doğrulanmadıysa asla `allowed` olamaz |
| `redistribution` | İçeriğin öğrenciye aynen veya türetilmiş gösterilmesi | Aynı kural |
| `model_training` | Model eğitimi veya ince ayar | Aynı kural; CC lisansları bunu ayrıca düzenlemediği için `unknown` |

Sözleşme kuralları (test edilir):

- Lisansı doğrulanmamış kaynakta içeri alma, dağıtım veya eğitim `allowed` olamaz.
- Satın alma gerektiren ve lisansı olmayan ders kitabında içeri alma `not_allowed` olmalıdır. Satın almak içeri alma hakkı vermez.
- Share-alike (SA) lisanslarda yükümlülük koşul olarak yazılır (`conditional` + `conditions_tr`).
- Kamuya açık olmak lisans anlamına gelmez.

## Bugünkü durum (2026-11-24)

| Grup | Kaynaklar | Lisans | Not |
| --- | --- | --- | --- |
| OpenStax | Prealgebra 2e, Elementary/Intermediate/College Algebra 2e, Introductory Statistics 2e, Calculus Vol. 1, University Physics Vol. 1-2, Chemistry 2e, Biology 2e | Sitede bugün **CC BY-NC-SA 4.0** ("aksi belirtilmedikçe") | Ticari olmayan kullanım + aynı lisans. TeacherAI'nin ticari durumu belirlenmeden içeri alınmaz; bilgi girdileri yalnız başvuru olarak bağlanır. Eski baskıların lisansı farklı olabilir. |
| Standart ve veri | BIPM SI Broşürü 9. baskı (**CC BY 4.0**), NIST CODATA, NASA Planetary Fact Sheet, PubChem | BIPM doğrulandı; diğerleri doğrulanmadı | NIST ve NASA için veri koşulları ayrıca doğrulanmalı |
| Açık ders kitapları | BCcampus Concepts of Biology 1. Kanada baskısı (**CC BY 4.0**, 2015), Siyavula (CC BY, sürüm yazmıyor), Active Calculus (CC BY-SA, sürüm doğrulanmadı), LibreTexts (sayfa bazında değişir) | Kısmen | Ticari kullanıma izin veren adaylar: BCcampus, Siyavula (atıfla) |
| Erişilemeyen | IUPAC Gold Book (403), NCBI Bookshelf (reCAPTCHA), AIM onaylı kitap listesi (404) | — | Kısıtlamalar aşılmadı |
| Telifli ders kitapları | Sullivan, Stewart, Pólya, Serway-Jewett, Brown-LeMay, Chang, Campbell | — | Edinilmedi; baskı/ISBN doğrulanmadı. Yalnız akademik başvuru adayı |
| Resmî müfredat | MEB öğretim programları (12 PDF, sha256 kayıtlı) | Belgelerde lisans ifadesi yok | Yalnız kod, başlık, sayfa alındı |

Hiçbir ders kitabı, soru bankası veya yetkisiz PDF depoya eklenmedi. İndirilen resmî PDF'ler yalnız oturum çalışma dizininde tutuldu.

## İş akışı

1. Kaynak önce `access`, `license_verified`, `edition_verified` ve dört izinle kaydedilir.
2. Bilgi girdisi kaynağa `Locator` ile bağlanır (bölüm adresi doğrulanır).
3. Girdinin çalışma zamanına uygunluğu (`knowledge/registry.py → runtime_eligibility`) şunları ister: onaylı durum, en az bir doğrulanmış konum, kaynağın akademik başvuruya açık ve erişilebilir olması.
4. Proje sahibi kaynak kaydını gözden geçirdiğinde `review_status: owner_reviewed` yapılır (bugün hiçbiri).
