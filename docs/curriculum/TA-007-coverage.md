# TA-007 müfredat kapsam raporu

Bu dosya `python -m scripts.curriculum_registry` ile üretilir; elle düzenlenmez. CI `--check` ile eskimiş raporu reddeder.

- Kayıt sürümü: `2.0.0+f9dbcc1e22c1`
- Program sürümü: 16 · başlık (ünite/tema/konu): 919 · kazanım/öğrenme çıktısı: 2197
- Disiplin dağılımı: biology 261, chemistry 355, geometry 195, mathematics 467, physics 555, science 364
- Yöntem politikası: 5 (hepsi `draft`; v1'den göç)

Sütunlar: **beklenen** resmî sayı tablosundan okunabildiyse yazılır, okunamadıysa `bilinmiyor` kalır. **eksik** yalnız beklenen
sayı biliniyorsa hesaplanır. **resmî metin** TA-005'ten korunan birebir kazanım metnidir (hak incelemesi bekliyor).
**betimleme** özgün, incelenmemiş kısa açıklamadır. **incelenen** bağımsız insan incelemesinden geçmiş kayıt sayısıdır.
**uygulama** doğrulanmış resmî kaynağa göre o sınıfta programın okutulduğu öğretim yıllarıdır.

| Alan | Çerçeve | Program | Sınıf | Beklenen | Kayıtlı | Eksik | Resmî metin | Betimleme | İncelenen | Kaynak | Uygulama |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Matematik | MEB 2018 | `meb-2018.matematik.1-8` | 5 | 56 | 56 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.matematik.1-8` | 6 | 59 | 59 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025 |
| Matematik | MEB 2018 | `meb-2018.matematik.1-8` | 7 | 48 | 48 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026 |
| Matematik | MEB 2018 | `meb-2018.matematik.1-8` | 8 | 52 | 52 | 0 | 29 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026, 2026-2027 |
| Fen Bilimleri | MEB 2018 | `meb-2018.fen-bilimleri.3-8` | 5 | 36 | 36 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fen Bilimleri | MEB 2018 | `meb-2018.fen-bilimleri.3-8` | 6 | 59 | 59 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025 |
| Fen Bilimleri | MEB 2018 | `meb-2018.fen-bilimleri.3-8` | 7 | 67 | 67 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026 |
| Fen Bilimleri | MEB 2018 | `meb-2018.fen-bilimleri.3-8` | 8 | 61 | 61 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026, 2026-2027 |
| Matematik | MEB 2018 | `meb-2018.matematik.9-12` | 9 | 41 | 41 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.matematik.9-12` | 10 | 27 | 27 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025 |
| Matematik | MEB 2018 | `meb-2018.matematik.9-12` | 11 | 28 | 28 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026 |
| Matematik | MEB 2018 | `meb-2018.matematik.9-12` | 12 | 34 | 34 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026, 2026-2027 |
| Fizik | MEB 2018 | `meb-2018.fizik.9-12` | 9 | 44 | 44 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fizik | MEB 2018 | `meb-2018.fizik.9-12` | 10 | 39 | 39 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025 |
| Fizik | MEB 2018 | `meb-2018.fizik.9-12` | 11 | 62 | 62 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026 |
| Fizik | MEB 2018 | `meb-2018.fizik.9-12` | 12 | 68 | 68 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026, 2026-2027 |
| Kimya | MEB 2018 | `meb-2018.kimya.9-12` | 9 | 38 | 38 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Kimya | MEB 2018 | `meb-2018.kimya.9-12` | 10 | 23 | 23 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025 |
| Kimya | MEB 2018 | `meb-2018.kimya.9-12` | 11 | 35 | 35 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026 |
| Kimya | MEB 2018 | `meb-2018.kimya.9-12` | 12 | 31 | 31 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026, 2026-2027 |
| Biyoloji | MEB 2018 | `meb-2018.biyoloji.9-12` | 9 | 11 | 11 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | MEB 2018 | `meb-2018.biyoloji.9-12` | 10 | 17 | 17 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025 |
| Biyoloji | MEB 2018 | `meb-2018.biyoloji.9-12` | 11 | 34 | 34 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026 |
| Biyoloji | MEB 2018 | `meb-2018.biyoloji.9-12` | 12 | 29 | 29 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2024-2025, 2025-2026, 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.5-8` | 5 | 23 | 23 | 0 | 0 | 23 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.5-8` | 6 | 24 | 24 | 0 | 0 | 24 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.5-8` | 7 | 30 | 30 | 0 | 0 | 30 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.5-8` | 8 | 23 | 23 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fen Bilimleri | Maarif Modeli (2026) | `tymm-2026.fen-bilimleri.3-8` | 5 | 27 | 27 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fen Bilimleri | Maarif Modeli (2026) | `tymm-2026.fen-bilimleri.3-8` | 6 | 36 | 36 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fen Bilimleri | Maarif Modeli (2026) | `tymm-2026.fen-bilimleri.3-8` | 7 | 35 | 35 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fen Bilimleri | Maarif Modeli (2026) | `tymm-2026.fen-bilimleri.3-8` | 8 | 43 | 43 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.9-12` | 9 | 20 | 20 | 0 | 0 | 20 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.9-12` | 10 | 21 | 21 | 0 | 0 | 21 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.9-12` | 11 | 15 | 15 | 0 | 0 | 15 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.9-12` | 12 | 21 | 21 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fizik | Maarif Modeli (2026) | `tymm-2026.fizik.9-12` | 9 | 24 | 24 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fizik | Maarif Modeli (2026) | `tymm-2026.fizik.9-12` | 10 | 22 | 22 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fizik | Maarif Modeli (2026) | `tymm-2026.fizik.9-12` | 11 | 33 | 33 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fizik | Maarif Modeli (2026) | `tymm-2026.fizik.9-12` | 12 | 27 | 27 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Kimya | Maarif Modeli (2026) | `tymm-2026.kimya.9-12` | 9 | 23 | 23 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Kimya | Maarif Modeli (2026) | `tymm-2026.kimya.9-12` | 10 | 21 | 21 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Kimya | Maarif Modeli (2026) | `tymm-2026.kimya.9-12` | 11 | 25 | 25 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Kimya | Maarif Modeli (2026) | `tymm-2026.kimya.9-12` | 12 | 24 | 24 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | Maarif Modeli (2026) | `tymm-2026.biyoloji.9-12` | 9 | 14 | 14 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Biyoloji | Maarif Modeli (2026) | `tymm-2026.biyoloji.9-12` | 10 | 19 | 19 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Biyoloji | Maarif Modeli (2026) | `tymm-2026.biyoloji.9-12` | 11 | 22 | 22 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Biyoloji | Maarif Modeli (2026) | `tymm-2026.biyoloji.9-12` | 12 | 20 | 20 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.fen-lisesi-matematik.9-12` | 9 | bilinmiyor | 46 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.fen-lisesi-matematik.9-12` | 10 | bilinmiyor | 27 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.fen-lisesi-matematik.9-12` | 11 | bilinmiyor | 29 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.fen-lisesi-matematik.9-12` | 12 | bilinmiyor | 38 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fizik | MEB 2018 | `meb-2018.fen-lisesi-fizik.9-12` | 9 | 44 | 44 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fizik | MEB 2018 | `meb-2018.fen-lisesi-fizik.9-12` | 10 | 41 | 41 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fizik | MEB 2018 | `meb-2018.fen-lisesi-fizik.9-12` | 11 | 68 | 68 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fizik | MEB 2018 | `meb-2018.fen-lisesi-fizik.9-12` | 12 | 83 | 83 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Kimya | MEB 2018 | `meb-2018.fen-lisesi-kimya.9-12` | 9 | 42 | 42 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Kimya | MEB 2018 | `meb-2018.fen-lisesi-kimya.9-12` | 10 | 26 | 26 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Kimya | MEB 2018 | `meb-2018.fen-lisesi-kimya.9-12` | 11 | 35 | 35 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Kimya | MEB 2018 | `meb-2018.fen-lisesi-kimya.9-12` | 12 | 32 | 32 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Biyoloji | MEB 2018 | `meb-2018.fen-lisesi-biyoloji.9-12` | 9 | 12 | 12 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | MEB 2018 | `meb-2018.fen-lisesi-biyoloji.9-12` | 10 | 17 | 17 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | MEB 2018 | `meb-2018.fen-lisesi-biyoloji.9-12` | 11 | 35 | 35 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | MEB 2018 | `meb-2018.fen-lisesi-biyoloji.9-12` | 12 | 31 | 31 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |

## Uygulama takvimi (doğrulanmış kaynaklar)

| Öğretim yılı | Kademe | Sınıflar | Çerçeve | Program belgesi | Kanıt |
| --- | --- | --- | --- | --- | --- |
| 2026-2027 | ortaokul | 5, 6, 7 | Maarif Modeli (2026) | `tymm-2026.matematik.5-8`, `tymm-2026.fen-bilimleri.3-8` | açık — [Temel Eğitim Taslak Çerçeve Planları - Türkiye Yüzyılı Maarif Modeli](https://tymm.meb.gov.tr/taslak-cerceve-planlari/temel-egitim) |
| 2026-2027 | ortaokul | 8 | MEB 2018 | `meb-2018.matematik.1-8`, `meb-2018.fen-bilimleri.3-8` | açık — [Antalya Ölçme Değerlendirme Merkezi (MEB): 2026-2027 Maarif Modeli taslak çerçeve planlar duyurusu (03.09.2026)](https://antalyaodm.meb.gov.tr/www/2026-2027-egitim-ogretim-yili-turkiye-yuzyili-maarif-modeli-taslak-cerceve-planlar-yayimlandi/icerik/172/tr) |
| 2026-2027 | ortaogretim | 9, 10, 11 | Maarif Modeli (2026) | `tymm-2026.matematik.9-12`, `tymm-2026.fizik.9-12`, `tymm-2026.kimya.9-12`, `tymm-2026.biyoloji.9-12` | açık — [Ortaöğretim Taslak Çerçeve Planları - Türkiye Yüzyılı Maarif Modeli](https://tymm.meb.gov.tr/taslak-cerceve-planlari/ortaogretim) |
| 2026-2027 | ortaogretim | 12 | MEB 2018 | `meb-2018.matematik.9-12`, `meb-2018.fizik.9-12`, `meb-2018.kimya.9-12`, `meb-2018.biyoloji.9-12` | açık — [Ortaöğretim Taslak Çerçeve Planları - Türkiye Yüzyılı Maarif Modeli](https://tymm.meb.gov.tr/taslak-cerceve-planlari/ortaogretim) |
| 2025-2026 | ortaokul | 5, 6 | Maarif Modeli (2026) | kayıtta yok | açık — [2025-2026 Eğitim ve Öğretim Yılı'na İlişkin İş ve İşlemler genelgesi (2025/63, 18.08.2025)](https://mevzuat.meb.gov.tr/dosyalar/2288.pdf) |
| 2025-2026 | ortaogretim | 9, 10 | Maarif Modeli (2026) | kayıtta yok | açık — [2025-2026 Eğitim ve Öğretim Yılı'na İlişkin İş ve İşlemler genelgesi (2025/63, 18.08.2025)](https://mevzuat.meb.gov.tr/dosyalar/2288.pdf) |
| 2026-2027 | ortaogretim | 9, 10, 11 | Maarif Modeli (2026) | `tymm-2026.matematik.9-12`, `tymm-2026.fizik.9-12`, `tymm-2026.kimya.9-12`, `tymm-2026.biyoloji.9-12` | açık — [Ortaöğretim Taslak Çerçeve Planları - Türkiye Yüzyılı Maarif Modeli](https://tymm.meb.gov.tr/taslak-cerceve-planlari/ortaogretim) |
| 2026-2027 | ortaogretim | 12 | MEB 2018 | `meb-2018.fen-lisesi-matematik.9-12`, `meb-2018.fen-lisesi-fizik.9-12`, `meb-2018.fen-lisesi-kimya.9-12`, `meb-2018.fen-lisesi-biyoloji.9-12` | açık — [Antalya Ölçme Değerlendirme Merkezi (MEB): 2026-2027 Maarif Modeli taslak çerçeve planlar duyurusu (03.09.2026)](https://antalyaodm.meb.gov.tr/www/2026-2027-egitim-ogretim-yili-turkiye-yuzyili-maarif-modeli-taslak-cerceve-planlar-yayimlandi/icerik/172/tr) |
| 2025-2026 | ortaokul | 7, 8 | MEB 2018 | `meb-2018.matematik.1-8`, `meb-2018.fen-bilimleri.3-8` | dışlama yoluyla — [2025-2026 Eğitim ve Öğretim Yılı'na İlişkin İş ve İşlemler genelgesi (2025/63, 18.08.2025)](https://mevzuat.meb.gov.tr/dosyalar/2288.pdf) |
| 2025-2026 | ortaogretim | 11, 12 | MEB 2018 | `meb-2018.matematik.9-12`, `meb-2018.fizik.9-12`, `meb-2018.kimya.9-12`, `meb-2018.biyoloji.9-12` | dışlama yoluyla — [2025-2026 Eğitim ve Öğretim Yılı'na İlişkin İş ve İşlemler genelgesi (2025/63, 18.08.2025)](https://mevzuat.meb.gov.tr/dosyalar/2288.pdf) |
| 2024-2025 | ortaokul | 5 | Maarif Modeli (2026) | kayıtta yok | açık — [2024-2025 Eğitim ve Öğretim Yılı Türkiye Yüzyılı Maarif Modeli'ne İlişkin İş ve İşlemler genelgesi (2024/54, 16.08.2024)](https://mevzuat.meb.gov.tr/dosyalar/2230.pdf) |
| 2024-2025 | ortaogretim | 9 | Maarif Modeli (2026) | kayıtta yok | açık — [2024-2025 Eğitim ve Öğretim Yılı Türkiye Yüzyılı Maarif Modeli'ne İlişkin İş ve İşlemler genelgesi (2024/54, 16.08.2024)](https://mevzuat.meb.gov.tr/dosyalar/2230.pdf) |
| 2024-2025 | ortaokul | 6, 7, 8 | MEB 2018 | `meb-2018.matematik.1-8`, `meb-2018.fen-bilimleri.3-8` | dışlama yoluyla — [2024-2025 Eğitim ve Öğretim Yılına İlişkin İş ve İşlemler genelgesi (2024/53, 14.08.2024)](https://mevzuat.meb.gov.tr/dosyalar/2229.pdf) |
| 2024-2025 | ortaogretim | 10, 11, 12 | MEB 2018 | `meb-2018.matematik.9-12`, `meb-2018.fizik.9-12`, `meb-2018.kimya.9-12`, `meb-2018.biyoloji.9-12` | dışlama yoluyla — [2024-2025 Eğitim ve Öğretim Yılına İlişkin İş ve İşlemler genelgesi (2024/53, 14.08.2024)](https://mevzuat.meb.gov.tr/dosyalar/2229.pdf) |

## Sınav kapsamı

Sınav kapsamı okul programından ayrı sürümlenir. Doğrulanmamış kapsam hiçbir kazanımı sınava bağlamaz.

| Kimlik | Sınav | Yıl | Durum | Sınıf | Not |
| --- | --- | --- | --- | --- | --- |
| `lgs-2026` | LGS | 2026 | doğrulandı | 8 | Kapsam 8. sınıf programına bağlanır; hangi kazanımların sınavda yer alacağını tek tek belirlemez. |
| `lgs-2027` | LGS | 2027 | doğrulandı | 8 | Sınıf düzeyi kapsamı (8. sınıf programları) doğrulandı. Program sürümü 2026-2027 uygulama kuralından türetilir (8. sınıf: MEB 2018). Kazanım düzeyinde liste ve dönem sınırı yayımlanmadı. |
| `tyt-2027` | TYT | 2027 | doğrulanmadı | — | Sınav tarihi ÖSYM'den doğrulandı. Kapsamın hangi program sürümüne ve konulara dayandığı resmî olarak doğrulanmadı; kapsam tarihten türetilmez. Mezun adaylar okul programı yerine sınav kapsamıyla değerlendirilir. |
| `ayt-2027` | AYT | 2027 | doğrulanmadı | — | Sınav tarihi ÖSYM'den doğrulandı. Kapsamın hangi program sürümüne ve konulara dayandığı resmî olarak doğrulanmadı; kapsam tarihten türetilmez. Mezun adaylar okul programı yerine sınav kapsamıyla değerlendirilir. |

## Sınav kapsam katmanları (TA-007)

Tarih, sınıf düzeyi, program sürümü ve kazanım düzeyi kapsam ayrı ayrı doğrulanır; biri diğerinin kanıtı değildir.

| Kimlik | Tarih | Tarih durumu | Sınıf/genel kapsam | Program kapsamı | Kazanım kapsamı |
| --- | --- | --- | --- | --- | --- |
| `lgs-2026` | 2026-06-13 | unverified | verified | unverified | unverified |
| `lgs-2027` | 2027-06-13 | verified | verified | derived | unverified |
| `tyt-2027` | 2027-06-19 | verified | unverified | unverified | unverified |
| `ayt-2027` | 2027-06-20 | verified | unverified | unverified | unverified |

## İzlekler

Fen lisesi ve temel düzey programları yalnız açık okul türü beyanıyla seçilir; beyan yoksa genel program kullanılır ve
bu çözümlemede `track_unspecified_general_assumed` gerekçesiyle yazılır.

| Program | İzlek | Sınıflar |
| --- | --- | --- |
| `meb-2018.biyoloji.9-12` | general | 9, 10, 11, 12 |
| `meb-2018.fen-bilimleri.3-8` | general | 5, 6, 7, 8 |
| `meb-2018.fen-lisesi-biyoloji.9-12` | science_high_school | 9, 10, 11, 12 |
| `meb-2018.fen-lisesi-fizik.9-12` | science_high_school | 9, 10, 11, 12 |
| `meb-2018.fen-lisesi-kimya.9-12` | science_high_school | 9, 10, 11, 12 |
| `meb-2018.fen-lisesi-matematik.9-12` | science_high_school | 9, 10, 11, 12 |
| `meb-2018.fizik.9-12` | general | 9, 10, 11, 12 |
| `meb-2018.kimya.9-12` | general | 9, 10, 11, 12 |
| `meb-2018.matematik.1-8` | general | 5, 6, 7, 8 |
| `meb-2018.matematik.9-12` | general | 9, 10, 11, 12 |
| `tymm-2026.biyoloji.9-12` | general | 9, 10, 11, 12 |
| `tymm-2026.fen-bilimleri.3-8` | general | 5, 6, 7, 8 |
| `tymm-2026.fizik.9-12` | general | 9, 10, 11, 12 |
| `tymm-2026.kimya.9-12` | general | 9, 10, 11, 12 |
| `tymm-2026.matematik.5-8` | general | 5, 6, 7, 8 |
| `tymm-2026.matematik.9-12` | general | 9, 10, 11, 12 |

## Bekleyen programlar (kayda alınmadı)

| Kimlik | Başlık | Neden | Ayrıntı | Denetim tarihi |
| --- | --- | --- | --- | --- |
| `tymm-2024.mat5678` | Maarif Modeli Ortaokul Matematik (5-8) · 2024 onaylı | http_error | Resmî adres 2026-11-24'te HTTP 500 döndürdü (dosya boş). Erişim kısıtlaması aşılmadı. 2024 sürümü 2026 sürümünün yerine geçmez; 2025-2026'da hangi baskının okutulduğu ayrıca doğrulanmalı. | 2026-11-24 |
| `tymm-2024.math9101112` | Maarif Modeli Matematik (Hazırlık, 9-12) · 2024 onaylı | http_error | Resmî adres 2026-11-24'te HTTP 500 döndürdü (dosya boş). Erişim kısıtlaması aşılmadı. 2024 sürümü 2026 sürümünün yerine geçmez; 2025-2026'da hangi baskının okutulduğu ayrıca doğrulanmalı. | 2026-11-24 |
| `tymm-2024.fiz9101112` | Maarif Modeli Fizik (9-12) · 2024 onaylı | http_error | Resmî adres 2026-11-24'te HTTP 500 döndürdü (dosya boş). Erişim kısıtlaması aşılmadı. 2024 sürümü 2026 sürümünün yerine geçmez; 2025-2026'da hangi baskının okutulduğu ayrıca doğrulanmalı. | 2026-11-24 |
| `tymm-2024.kim9101112` | Maarif Modeli Kimya (9-12) · 2024 onaylı | http_error | Resmî adres 2026-11-24'te HTTP 500 döndürdü (dosya boş). Erişim kısıtlaması aşılmadı. 2024 sürümü 2026 sürümünün yerine geçmez; 2025-2026'da hangi baskının okutulduğu ayrıca doğrulanmalı. | 2026-11-24 |
| `tymm-2024.biy9101112` | Maarif Modeli Biyoloji (9-12) · 2024 onaylı | http_error | Resmî adres 2026-11-24'te HTTP 500 döndürdü (dosya boş). Erişim kısıtlaması aşılmadı. 2024 sürümü 2026 sürümünün yerine geçmez; 2025-2026'da hangi baskının okutulduğu ayrıca doğrulanmalı. | 2026-11-24 |
| `tymm-2024.fen345678` | Maarif Modeli Fen Bilimleri (3-8) · 2024 onaylı | http_error | Resmî adres 2026-11-24'te HTTP 500 döndürdü (dosya boş). Erişim kısıtlaması aşılmadı. 2024 sürümü 2026 sürümünün yerine geçmez; 2025-2026'da hangi baskının okutulduğu ayrıca doğrulanmalı. | 2026-11-24 |
| `tymm-2026.temel-matematik.11-12` | [TYMM] Ortaöğretim Temel Matematik Dersi (11-12) (2026), PID=2181 | inconsistent_codes | PDF indirildi (sha256 c73dd4d8…). Belgede iki farklı kod öneki geçer (MAT.T.11… ve T.MAT.11…); hangisinin resmî olduğu elle doğrulanmadan kod uydurulmaz. | 2026-11-24 |
| `meb-2018.temel-duzey-matematik.11-12` | MEB 2018 Ortaöğretim Matematik — Temel Düzey bölümü (TD.11, TD.12), PID=343 | extraction_unreliable | Kodlar bulundu (11. sınıf 15, 12. sınıf 5) ancak ünite/konu başlıkları tablo hücreleriyle karışıyor ve 12. sınıf eksik görünüyor; elle sayfa incelemesi gerekir. | 2026-11-24 |
| `maarif-hazirlik.matematik` | Maarif Modeli hazırlık sınıfı matematik öğrenme çıktıları (PID=2256 içinde) | not_downloaded | Hazırlık sınıfı sınıf numarası taşımadığı için 5-12 sınıf modeline henüz eşlenmedi; belge kayıtlı (tymm-2026.matematik.9-12). | 2026-11-24 |

## Konu taksonomisi kapsamı

Taksonomi sürümü `1.0.0`, 67 konu (biology 11, chemistry 11, geometry 6, mathematics 20, physics 14, science 5). Eşlemeler AI
taslağıdır; incelenmeden müfredat denetimini tek başına geçirmez. Birden çok konuya düşen kazanımlar açıkça sayılır.

| Program | Kazanım | Bir konuya eşlenen | Eşlenmeyen | Birden çok konuya düşen |
| --- | --- | --- | --- | --- |
| `meb-2018.biyoloji.9-12` | 91 | 91 | 0 | 37 |
| `meb-2018.fen-bilimleri.3-8` | 223 | 223 | 0 | 217 |
| `meb-2018.fen-lisesi-biyoloji.9-12` | 95 | 95 | 0 | 38 |
| `meb-2018.fen-lisesi-fizik.9-12` | 236 | 233 | 3 | 165 |
| `meb-2018.fen-lisesi-kimya.9-12` | 135 | 103 | 32 | 35 |
| `meb-2018.fen-lisesi-matematik.9-12` | 140 | 126 | 14 | 56 |
| `meb-2018.fizik.9-12` | 213 | 210 | 3 | 145 |
| `meb-2018.kimya.9-12` | 127 | 99 | 28 | 38 |
| `meb-2018.matematik.1-8` | 215 | 189 | 26 | 86 |
| `meb-2018.matematik.9-12` | 130 | 120 | 10 | 50 |
| `tymm-2026.biyoloji.9-12` | 75 | 69 | 6 | 0 |
| `tymm-2026.fen-bilimleri.3-8` | 141 | 131 | 10 | 90 |
| `tymm-2026.fizik.9-12` | 106 | 94 | 12 | 39 |
| `tymm-2026.kimya.9-12` | 93 | 36 | 57 | 0 |
| `tymm-2026.matematik.5-8` | 100 | 58 | 42 | 1 |
| `tymm-2026.matematik.9-12` | 77 | 61 | 16 | 2 |

Eşlenmeyen bilgi konusu: yok.

## TA-006 → TA-007

| Ölçü | TA-006 | TA-007 |
| --- | --- | --- |
| Program sürümü | 12 | 16 |
| Kazanım/öğrenme çıktısı | 1591 | 2197 |
| Beklenen sayısı bilinen sınıf hücresi | 33 | 60 |
| Beklenen sayısı bilinmeyen hücre | 11 | 4 |
| Açık kanıtlı uygulama kuralı | — | 10 |
| Dışlamayla uygulama kuralı | — | 4 |
| Bekleyen program | — | 9 |


## Durum ayrımı

| Düzey | Sayı |
| --- | --- |
| Şemada temsil edilebilir | 5–12. sınıf, 5 alan, iki çerçeve, sınırsız sürüm |
| Kayıtlı (kod, başlık, sayfa) | 2197 |
| Kaynağa dayalı (resmî belge + sayfa) | 2197 |
| Bağımsız incelenmiş | 0 |
| Özgün betimlemeli (incelenmemiş) | 133 |
| Ders bağlamına girebilir (resmî kod/başlık, çözümlenmiş program, eşleşen konu) | matematik: 2026-2027'de 5-12. sınıflar |
| Gerçek öğrenci veya sağlayıcıyla doğrulanmış | 0 |
