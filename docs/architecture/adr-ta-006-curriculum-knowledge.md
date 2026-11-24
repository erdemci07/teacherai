# ADR TA-006: Müfredat Kaydı v2, bilimsel bilgi kaydı ve çalışma zamanı eğitim bağlamı

Durum: kabul edildi ve uygulandı (TA-006). Tasarım hazırlığı: [adr-ta-006-scientific-knowledge-architecture.md](adr-ta-006-scientific-knowledge-architecture.md). Bu ADR o kararları kodla somutlaştırır; beş temel ve "sabit oran yok" ilkesi aynen geçerlidir.

## Bağlam

TA-005'te yalnız 8. sınıf matematik için 29 kaynaklı kazanım ve 5 taslak yöntem politikası vardı. TeacherAI'nin dört branşta (matematik, fizik, kimya, biyoloji) ve ortaokul fende müfredata duyarlı, kaynağa dayalı bağlam kullanabilmesi için sürümlenmiş bir müfredat kaydı, haklarıyla kayıtlı bir kaynak kaydı ve taslak/onay ayrımı olan bir bilgi kaydı gerekiyordu.

## Karar 1: Program içeriği, uygulama takvimi ve sınav kapsamı ayrı sürümlenir

- `ProgramVersion`: belge (başlık, resmî adres, dosya adresi, sha256, sayfa sayısı, tarih notu, hak durumu, metin politikası), kapsanan sınıflar, resmî terim (kazanım / öğrenme çıktısı), okunabildiyse beklenen sayılar.
- `ApplicationRule`: öğretim yılı × sınıf × çerçeve × program; kanıt türü `explicit` veya `by_exclusion` ve resmî alıntı özeti.
- `ExamScope`: LGS/TYT/AYT kapsamı; `unverified` kapsam hiçbir kazanımı sınava bağlamaz.
- Taslak yıllık planlar program sürümü olarak kaydedilemez (`status: final` zorunlu).

## Karar 2: Küresel kimlik ve modüler veri

- Kimlik `<program_id>::<resmî kod (ASCII)>` (ör. `tymm-2026.fizik.9-12::FIZ.10.3.3`). Aynı resmî kod (`9.1.1.1`) dört programda dört ayrı kayıttır.
- Veri `features/curriculum/data/catalog.json` + program başına `programs/<id>.json` + özgün betimlemeler `descriptions/<id>.json`. Küresel kayıt boyutu sınırı yoktur.
- Program dosyaları `scripts/curriculum_extract.py` ile resmî PDF'ten belirlenimci üretilir (pdftotext + kod deseni). PDF depoya alınmaz; sha256 kaydedilir.
- **Metin politikası:** MEB belgelerinde lisans ifadesi bulunmadığı için resmî kazanım cümleleri kopyalanmadı. Kayıtlar kod, üst başlık (ünite/tema/konu adı) ve PDF sayfası taşır. TA-005'in 29 birebir metni korunur (`legacy_verbatim_pending_review`) ama öğrenciye ve isteme gönderilmez.

## Karar 3: v1 korunur, v2 göçü belirlenimcidir

`curriculum/registry.py` ve v1 sözleşmesi değişmedi; yöntem/müfredat denetimi v1'le aynı çalışır. v2 yüklenirken v1'in 29 kazanımı aynı resmî kodlu v2 kaydına bindirilir (metin + v1 konu anahtarı takma ad), 5 politika `MethodPolicyV2`'ye taşınır (`legacy_id`). Göç testi metnin değişmediğini ve iki yüklemenin aynı özeti verdiğini doğrular.

## Karar 4: Doğrulama sorunları toplu raporlanır

Yinelenen kimlik/resmî kod, tanımsız ünite/ön koşul/ilişki, farklı çerçeveden ön koşul (sürüm uyuşmazlığı), ön koşul döngüsü, kod-sınıf uyuşmazlığı, alan/terim uyuşmazlığı, aynı yıl-sınıf-alan için iki program, v1 kaydının v2'de bulunmaması. `python -m scripts.curriculum_registry --check` CI'da çalışır.

## Karar 5: Belirlenimci program çözümlemesi

Girdi yalnız beyan/profil bağlamıdır: alan, sınıf, öğretim yılı (beyan veya sunucu saati), öğrenci/mezun durumu, sınav hedefi, isteğe bağlı açık program. Sonuç `resolved`, `ambiguous` veya `unresolved` ve gerekçe listesidir. Sınıf veya mezuniyet görselden çıkarılmaz. Mezun + AYT, doğrulanmış kapsam olmadıkça `ambiguous`; Temmuz–Ağustos'ta öğretim yılı beyan edilmediyse `academic_year_transition`.

## Karar 6: Bilimsel kaynak ve bilgi kaydı

- `SourceRecord`: dört ayrı izin; lisans doğrulanmadan izin verilmez (sözleşme düzeyinde).
- `KnowledgeEntry`: tür (gerçek, yasa, tanım, teorem, ilişki, süreç, deneysel ilke, yöntem), özgün ifade, gösterim, nicelikler, koşullar, varsayımlar, istisnalar, ön koşullar, kazanım bağları, yapı-işlev, kavram yanılgıları, **ayrı** pedagojik sadeleştirmeler, görsel türleri, denetleyici bağlantıları, kaynak konumu, inceleme kayıtları. Yasa kaydı geçerlilik koşulu yazmak zorundadır.
- İnceleme akışı: `draft → source_verified → in_review → revision_requested/approved/rejected → superseded`. Durum son kararla uyuşmak zorundadır. Onay yalnız aynı sürümü inceleyen öğretmen veya alan uzmanıyla ve kaynaklı girdide verilir; inceleyen başvurusu `teacher:|expert:|owner:` ile başlar, AI taslağı kendini onaylayamaz.

## Karar 7: Denetleyici bağlantısı kısmidir

`knowledge/capabilities.py` 22 denetleyici kimliğini gerçek fonksiyonlara bağlar ve her biri için "kanıtlar / kanıtlamaz" yazar. Girdi düzeyinde iddia durumu yalnız `partially_checked` veya `not_checked` olabilir; `passed` yapısal olarak oluşamaz. Boyut doğruluğu yasa seçimini, atom korunumu tepkimenin gerçekleşmesini, dizi denetimi biyolojik işlevi kanıtlamaz.

## Karar 8: Çalışma zamanı bağlamı

`curriculum/context.py → select`:

- Konu anahtarı sağlayıcı etiketinden değil, kaynak ifadelerin yapısından (`registry.topic_of`) gelir; kazanımlar konu anahtarı veya takma adla eşleşir.
- Yük: program etiketi, çerçeve, yıl, sınıf, en çok 4 kazanımın resmî kodu ve ünite/konu başlığı, en çok 3 **onaylı** bilgi girdisi; ≤ 1500 bayt; acil sıkıştırmada düşer. İncelenmemiş betimleme ve resmî metin gönderilmez.
- Çözümleme `resolved` değilse veya eşleşme yoksa istem bayt bayt aynı kalır. Ek sağlayıcı çağrısı, gömme, vektör veritabanı veya Firestore okuması yoktur; profil zaten okunan tek belgedir.
- `GeneratedLesson.educational_provenance`: kayıt sürümleri (özetli), çözümleme, konu anahtarı, eşleşme türü, seçilen kazanım ve bilgi kimlikleri, dışarıda bırakılan taslak sayısı, yük boyutu. Ders kaydıyla saklanır; kayıt veya profil değişince eski ders yeniden hesaplanmaz. Seçilen kazanımlar `EducationContext.references` içine de yazılır (v2 görünümünde `unreviewed`).
- Sağlayıcı bu bağlamı kullanabilir; onay, müfredat veya doğrulama durumu belirleyemez (çıktı şemasında böyle alan yoktur).

## Karar 9: Ders amacı ile sunum ayrıdır

`LessonIntent` (soru çözümü, konu anlatımı, konuşma, etkileşimli tahta, pratik, geri bildirim, sesli anlatım) `LessonView`'dan ayrıdır. Konu anlatımı soru gerektirmez ve soruya bağlanamaz. `mode_support` hangi kipin bugün çalıştığını ve hangisinin hangi faza ait olduğunu söyler; FKB'de üretim `subject_generation_unavailable` kalır.

## Karar 10: Veri ayrımı

`evals/datasets/TA-006-manifest.json` bilgi, müfredat, öğretmen katkısı, geliştirme fikstürü, alıştırma, bağımsız değerlendirme, öğretmen anahtarı ve OCR varyantlarını ayırır. `generation_context: false` yolların çalışma zamanı kodunda anılmadığı ve bağımsız 24 soruyla üretim bağlamı kayıtları arasında 6-kelimelik örtüşme olmadığı `python -m scripts.dataset_manifest --check` ile denetlenir.

## Sonuçlar

- Müfredat kapsamı resmî tablolarla eşleşir (okunabilen 33 hücrede eksik 0); resmî metin olmadan öğrenciye "kazanım metni" gösterilemez.
- Bilgi kaydı dengeli ama tamamen taslaktır; çalışma zamanına uygun girdi 0'dır. TA-007 öğretmen incelemesi bu sayıyı değiştirecek tek yoldur.
- Gelecekte geri getirme ihtiyacı ölçülürse vektör araması bu belirlenimci seçimin yerine değil, arkasına eklenir.

## Reddedilenler

- Resmî kazanım metninin izinsiz toplu kopyalanması
- İsteğe her ders için bütün kaydın eklenmesi; gömme/vektör araması (bu faz)
- Sınıf veya mezuniyetin görselden tahmini
- AI taslak politikalarının ve bilgi girdilerinin otomatik onayı
- Sabit çalışma zamanı yüzdeleri
