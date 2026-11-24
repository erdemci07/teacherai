# TA-006 eksik kaynak istek listesi

Bu liste proje sahibinin edinmesi veya karar vermesi gereken belgeleri içerir. Hiçbir satır için kazanım kodu, resmî metin veya inceleme uydurulmadı; erişilemeyen belge "incelendi" sayılmadı ve site kısıtlamaları aşılmadı. Erişim tarihi: 2026-11-24.

## A. Müfredat ve takvim

| # | Alan | Sınıf | Program sürümü | Belge | Resmî adres | Gereken dosya/bölüm | Erişim sorunu | Bağımlı gereklilik |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Matematik, Fen, Fizik, Kimya, Biyoloji | 5, 6, 9, 10 | Maarif Modeli ilk sürümleri (2024/2025) | 2024-2025 ve 2025-2026'da okutulan TYMM program PDF'leri | https://mufredat.meb.gov.tr/Programlar.aspx | Her dersin 2024 ve 2025 tarihli tam PDF'i | Program listesinde yalnız "(2026)" sürümleri var; önceki sürümler listelenmiyor | 2025-2026 çözümlemesi `program_document_missing` döner (§7); bu yılda üretilmiş derslerin bağlamı kurulamaz |
| A2 | Tümü | 1, 5, 9 | — | 2024-2025 uygulama takvimi resmî metni | https://www.meb.gov.tr | 2024-2025 eğitim öğretim yılı iş ve işlemler genelgesi | Aranmadı/doğrulanmadı | 2024-2025 uygulama kuralı kayıtta yok |
| A3 | Tümü | 7, 8, 11, 12 | MEB 2018 | 2025-2026'da önceki programların sürdüğünü açıkça söyleyen resmî metin | https://www.meb.gov.tr/…/haber/38072/tr | Genelgenin tam metni | Haber metni yalnız Maarif sınıflarını sayar | 2025-2026 bu sınıflar `schedule_unverified` kalır |
| A4 | Matematik, Fen | 8 | MEB 2018 | 2026-2027'de 8. sınıfta önceki programın sürdüğünü açıkça söyleyen metin | https://tymm.meb.gov.tr/taslak-cerceve-planlari/temel-egitim | Temel eğitim genelgesi veya duyurusu | Sayfa yalnız Maarif sınıflarını sayar; kural `by_exclusion` olarak işaretli | 8. sınıf çözümlemesi `by_exclusion` gerekçesi taşır |
| A5 | Tüm programlar | — | 12 program | Talim ve Terbiye Kurulu karar tarihi ve sayısı | https://ttkb.meb.gov.tr | Her programın kabul kararı | PDF'lerde karar bilgisi okunamadı | `ProgramDocument.stated_date` yalnız dosya adı/kapaktan |
| A6 | Matematik | 5, 6, 7 | MEB 2018 | Kazanım sayısı tablosu | PID=329 PDF | 5-7. sınıf "Kazanım Sayısı ve Süre" tabloları | Tablo metni pdftotext ile güvenle okunamadı | Beklenen sayı `bilinmiyor` |
| A7 | Fizik / Kimya | 12 / 11 | MEB 2018 | Kazanım sayısı tablosu | PID=351, PID=350 | İlgili sınıf tablosu | Aynı | Beklenen sayı `bilinmiyor` |
| A8 | Matematik / Kimya / Biyoloji | 7 / 9-12 / 12 | Maarif 2026 | Öğrenme çıktısı sayısı tablosu | PID=2340, 2255, 2250 | İlgili tablolar | Aynı | Beklenen sayı `bilinmiyor` |
| A9 | Matematik | Hazırlık, 11-12 (Temel Düzey) | MEB 2018 ve Maarif | Hazırlık sınıfı ve Temel Düzey/Temel Matematik izlekleri | PID=343 (TD bölümü), PID=2181 | Bölümler | Kapsam dışı bırakıldı (izlek ayrımı henüz modellenmedi) | `track` alanı boş |
| A10 | Matematik, Fizik, Kimya, Biyoloji | 9-12 | MEB 2018 | Fen Lisesi programları | PID=340, 349, 347, 363 | Tam PDF | İndirilmedi (izlek ayrımı TA-007) | Fen lisesi öğrencisi genel programla çözümlenir |
| A11 | Tümü | — | Tümü | MEB program metinlerinin birebir yeniden kullanım koşulu | MEB / hukuk danışmanı | Yazılı izin veya hukuki görüş | Belgelerde lisans ifadesi yok | Resmî kazanım metni öğrenciye ve isteme gönderilmiyor; yalnız kod ve başlık |

## B. Sınav kapsamı

| # | Sınav | Yıl | Gereken | Resmî adres | Durum | Bağımlı gereklilik |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | LGS | 2027 | Kapsam duyurusu (hangi sınıf programı, dönem sınırı) | https://www.meb.gov.tr | Bulunamadı | `lgs-2027` `unverified`; kazanım sınava bağlanmaz |
| B2 | TYT | 2027 | ÖSYM'nin kapsamı hangi program sürümüne dayandırdığı | https://www.osym.gov.tr | Bulunamadı (YKS sayfası 404) | `tyt-2027` `unverified` |
| B3 | AYT | 2027 | Aynı | https://www.osym.gov.tr | Bulunamadı | Mezun/AYT çözümlemesi `ambiguous` kalır |
| B4 | LGS | 2026 | Dönem sınırı (yalnız birinci dönem mi) | MEB haber 40956 | Haber yalnız "8. sınıf programları" der | `lgs-2026` sınıf düzeyiyle bağlı, kazanım düzeyinde değil |

## C. Bilimsel kaynaklar

| # | Kaynak | Gereken | Erişim sorunu | Bağımlı gereklilik |
| --- | --- | --- | --- | --- |
| C1 | IUPAC Gold Book | Terim kayıtları ve lisans | Otomatik erişim 403 tarayıcı doğrulaması; aşılmadı | Kimya tanımları yalnız OpenStax'e bağlı |
| C2 | NCBI Bookshelf | Kitap bazında lisans | reCAPTCHA; aşılmadı | Biyoloji yetkili kaynak çeşitliliği |
| C3 | AIM Open Textbook Initiative | Onaylı kitap listesi | Liste sayfası 404 | Açık matematik kaynağı seçimi |
| C4 | NIST CODATA | Standard Reference Data kullanım koşulu | Koşul sayfası doğrulanmadı | `nist.codata` içeri alma `unknown` |
| C5 | NASA Planetary Fact Sheet | Veri yeniden kullanım koşulu | Medya yönergesi veriyi açıkça kapsamıyor | `nasa.planetary-fact-sheet` içeri alma `unknown` |
| C6 | PubChem | Kayıt bazında katkıcı lisansları | Doğrulanmadı | Bileşik verisi içeri alınmaz |
| C7 | Siyavula | Lisans sürümü ve "unbranded" baskı | Sayfada sürüm yok | Koşullu izin |
| C8 | Sullivan, Stewart, Pólya, Serway-Jewett, Brown-LeMay, Chang, Campbell | Baskı, yıl, ISBN; içeri alma için yazılı lisans | Edinilmedi; baskı doğrulanmadı | Yalnız akademik başvuru adayı; `math.polya-problem-solving` kaynaksız |
| C9 | OpenStax | TeacherAI'nin ticari durumu belirlenince CC BY-NC-SA uygunluğu | Ticari durum proje sahibinin kararı | OpenStax içeriği içeri alınmaz/dağıtılmaz; yalnız başvuru |
| C10 | OGM Materyal, ÖSYM soru tipi analizi | Materyal ve soru tipi incelemesi | OGM Materyal JavaScript gerektiren tek sayfalı uygulama; içerik incelenmedi | TA-007 yöntem çalışması |

## D. Değerlendirme

| # | Öğe | Durum | Bağımlı gereklilik |
| --- | --- | --- | --- |
| D1 | 24 özgün sorunun görselleri (B01–B06, C01–C06, M01–M06, P01–P06) | 0/24 | Gerçek Vision/ders değerlendirmesi |
| D2 | Bağımsız öğretmen cevap anahtarı | 0/24 | İstenen cevap doğruluğu ölçümü |
| D3 | OCR varyantları | 0 | Görsel dayanıklılık ölçümü |
