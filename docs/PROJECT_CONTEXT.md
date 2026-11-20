# TeacherAI proje bağlamı

TeacherAI genel amaçlı, çok disiplinli bir öğretmendir. Amaç, öğrencinin karşılaştığı bir sonraki soruyu bağımsız çözebilmesidir. Sınav hedefi öğrenci bağlamının isteğe bağlı bir alanıdır. Çalışan öğrenci akışları değişiklikler sırasında korunur.

| Durum | Kapsam |
| --- | --- |
| Uygulandı | Next.js/React/TypeScript öğrenci arayüzü, FastAPI/Pydantic modüler monoliti, Firebase Auth, Firestore, matematik görseli analizi, yapılandırılmış ders, BoardPlanner, KaTeX, ders sonrası etkileşim, geçmiş ve bağlantıyla paylaşım. TA-001 değişiklikleri yerel dalda doğrulanır. |
| Uygulandı (TA-002) | Ortak eğitim çekirdeği (`features/education`): kanonik alan kimlikleri, kökenli eğitim bağlamı, soru anlama sözleşmesi, LessonPlan v2, alan yetenek tablosu, boyut bazında doğrulama raporu. Matematik üretim hattı v2 projeksiyonunu her derste kurar. Sahibine özel salt okunur `GET /api/v1/lessons/{id}/v2` ve geçmişte v2 anlatım görünümü. Pydantic’ten üretilen JSON Schema ve TypeScript tipleri, CI eskime denetimi. |
| Yalnızca sözleşme ve çevrimdışı fikstür | Fizik, kimya, biyoloji ve fen dersleri v2 ile temsil edilir ve çevrimdışı testlerde gösterilir. Bu alanlarda tanıma, ders üretimi, doğrulama ve pratik **çalışmaz**. Üretim isteği 422 `subject_generation_unavailable` alır. |
| Kısmi | MathAI sınırlı tek değişkenli gerçel denklemleri ve belirli grafik özelliklerini denetler. Sözel gerekçeler otomatik olarak kanıtlanmaz. Doğrulanabilir benzer denklem üretildiğinde öğrenci pratik yanıtı gönderebilir. Öğrenme hafızası mevcut etkileşim olaylarından oluşur. |
| Planlandı | Müfredat modülü ilgili eski programları ve Türkiye Yüzyılı Maarif Modeli’ni destekleyecek. Sınıf düzeyine uygun yöntemler açık politikalarla uygulanacak. Öğretmen bilgisi yapılandırılacak ve bağımsız incelemeden geçecek. Mobil istemci için ilk tercih Capacitor. |
| Ertelendi | Bilim alanı motorları (TA-002 yalnızca sözleşmeyi kurdu), ek AI sağlayıcıları (TA-003), Öğretmen Stüdyosu, canlı ses ve cihaz entegrasyonu sonraki fazlarda ele alınacak. |
| Dış doğrulama bekliyor | Gerçek sağlayıcı kalite karşılaştırması, dağıtılmış sürüm, gerçek Firebase kimliği ve App Check geçişi. |

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

Cloud Run ve mevcut Firestore yapılandırması math-ai-07, Firebase Hosting teacherai-07 ve bölge us-east4 olarak korunur. Web uygulamasının gerçek Firebase Auth projesini web kaydından doğrulayın. Sunucu kimlik kitlesi ve Firestore proje seçimi ayrı ayarlanabilir. Paylaşım kısayolu Hosting üzerinden Cloud Run’a yönlenir. Müşteri verisi, gizli anahtarlar ve canlı servis çağrıları olağan CI testlerine girmez.

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
