# TeacherAI proje bağlamı

TeacherAI genel amaçlı, çok disiplinli bir öğretmendir. Amaç, öğrencinin karşılaştığı bir sonraki soruyu bağımsız çözebilmesidir. Sınav hedefi öğrenci bağlamının isteğe bağlı bir alanıdır. Çalışan öğrenci akışları değişiklikler sırasında korunur.

| Durum | Kapsam |
| --- | --- |
| Uygulandı | Next.js/React/TypeScript öğrenci arayüzü, FastAPI/Pydantic modüler monoliti, Firebase Auth, Firestore, matematik görseli analizi, yapılandırılmış ders, BoardPlanner, KaTeX, ders sonrası etkileşim, geçmiş ve bağlantıyla paylaşım. TA-001 değişiklikleri yerel dalda doğrulanır. |
| Uygulandı (TA-002) | Ortak eğitim çekirdeği (`features/education`): kanonik alan kimlikleri, kökenli eğitim bağlamı, soru anlama sözleşmesi, LessonPlan v2, alan yetenek tablosu, boyut bazında doğrulama raporu. Matematik üretim hattı v2 projeksiyonunu her derste kurar. Sahibine özel salt okunur `GET /api/v1/lessons/{id}/v2` ve geçmişte v2 anlatım görünümü. Pydantic’ten üretilen JSON Schema ve TypeScript tipleri, CI eskime denetimi. |
| Uygulandı (TA-003) | Soru bütünlüğü motoru (`features/integrity`): sınırlı, dengeli ifade ayrıştırıcısı (kök, kesir, üs kapsamı, tekli eksi korunur), Türkçe soru amacı ve olumsuzluk işaretleri, yapılandırılmış seçenekler, kanıta dayalı önemlilik kararı, aynı istekte koşullu tek hedefli yeniden okuma, son çare öğrenci açıklaması (`POST /api/v1/vision/analyses/{id}/clarification`) ve sunucuya ait soru revizyonları. Kesin eşdeğerlikle seçenek uzlaştırması ve önce-çöz bağlamı. Mantıksal istek başına sağlayıcı çağrısı tavanı. Tahribatsız görüntü hazırlama ve tavsiye niteliğinde kalite göstergeleri. |
| Uygulandı (TA-004) | İstenen hedef (`AnswerTarget`) ve hedefe göre son cevap ve seçenek uzlaştırması (x = 3 iken x + 2 için 5). Kök doğrulama, yabancı kök, çözüm kaybı, eşitsizlik yönü, tanımlardan yerine koyma, iki bilinmeyende sabit oran, matematik öncül birleşimi. LessonPlan v2 2.2.0: `derivation_step`, blok kontrolleri, hedef çözümü, anlatım sözleşmesi, `ScientificProblemModel`. Eski OCR notları için önemlilik köprüsü ve zorunlu görselin metin yeterliliği. Bunlar gerçek matematik akışındadır. |
| Çevrimdışı denetim (TA-004) | Fizik, kimya ve biyoloji için `features/reasoning/` altında sınırlı yerel denetimler: birim/boyut, formül, grafik/tablo, atom/yük korunumu, denkleştirme, stokiyometri, etiket/sıra/ok, deney iddiaları, öncüller, DNA→mRNA. Sentetik matris ve 24 özgün soru paketi ile sınanır. Öğrenci akışına **bağlı değildir**. |
| Yalnızca sözleşme ve çevrimdışı fikstür | Fizik, kimya, biyoloji ve fen dersleri v2 ile temsil edilir ve çevrimdışı testlerde gösterilir. Bu alanlarda tanıma, ders üretimi, öğrenci akışında doğrulama ve pratik **çalışmaz**. Üretim isteği 422 `subject_generation_unavailable` alır. |
| Kısmi | MathAI sınırlı tek değişkenli gerçel denklemleri ve belirli grafik özelliklerini denetler. Sözel gerekçeler otomatik olarak kanıtlanmaz. Doğrulanabilir benzer denklem üretildiğinde öğrenci pratik yanıtı gönderebilir. Öğrenme hafızası mevcut etkileşim olaylarından oluşur. |
| Planlandı | Müfredat modülü ilgili eski programları ve Türkiye Yüzyılı Maarif Modeli’ni destekleyecek. Sınıf düzeyine uygun yöntemler açık politikalarla uygulanacak. Öğretmen bilgisi yapılandırılacak ve bağımsız incelemeden geçecek. Mobil istemci için ilk tercih Capacitor. |
| Ertelendi | Aşağıdaki yol haritasındaki TA-005 ve sonrası. 100 soruluk öğretmen incelemeli değerlendirme seti dış katkı olarak ertelendi. |
| Dış doğrulama bekliyor | Gerçek sağlayıcı kalite karşılaştırması, dağıtılmış sürüm, gerçek Firebase kimliği ve App Check geçişi. |

## Yol haritası

TA-002 sonrası numaralandırma (TA-003 ile güncellendi):

| Faz | Kapsam | Durum |
| --- | --- | --- |
| TA-001 / TA-001B | Temel ve son stabilizasyon | Tamamlandı |
| TA-002 | Ortak eğitim çekirdeği, LessonPlan v2 | Tamamlandı |
| TA-003 | Soru bütünlüğü ve görsel zekâ | Tamamlandı |
| TA-004 | Akıl yürütme ve doğrulama çekirdeği | Bu dal |
| TA-005 | Çok sağlayıcılı AI Gateway | Planlandı |
| TA-006 | Müfredat ve yöntem zekâsı | Planlandı |
| TA-007 | Uzman öğretmen bilgisi | Planlandı |
| TA-008 | İleri matematik ve geometri | Planlandı |
| TA-009 | Fizik zekâsı | Planlandı |
| TA-010 | Kimya zekâsı | Planlandı |
| TA-011 | Biyoloji ve fen zekâsı | Planlandı |
| TA-012 | Öğrenci zekâsı | Planlandı |
| TA-013 | Uyarlanabilir ders motoru | Planlandı |
| TA-014 | Ses ve akıllı tahta | Planlandı |
| TA-015 | Etkileşimli canlı öğretmen | Planlandı |
| TA-016 | Çapraz platform mobil (Capacitor) | Planlandı |
| TA-017 | Üretime hazırlık ve ölçekleme | Planlandı |

GPT-4.1-mini yaşam döngüsü ve model geçişi bu numaralandırmadan bağımsız, zamana bağlı bir yayın gerekliliğidir. Model varsayılanları değiştirilmedi.

## Doğruluk boyutları

Beş boyut (doğru soru, doğru cevap, uygun yöntem, tutarlı sunum, gerçek öğrenme) ayrı değerlendirilir. TA-003 birinci boyutu uygular ve seçenek tutarlılığıyla ikinciyi güçlendirir. TA-004 ikinci boyutu istenen hedefe bağlar ve dördüncü boyut için adım/blok kontrolleri ekler. Diğer boyutlar tamamlanmış sayılmaz.

## Akıl yürütme ve doğrulama (TA-004)

Ayrıntılar [ADR TA-004](architecture/adr-ta-004-reasoning-verification.md) ve [TA-004 raporu](phase-reports/TA-004.md) içindedir.

- Denklemin çözümü her zaman istenen cevap değildir. Hedef sağlayıcıdan bağımsız belirlenir ve MathAI işçisinde hesaplanır. Seçenek yalnızca hedefin bağımsız değeriyle eşlenir. Hedef belirlenemezse seçenek değiştirilmez.
- v2 2.2.0 her istekte v1’den üretilir ve saklanmaz. Kontrolü olmayan adım `not_checked` görünür. Bloğa bağlanamayan kontrol ders düzeyinde `unmapped` kalır. Sağlayıcı çıktısı hiçbir kontrolün sonucunu belirleyemez.
- FKB denetimleri yereldir ve çevrimdışıdır. Bunlar kaynağın kendi içindeki tutarlılığını ve verilen modelle hesabı sınar; yasa seçimini, tepkimenin gerçekleşmesini veya biyolojik işlevi kanıtlamaz.
- Olağan soruda ek sağlayıcı çağrısı yoktur. Hedef ipucu mevcut ders çağrısının bağlamındadır.
- Çevrimdışı kabul: `python -m scripts.science_matrix --check` (71 vaka) ve `python -m scripts.question_pack --check` (proje sahibinin 24 özgün sorusu; cevaplar çözümden türetildi, resmî anahtar ve görseller henüz eklenmedi). Bunlar model başarısı ölçmez.

## Soru bütünlüğü (TA-003)

Ayrıntılar [ADR TA-003](architecture/adr-ta-003-question-integrity.md) ve [TA-003 raporu](phase-reports/TA-003.md) içindedir.

- Olağan temiz soru: 1 Vision + 1 ders çağrısı, öğrenciye soru sorulmaz. Ek Vision çağrısı yalnızca görsel olarak çözülebilir, sonuca bağlı bir belirsizlikte ve aynı istek içinde yapılır (`TEACHERAI_VISION_MAX_RECHECKS`, varsayılan 1, 0 kapatır). Ders üretimi en çok 3 sağlayıcı çağrısı yapar (`TEACHERAI_LESSON_MAX_PROVIDER_CALLS`).
- Analiz yanıtı `revision` ve `integrity` taşır. Çözülemeyen soruda `/lessons/generate` sağlayıcı çağrılmadan 409 `question_clarification_required` döner. Eski revizyon 409 `stale_question_revision` alır.
- Revizyon aynı `lesson_analyses` belgesinde tek işlemde, hesap silme işaretiyle birlikte yazılır. TTL uzatılmaz. Görsel kalıcı olarak saklanmaz.
- `verification.source_consistency: partially_checked` yalnızca yapısal kaynak tutarlılığını ifade eder. Görselin doğru okunduğunu kanıtlamaz.
- Gerçek tanıma doğruluğu, açıklama oranı ve maliyet ölçülmedi. Sentetik matris (`python -m scripts.integrity_matrix --check`) yalnızca fikstür kabul ölçütüdür.

## Mimari ve sözleşme

Sağlayıcı → yapılandırılmış LessonPlan → doğrulama → renderer → öğrenci. Sağlayıcı değiştirilebilir. Tahta elemanlarını oluşturmak BoardPlanner’ın sorumluluğudur. Güvenlik, bilimsel doğruluk, maliyet ölçümü ve testler her modülde geliştirme koşuludur. Fiziksel dizinler çalışan modüller ihtiyaç duydukça gelişir.

Çalışan sözleşme Python modellerinde ve FastAPI OpenAPI çıktısındadır. LessonPlan v1, kaynak analizi, kavram, öğrenme hedefleri ve içeriği taşır. GeneratedLesson zarfı doğrulama sonucu, tahta ve süreleri taşır. v1 kayıt Firestore’daki yetkili kayıttır ve değişmedi. Mimari taslaktaki ses, video, öğretmen değerlendirmesi ve veri kümesi alanları geleceğe aittir. Kök src/ altındaki TypeScript örneği ayrı bir mimari prototiptir. Uyumsuz bir sözleşme ayrı bir sürüm ve geçiş planı gerektirir.

## Ortak eğitim çekirdeği (TA-002)

Ayrıntılı kararlar [ADR TA-002](architecture/adr-ta-002-education-core.md), sonuçlar [TA-002 raporu](phase-reports/TA-002.md) içindedir.

- LessonPlan v2 (`teacherai.lesson_plan` / `2.0.0`) sağlayıcı taslağı (`EducationalDraft`), sunucu kimliği ve kökeni, doğrulama raporu ve sunumu (`LessonView`) ayrı tiplerde tutar. Cevap LaTeX’e bağlı değildir (matematik, sayı, birimli nicelik, seçenek, metin, tablo). Konu dersi cevapsız geçerlidir.
- v2 saklanmaz. Her istekte v1 kayıttan belirlenimci olarak üretilir. Eski doğrulanmamış kayıtlar v2 görünümüne yükseltilmez.
- Doğrulama raporunda `scientific: passed` bu sürümde hiçbir derste oluşamaz. MathAI yalnızca `calculation` boyutunu kanıtlar. `curriculum`, `method`, `pedagogy` her zaman `not_checked`’tir. Referanslar `unreviewed`’dır ve resmî müfredat onayı ifade etmez.
- Sözleşme kaynağı Pydantic’tir: `python -m scripts.education_contracts` (`--check` CI’da). v1 web tipleri hâlâ elle yazılıdır.

## Kalıcı veri ve dağıtım

Hedef yapı (TA-005) tek Firebase projesidir: teacherai-07. Cloud Run, Firestore, Secret Manager, Artifact Registry, Auth ve Hosting aynı projede olur. Paylaşım kısayolu `/s/**` aynı projedeki Cloud Run servisine Hosting rewrite ile gider. API ise 60 sn Hosting sınırı nedeniyle doğrudan Cloud Run adresinden çağrılır. Production'da `TEACHERAI_FIREBASE_PROJECT_ID` ve `TEACHERAI_FIREBASE_AUTH_PROJECT_ID` zorunlu ve eşittir. Canlı taşıma henüz yapılmadı. Bugünkü canlı durum [TA-005 denetiminde](migration/TA-005-audit.md), adımlar [runbook'ta](migration/TA-005-runbook.md) yer alır.

Kabul sonuçları, istemci geçişi, yapılandırma ve açık konular [TA-001](phase-reports/TA-001.md) ve [TA-001B](phase-reports/TA-001B.md) faz raporlarında yer alır.

## AI maliyet ve sonuç sözleşmesi (TA-001B)

- Her sağlayıcı çağrısı `core/gateway.py` üzerinden geçer. Çıktı sınırı işlem başına ayarlanır (`TEACHERAI_MAX_OUTPUT_TOKENS_BY_OPERATION`, varsayılan 4096 / 4096 / 16384). Reasoning düzeyi yalnızca destekleyen modelde gönderilir (`TEACHERAI_REASONING_EFFORT_BY_OPERATION`).
- Sonuç sınıfları ve hata kodları: `completed`, `incomplete_max_tokens` (502 `ai_output_truncated`), `incomplete_other` (422 `ai_output_filtered` veya 502 `ai_output_incomplete`), `refusal` (422 `ai_refused`), `invalid_output` (502 `ai_invalid_output`), `timeout` (504 `ai_timeout`), `provider_error` (mevcut kodlar). Başarısız sonuçta hiçbir kayıt kalıcı hale gelmez. `ai_usage` günlüğü `outcome` alanını taşır.
- Kullanıcı başına günlük sınırların yanında küresel günlük bütçe uygulanır (`TEACHERAI_GLOBAL_DAILY_PAID_OPERATIONS`, `…_PROVIDER_CALLS`, `…_OUTPUT_TOKENS`). Bütçe tek `ai_global_usage/{gün}` belgesinde, kullanıcı sayacıyla aynı işlemde ayrılır. `0` ilgili yolu kapatır. Aşımda 503 `ai_global_budget_exhausted` döner. Bu sınırlar kesin bir USD tavanı değildir.
- Aynı `Idempotency-Key` ile tekrar gelen istek 409 `duplicate_request` alır ve ücretli işlem ikinci kez çalışmaz. İstemci, sonucu bilinmeyen denemeyi aynı anahtarla tekrarlar. Bu “en fazla bir kez çalıştırma” güvencesidir, önceki yanıt saklanmaz.

## Hesap silme ve veri yaşam döngüsü (TA-001B)

- `POST /api/v1/account/deletion` (`{"confirm": true}`, son 300 sn içinde giriş gerekir), `GET /api/v1/account/deletion` ve oturumsuz `POST /api/v1/account/deletion/receipt` (silme makbuzuyla sonuç sorgusu). Silme sürerken veya tamamlandıktan sonra kullanıcıya bağlı tüm yazmalar 409 `account_deletion_in_progress` alır.
- TTL (`expires_at`, altı koleksiyon): analiz 24 saat, pratik sorusu 7 gün (yanıt süresi 1 saat), günlük ve küresel sayaçlar 30 gün, tamamlanmış silme kaydı 30 gün. Dersler, profiller, hafızalar, olaylar, pratik yanıtları, paylaşımlar ve geri bildirimler otomatik silinmez. Süresi geçen analiz ve pratik kaydı backend’de hemen reddedilir. TTL tanımı `firestore.indexes.json` içindedir ve `core/retention.py` ile bir testle senkron tutulur.
- Eski paylaşımlar için `scripts/legacy_shares.py` vardır: varsayılan mod salt okunur `audit`, `unpublish` ise yalnızca açık bayraklarla çalışır.
- Gizlilik metninin hukuki onaysız taslağı `docs/privacy/gizlilik-metni-taslak.md` dosyasındadır.

## Model değerlendirme (TA-001B)

`python -m scripts.evaluate_models` veri setlerini doğrular ve çağrı yapmaz. `run --provider fake` hattı ücretsiz sınar. Ücretli koşu ve karar kuralı [evals/README.md](../evals/README.md) içindedir. 100 soruluk özgün öğretmen seti henüz yoktur. Sentetik smoke sonuçları model kalitesi sayılmaz.
