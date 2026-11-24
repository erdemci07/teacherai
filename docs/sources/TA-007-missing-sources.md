# TA-007 eksik kaynak listesi (TA-006 listesinin güncellemesi)

Bu liste proje sahibinin edinmesi veya karar vermesi gereken belgeleri içerir. TA-007'de proje sahibinin araştırma listesi (`TA007_kaynak_ve_eksik_listesi.md`) bir başlangıç noktası olarak kullanıldı; her satır yeniden denetlendi. Hiçbir satır için kazanım kodu, resmî metin, sayfa numarası, lisans onayı veya inceleme uydurulmadı. Erişilemeyen belge "incelendi" sayılmadı ve erişim kısıtlamaları aşılmadı. Son denetim: 2026-11-24.

Durum sütunu: **kapandı** (resmî kaynakla doğrulandı ve kayda girdi), **kısmen** (bir bölümü doğrulandı), **açık** (eksik).

## A. Müfredat ve takvim

| # | Konu | TA-006 durumu | TA-007 durumu | Ne yapıldı / ne eksik |
| --- | --- | --- | --- | --- |
| A1 | 2024 onaylı Maarif (TYMM) program PDF'leri (matematik 5-8, 9-12; fizik, kimya, biyoloji 9-12; fen 3-8) | açık | **açık** | Resmî adresler 2026-11-24'te HTTP 500 döndürdü (boş dosya). Altısı `pending_programs` içinde `http_error` olarak kayıtlı. 2024 sürümü 2026 sürümünün yerine yazılmaz; ayrı sürüm olarak eklenecek. Tarayıcı taklidiyle yeniden deneme yapılmadı. |
| A2 | 2024-2025 uygulama takvimi | açık | **kapandı** | 2024/53 iş ve işlemler genelgesi ve 2024/54 Maarif Modeli genelgesi okundu. Kural: 5 ve 9. sınıf Maarif (`explicit`, program belgesi kayıtta yok → `program_document_missing`), 6-8 ve 10-12 önceki programlar (`by_exclusion`). |
| A3 | 2025-2026'da 7, 8, 11, 12. sınıflarda önceki programın sürmesi | açık | **kısmen** | 2025-2026 iş ve işlemler genelgesi (PDF) Maarif sınıflarını (5, 6, 9, 10) açıkça sayıyor; diğer sınıflar için kural `by_exclusion`. Önceki programın sürdüğünü *açıkça* söyleyen metin bulunmadı. |
| A4 | 2026-2027'de 8. sınıf | `by_exclusion` | **kapandı** | Antalya Ölçme Değerlendirme Merkezi'nin (MEB alanı) 2026-2027 duyurusu 8 ve 12. sınıfta 2018 programlarının sürdüğünü açıkça yazıyor. Kural `explicit`. |
| A5 | Talim ve Terbiye Kurulu karar tarih/sayıları | açık | **açık** | Karar metinleri bulunamadı. `stated_date` yalnız belge kapağından. |
| A6 | Matematik 1-8 (2018) 5/6/7. sınıf kazanım sayıları | bilinmiyor | **kapandı** | PDF s. 24-26 tablosu `pdftotext -layout` ile sütun düzeninde görsel olarak okundu: 56/59/48; kayıtla eşleşti. |
| A7 | Fizik 12 / Kimya 11 (2018) sayıları | bilinmiyor | **kapandı** | 68 ve 35; kayıtla eşleşti. |
| A8 | TYMM matematik 7, kimya 9-12, biyoloji 12 sayıları | bilinmiyor | **kapandı** | 30; 23/21/25/24; 20 — kayıtla eşleşti. |
| A9 | Temel düzey / temel matematik ve hazırlık sınıfı | kapsam dışı | **kısmen** | İzlek modeli eklendi (`general`, `science_high_school`, `basic_level`). Temel Matematik 11-12 (PID 2181) iki farklı kod öneki taşıdığı için (`inconsistent_codes`), 2018 Temel Düzey bölümü başlıkları güvenilir çıkmadığı için (`extraction_unreliable`) kayda alınmadı. Hazırlık sınıfı sınıf numarası taşımadığından eşlenmedi. |
| A10 | Fen lisesi programları (matematik, fizik, kimya, biyoloji 9-12) | indirilmedi | **kısmen** | Dört program indirildi (sha256 katalogda), çıkarıcıyla üretildi ve yalnız açık okul türü beyanıyla seçilir. 2026-2027'de fen lisesi 9-11 Maarif, 12 fen lisesi 2018 (Antalya ÖDM). Fen lisesi matematiğinde beklenen sayı tablosu okunamadı (`bilinmiyor`, 4 hücre). |
| A11 | MEB program metinlerinin yeniden kullanım koşulu | açık | **açık** | Değişmedi: resmî kazanım metni öğrenciye ve isteme gönderilmez. |

## B. Sınav kapsamı

| # | Sınav | TA-007 durumu | Ayrıntı |
| --- | --- | --- | --- |
| B1 | LGS 2027 | **kısmen** | Tarih (2027-06-13) ve 8. sınıf kapsamı MEB duyurusuyla doğrulandı; program kapsamı uygulama kuralından türetildi (`derived`); kazanım düzeyi kapsam (dönem sınırı) `unverified`. |
| B2 | TYT 2027 | **kısmen** | Tarih (2027-06-19) ÖSYM takviminden doğrulandı; hangi program sürümüne dayandığı `unverified`. |
| B3 | AYT 2027 | **kısmen** | Tarih (2027-06-20) doğrulandı; kapsam `unverified`. Mezun öğrenci çözümlemesi bu yüzden `ambiguous` kalır. |
| B4 | LGS 2026 dönem sınırı | **açık** | Değişmedi. |

## C. Bilimsel kaynaklar

| # | Kaynak | TA-007 durumu |
| --- | --- | --- |
| C1 | IUPAC Gold Book | açık — otomatik erişim tarayıcı doğrulamasıyla engelli; aşılmadı. |
| C2 | NCBI Bookshelf | açık — reCAPTCHA; aşılmadı. |
| C3 | AIM Open Textbook listesi | açık. |
| C4 | NIST CODATA kullanım koşulu | açık — içeri alma `unknown`. |
| C5 | NASA veri yeniden kullanım koşulu | açık. |
| C6 | PubChem katkıcı lisansları | açık. |
| C7 | Siyavula lisans sürümü / unbranded baskı | açık. |
| C8 | Sullivan, Stewart, Pólya, Serway-Jewett, Brown-LeMay, Chang, Campbell | açık — baskı/ISBN meşru erişilebilir kaynaktan doğrulanmadı; içerik edinilmedi. Yalnız başvuru adayı; `math.polya-problem-solving` kaynaksız kalır. Yetkisiz kaynaktan kitap alınmadı. |
| C9 | OpenStax CC BY-NC-SA ve TeacherAI'nin ticari durumu | açık — NC lisans ticari izin değildir. Dört yeni OpenStax başlığı (Algebra and Trigonometry 2e, University Physics Vol. 3, College Physics 2e, Astronomy 2e) yalnız akademik başvuru olarak eklendi; metin içeri alınmadı. |
| C10 | OGM Materyal, ÖSYM soru tipi analizi | açık. |

## D. Değerlendirme

| # | Öğe | TA-007 durumu |
| --- | --- | --- |
| D1 | 24 özgün soru görseli | **kapandı (yerel)** — `Codex_29_gorsel_cevapsiz.zip` güvenli içe aktarıldı; 24/24 görsel `evals/local/images` altında (Git dışı), manifestte yalnız ad + sha256. |
| D2 | Bağımsız öğretmen cevap anahtarı | **açık** — 0/24. Anahtar modelden veya çözümden türetilmedi. |
| D3 | OCR varyantları | **kapandı (yerel)** — 5 varyant (M01 ×2, B01, C04, P02), özgün soruya bağlı; ayrı örnek sayılmaz. |
| D4 | Öğretmen katkı formları ve inceleme CSV'leri | **açık** — formlar boş; 74 taslak ve 5 yöntem politikası için karar yok. TA-007'de düzeltilen 13 girdinin CSV satırı bayattır; `python -m scripts.review_import export` güncel formu üretir. |
| D5 | İnceleyen yetkilendirmesi | **açık** — `reviewers.json` boş; proje sahibinin gerçek öğretmen/uzman yetkilendirmesi gerekiyor. |
