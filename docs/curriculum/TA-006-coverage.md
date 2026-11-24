# TA-006 müfredat kapsam raporu

Bu dosya `python -m scripts.curriculum_registry` ile üretilir; elle düzenlenmez. CI `--check` ile eskimiş raporu reddeder.

- Kayıt sürümü: `2.0.0+e39f0c37a4ad`
- Program sürümü: 12 · başlık (ünite/tema/konu): 602 · kazanım/öğrenme çıktısı: 1591
- Disiplin dağılımı: biology 166, chemistry 220, geometry 165, mathematics 357, physics 319, science 364
- Yöntem politikası: 5 (hepsi `draft`; v1'den göç)

Sütunlar: **beklenen** resmî sayı tablosundan okunabildiyse yazılır, okunamadıysa `bilinmiyor` kalır. **eksik** yalnız beklenen
sayı biliniyorsa hesaplanır. **resmî metin** TA-005'ten korunan birebir kazanım metnidir (hak incelemesi bekliyor).
**betimleme** özgün, incelenmemiş kısa açıklamadır. **incelenen** bağımsız insan incelemesinden geçmiş kayıt sayısıdır.
**uygulama** doğrulanmış resmî kaynağa göre o sınıfta programın okutulduğu öğretim yıllarıdır.

| Alan | Çerçeve | Program | Sınıf | Beklenen | Kayıtlı | Eksik | Resmî metin | Betimleme | İncelenen | Kaynak | Uygulama |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Matematik | MEB 2018 | `meb-2018.matematik.1-8` | 5 | bilinmiyor | 56 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.matematik.1-8` | 6 | bilinmiyor | 59 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.matematik.1-8` | 7 | bilinmiyor | 48 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.matematik.1-8` | 8 | 52 | 52 | 0 | 29 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fen Bilimleri | MEB 2018 | `meb-2018.fen-bilimleri.3-8` | 5 | 36 | 36 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fen Bilimleri | MEB 2018 | `meb-2018.fen-bilimleri.3-8` | 6 | 59 | 59 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fen Bilimleri | MEB 2018 | `meb-2018.fen-bilimleri.3-8` | 7 | 67 | 67 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fen Bilimleri | MEB 2018 | `meb-2018.fen-bilimleri.3-8` | 8 | 61 | 61 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | MEB 2018 | `meb-2018.matematik.9-12` | 9 | 41 | 41 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.matematik.9-12` | 10 | 27 | 27 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.matematik.9-12` | 11 | 28 | 28 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Matematik | MEB 2018 | `meb-2018.matematik.9-12` | 12 | 34 | 34 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Fizik | MEB 2018 | `meb-2018.fizik.9-12` | 9 | 44 | 44 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fizik | MEB 2018 | `meb-2018.fizik.9-12` | 10 | 39 | 39 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fizik | MEB 2018 | `meb-2018.fizik.9-12` | 11 | 62 | 62 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Fizik | MEB 2018 | `meb-2018.fizik.9-12` | 12 | bilinmiyor | 68 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Kimya | MEB 2018 | `meb-2018.kimya.9-12` | 9 | 38 | 38 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Kimya | MEB 2018 | `meb-2018.kimya.9-12` | 10 | 23 | 23 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Kimya | MEB 2018 | `meb-2018.kimya.9-12` | 11 | bilinmiyor | 35 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Kimya | MEB 2018 | `meb-2018.kimya.9-12` | 12 | 31 | 31 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Biyoloji | MEB 2018 | `meb-2018.biyoloji.9-12` | 9 | 11 | 11 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | MEB 2018 | `meb-2018.biyoloji.9-12` | 10 | 17 | 17 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | MEB 2018 | `meb-2018.biyoloji.9-12` | 11 | 34 | 34 | 0 | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | MEB 2018 | `meb-2018.biyoloji.9-12` | 12 | 29 | 29 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.5-8` | 5 | 23 | 23 | 0 | 0 | 23 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.5-8` | 6 | 24 | 24 | 0 | 0 | 24 | 0 | erişildi (sha256) | 2026-2027 |
| Matematik | Maarif Modeli (2026) | `tymm-2026.matematik.5-8` | 7 | bilinmiyor | 30 | bilinmiyor | 0 | 30 | 0 | erişildi (sha256) | 2026-2027 |
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
| Kimya | Maarif Modeli (2026) | `tymm-2026.kimya.9-12` | 9 | bilinmiyor | 23 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Kimya | Maarif Modeli (2026) | `tymm-2026.kimya.9-12` | 10 | bilinmiyor | 21 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Kimya | Maarif Modeli (2026) | `tymm-2026.kimya.9-12` | 11 | bilinmiyor | 25 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Kimya | Maarif Modeli (2026) | `tymm-2026.kimya.9-12` | 12 | bilinmiyor | 24 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |
| Biyoloji | Maarif Modeli (2026) | `tymm-2026.biyoloji.9-12` | 9 | 14 | 14 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Biyoloji | Maarif Modeli (2026) | `tymm-2026.biyoloji.9-12` | 10 | 19 | 19 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Biyoloji | Maarif Modeli (2026) | `tymm-2026.biyoloji.9-12` | 11 | 22 | 22 | 0 | 0 | 0 | 0 | erişildi (sha256) | 2026-2027 |
| Biyoloji | Maarif Modeli (2026) | `tymm-2026.biyoloji.9-12` | 12 | bilinmiyor | 20 | bilinmiyor | 0 | 0 | 0 | erişildi (sha256) | doğrulanmadı |

## Uygulama takvimi (doğrulanmış kaynaklar)

| Öğretim yılı | Kademe | Sınıflar | Çerçeve | Program belgesi | Kanıt |
| --- | --- | --- | --- | --- | --- |
| 2026-2027 | ortaokul | 5, 6, 7 | Maarif Modeli (2026) | `tymm-2026.matematik.5-8`, `tymm-2026.fen-bilimleri.3-8` | açık — [Temel Eğitim Taslak Çerçeve Planları - Türkiye Yüzyılı Maarif Modeli](https://tymm.meb.gov.tr/taslak-cerceve-planlari/temel-egitim) |
| 2026-2027 | ortaokul | 8 | MEB 2018 | `meb-2018.matematik.1-8`, `meb-2018.fen-bilimleri.3-8` | dışlama yoluyla — [Temel Eğitim Taslak Çerçeve Planları - Türkiye Yüzyılı Maarif Modeli](https://tymm.meb.gov.tr/taslak-cerceve-planlari/temel-egitim) |
| 2026-2027 | ortaogretim | 9, 10, 11 | Maarif Modeli (2026) | `tymm-2026.matematik.9-12`, `tymm-2026.fizik.9-12`, `tymm-2026.kimya.9-12`, `tymm-2026.biyoloji.9-12` | açık — [Ortaöğretim Taslak Çerçeve Planları - Türkiye Yüzyılı Maarif Modeli](https://tymm.meb.gov.tr/taslak-cerceve-planlari/ortaogretim) |
| 2026-2027 | ortaogretim | 12 | MEB 2018 | `meb-2018.matematik.9-12`, `meb-2018.fizik.9-12`, `meb-2018.kimya.9-12`, `meb-2018.biyoloji.9-12` | açık — [Ortaöğretim Taslak Çerçeve Planları - Türkiye Yüzyılı Maarif Modeli](https://tymm.meb.gov.tr/taslak-cerceve-planlari/ortaogretim) |
| 2025-2026 | ortaokul | 5, 6 | Maarif Modeli (2026) | kayıtta yok | açık — [2025-2026 Eğitim ve Öğretim Yılına İlişkin İş ve İşlemler genelgesi (MEB haberi)](https://www.meb.gov.tr/bakan-tekinin-imzasiyla-illere-giden-2025-2026-egitim-ve-ogretim-yilina-iliskin-is-ve-islemler-konulu-genelge-yayimlandi/haber/38072/tr) |
| 2025-2026 | ortaogretim | 9, 10 | Maarif Modeli (2026) | kayıtta yok | açık — [2025-2026 Eğitim ve Öğretim Yılına İlişkin İş ve İşlemler genelgesi (MEB haberi)](https://www.meb.gov.tr/bakan-tekinin-imzasiyla-illere-giden-2025-2026-egitim-ve-ogretim-yilina-iliskin-is-ve-islemler-konulu-genelge-yayimlandi/haber/38072/tr) |

## Sınav kapsamı

Sınav kapsamı okul programından ayrı sürümlenir. Doğrulanmamış kapsam hiçbir kazanımı sınava bağlamaz.

| Kimlik | Sınav | Yıl | Durum | Sınıf | Not |
| --- | --- | --- | --- | --- | --- |
| `lgs-2026` | LGS | 2026 | doğrulandı | 8 | Kapsam 8. sınıf programına bağlanır; hangi kazanımların sınavda yer alacağını tek tek belirlemez. |
| `lgs-2027` | LGS | 2027 | doğrulanmadı | — | 2027 LGS için resmî kapsam açıklaması bulunamadı. Sınav tarihi duyurulmuştur ancak kapsam doğrulanmadı. |
| `tyt-2027` | TYT | 2027 | doğrulanmadı | — | ÖSYM'nin 2027-YKS kapsamını hangi program sürümüne dayandırdığı resmî kaynaktan doğrulanmadı. |
| `ayt-2027` | AYT | 2027 | doğrulanmadı | — | ÖSYM'nin 2027-YKS kapsamını hangi program sürümüne dayandırdığı resmî kaynaktan doğrulanmadı. Mezun adaylar okul programı yerine sınav kapsamıyla değerlendirilir. |

## Durum ayrımı

| Düzey | Sayı |
| --- | --- |
| Şemada temsil edilebilir | 5–12. sınıf, 5 alan, iki çerçeve, sınırsız sürüm |
| Kayıtlı (kod, başlık, sayfa) | 1591 |
| Kaynağa dayalı (resmî belge + sayfa) | 1591 |
| Bağımsız incelenmiş | 0 |
| Özgün betimlemeli (incelenmemiş) | 133 |
| Ders bağlamına girebilir (resmî kod/başlık, çözümlenmiş program, eşleşen konu) | matematik: 2026-2027'de 5-12. sınıflar |
| Gerçek öğrenci veya sağlayıcıyla doğrulanmış | 0 |
