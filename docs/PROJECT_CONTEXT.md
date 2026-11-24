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
| Uygulandı (TA-005) | 8. sınıf matematik için kaynaklı kazanım kaydı (MEB 2018) ve taslak yöntem politikası; yalnız onaylı politika yöntem denetimi uygular, sınıf bilgisi beyan veya profilden gelir. Değişkensiz ifadelerde ve eşitsizlik uç değerinde şıkları gizleyerek çözme. Bakım modu, eski bağlantı yönlendirmesi, tek proje ayarları ve Firestore kopya betiği. Ayrıntı: [TA-005 raporu](phase-reports/TA-005.md). |
| Uygulandı (TA-005B) | Sağlayıcıdan bağımsız AI portu; davranışı bayt bayt koruyan OpenAI adaptörü; yalnız ders işlemini destekleyen Anthropic adaptörü (varsayılan sağlayıcı her işlemde `openai`). Tek fiyat/yetenek kataloğu. Yöntem denetiminde güçlü (AST) ve zayıf (metin) kanıt ayrımı. Profilde sınıf seçimi ve derste sınıfın anlık kaydı. MathAI eşzamanlılık sınırı ve `mathai_busy`/`mathai_timeout`/`mathai_error`. Kopya betiğinde iki yönlü uzlaştırma ve silinmiş verinin hortlamasını önleme. Bootstrap/Update modlu, digest ile dağıtım planı. Ayrıntı: [TA-005B raporu](phase-reports/TA-005B.md). |
| Uygulandı (TA-005C) | Üç işlem de Anthropic'te desteklenir. Anthropic'e onaylı şema izdüşümü gönderilir (4 sınır), doğrulama özgün Pydantic ile yapılır. Anthropic Vision ayrıca öğrenci görseli izni ister ve production'da kapalıdır. Varsayılan her işlemde `openai`'dir ve fallback yoktur. Sağlayıcı hataları kanonik nedenlere ayrılır; bağlam aşımında tek, sayılan yeniden deneme yapılır. Geçitte muhasebe kapsamı zorunludur (production/offline ayrımı). Katalogda yetenek ve yaşam döngüsü alanları vardır. Dağıtım Update'te çalışan ortamı uzlaştırır ve Firebase web yapılandırmasını gerçek uygulamayla karşılaştırır. Geçişte koşullu yazma/silme, onaylı ezme, yetim alt koleksiyon ve sahip farkı ele alınır. MathAI `mathai_startup_timeout` ekler. Değerlendirme hazırlık raporu vardır. Ayrıntı: [TA-005C raporu](phase-reports/TA-005C.md), [ADR TA-005C](architecture/adr-ta-005c-provider-completion.md). |
| Uygulandı (TA-006) | Müfredat Kaydı v2: 12 resmî program (MEB 2018 ve Maarif Modeli 2026; matematik 5-12, fen 5-8, fizik/kimya/biyoloji 9-12), 1591 kayıt (resmî kod, başlık, PDF sayfası; resmî metin kopyalanmaz), doğrulanmış 2025-2026/2026-2027 uygulama takvimi, ayrı sınav kapsamı, belirlenimci program çözümlemesi (mezun, belirsiz sınıf, yaz geçişi açıkça temsil edilir). Bilimsel kaynak kaydı (30 kaynak, dört ayrı izin) ve bilgi kaydı (74 taslak girdi; çalışma zamanına uygun 0). Matematik ders üretiminde sınırlı müfredat bağlamı ve dersle saklanan köken kaydı (ek çağrı yok). `/konular` gözatma, mobil öncelikli tasarım belirteçleri, alt gezinme/kenar çubuğu, büyütülebilir tahta. Ayrıntı: [TA-006 raporu](phase-reports/TA-006.md), [ADR TA-006](architecture/adr-ta-006-curriculum-knowledge.md). |
| Uygulandı (TA-007) | Uzman öğretmen zekâsının çalışan altyapısı: proje sahibinin yönettiği inceleyen yetki kaydı (üretimde boş), içerik özetiyle bayat onay koruması, girdi düzeyinde kaynak kullanım sınıfı ve hak kararı, ortak konu taksonomisi (67 konu, 4 branş + ortaokul fen), vektörsüz denetimli geri getirme (kırpma yok, dışarıda bırakma var), ders akışında MethodPolicy v2 (yetkili onay, program/konu belirsizliği, açık ileri yöntem isteği, adım kanıt sınıfları), seçilen ve gerçekten gönderilen bağlamı ayıran köken kaydı, okul izleği (fen lisesi) ve Türkçe ekli çoklu sınav hedefi, 4 fen lisesi programı (16 program, 2197 kayıt), 202 taslak bilgi girdisi (74'ü bağımsız denetlendi, 13'ü sürüm 2), güvenli değerlendirme paketi içe aktarma (24 görsel + 5 varyant, yerel), Word formu ve inceleme CSV içe aktarma, katkı yönetişimi. Onaylı içerik sayısı 0'dır. Ayrıntı: [TA-007 raporu](phase-reports/TA-007.md), [ADR TA-007](architecture/adr-ta-007-expert-teacher-intelligence.md). |
| Taslak (TA-006 → TA-007) | Bilgi girdileri, yöntem politikaları ve Maarif matematik betimlemeleri `claude-draft`; öğretmen incelemesi olmadan yetkili bağlam olmaz. Öğretmen katkı biçimi ve şablonları [docs/teachers](teachers/README.md). |
| Planlandı | Gerçek öğretmen incelemesiyle onaylı bilgi ve yöntem politikası (altyapı TA-007'de hazır). Konu anlatımı ve uyarlanabilir ders (TA-013), ses ve canlı tahta (TA-014/015), Capacitor yerel kabuğu (TA-016). FKB öğrenci üretimi kapalı kalır (TA-009–TA-011). |
| Ertelendi | Aşağıdaki yol haritasındaki TA-005 ve sonrası. 100 soruluk öğretmen incelemeli değerlendirme seti dış katkı olarak ertelendi. |
| Dış doğrulama bekliyor | Gerçek sağlayıcı kalite karşılaştırması, dağıtılmış sürüm, gerçek Firebase kimliği ve App Check geçişi. |

## Yol haritası

TA-002 sonrası numaralandırma (TA-003 ile güncellendi):

| Faz | Kapsam | Durum |
| --- | --- | --- |
| TA-001 / TA-001B | Temel ve son stabilizasyon | Tamamlandı |
| TA-002 | Ortak eğitim çekirdeği, LessonPlan v2 | Tamamlandı |
| TA-003 | Soru bütünlüğü ve görsel zekâ | Tamamlandı |
| TA-004 | Akıl yürütme ve doğrulama çekirdeği | Tamamlandı |
| TA-005 | Tek proje geçişine hazırlık, kimya düzeltmeleri, gizli şık stratejisi, 8. sınıf yöntem kaydı, değerlendirme altyapısı | Tamamlandı (canlı taşıma ve gerçek model koşusu onay bekliyor) |
| TA-005B | Geçiş araçlarının güvenliği, ilk dağıtım planı, yöntem denetimi, sınıf bilgisi, MathAI dayanıklılığı, sağlayıcıdan bağımsız AI geçidi | Tamamlandı (canlı denetim çıktısı ve gerçek model koşusu bekliyor) |
| TA-005C | Çoklu sağlayıcı tamamlama, muhasebe kapsamı, dağıtım ve geçiş güvenliği, değerlendirme hazırlığı, bilimsel bilgi mimarisi devri | Tamamlandı (PR #24; canlı geçiş, dağıtım ve gerçek model koşusu onay bekliyor) |
| TA-006 | Müfredat ve yöntem zekâsı, bilimsel kaynak/bilgi kaydı, mobil öncelikli arayüz temeli | Tamamlandı (PR #25) |
| TA-007 | Uzman öğretmen zekâsı, bilimsel bilgiye dayandırma, müfredat tamamlama, denetimli geri getirme | Bu dal (yetkili öğretmen/uzman, onaylar, hak kararları ve cevap anahtarı bekliyor) |
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

GPT-4.1-mini yaşam döngüsü ve model geçişi bu numaralandırmadan bağımsız, zamana bağlı bir yayın gerekliliğidir. `gpt-4.1-mini-2025-04-14` için duyurulmuş kapanış 2027-01-14'tür (katalogdaki `lifecycle` alanı); uygulama başlangıçta uyarı yazar. Model varsayılanları değiştirilmedi.

## Müfredat ve bilimsel bilgi (TA-006)

Ayrıntılar [ADR TA-006](architecture/adr-ta-006-curriculum-knowledge.md), [kapsam raporu](curriculum/TA-006-coverage.md), [bilgi kapsam raporu](knowledge/TA-006-knowledge-coverage.md), [kaynak kaydı](sources/TA-006-source-registry.md) ve [eksik kaynaklar](sources/TA-006-missing-sources.md) içindedir.

- Program içeriği, uygulama takvimi ve sınav kapsamı ayrı sürümlenir. Kimlik `<program>::<resmî kod>`. Doğrulanmamış sınav kapsamı kazanımı sınava bağlamaz.
- Resmî kazanım metni (lisans ifadesi yok) öğrenciye ve isteme gönderilmez; yalnız TA-005'in 29 metni korunur.
- Sınıf, öğrenci/mezun durumu ve sınav hedefi yalnız beyan veya profilden gelir; görselden çıkarılmaz. Mezun öğrenci 12. sınıf öğrencisi sayılmaz.
- Ders bağlamı ≤ 4 kazanım kodu/başlığı ve yalnız onaylı bilgi girdileri, ≤ 1500 bayt; çözümleme yoksa istem değişmez. Dersle `educational_provenance` saklanır ve eski ders yeniden hesaplanmaz.
- Denetleyici bağlantısı kısmidir; bilgi girdisi düzeyinde `passed` oluşamaz.
- CI: `python -m scripts.curriculum_registry --check`, `knowledge_registry --check`, `dataset_manifest --check`, `teacher_contributions validate-all`, `teacher_contributions status`.

## Uzman öğretmen zekâsı ve denetimli geri getirme (TA-007)

Ayrıntılar [ADR TA-007](architecture/adr-ta-007-expert-teacher-intelligence.md), [geri getirme](architecture/ta-007-retrieval.md), [inceleme akışı](governance/TA-007-review-workflow.md), [hak uygulaması](sources/TA-007-rights-enforcement.md), [kapsam](curriculum/TA-007-coverage.md), [bilgi kapsamı](knowledge/TA-007-knowledge-coverage.md), [eksik kaynaklar](sources/TA-007-missing-sources.md) ve [değerlendirme hazırlığı](evals/TA-007-readiness.md) içindedir.

- Onay yalnız `knowledge/data/reviewers.json` kaydında aşama, alan, rol ve tarih için yetkili inceleyenden geçerlidir; üretim kaydı boştur, sentetik yetki yalnız testte. Onay içerik özetini taşır; içerik değişirse bayatlar.
- Ders akışı MethodPolicy v2 ve Müfredat Kaydı v2 denetimini kullanır (v1 denetim işlevleri ders akışında çağrılmaz). Konu yalnız yapısal kanıtla kesindir; belirsiz program/konu kesin hüküm üretmez.
- Geri getirme belirlenimcidir (vektör/gömme/ek çağrı yok); kayıt bütünüyle gider veya nedeniyle dışarıda kalır. Köken kaydı seçilen ve gerçekten gönderilen bağlamı ayırır.
- Okul izleği ve sınav hedefleri yalnız beyandır; fen lisesi programı yalnız açık seçimle kullanılır.
- Değerlendirme görselleri `python -m scripts.eval_import` ile denetlenerek yerel klasöre alınır; varyantlar özgün soruya bağlıdır; cevap anahtarı türetilmez.
- Öğretmen katkıları çevrimdışı yönetilir (`scripts/teacher_forms.py`, `scripts/teacher_contributions.py status`, `scripts/review_import.py`); çalışma zamanı katkı dosyası okumaz.

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

- TA-005C: geçit açık bir muhasebe kapsamı olmadan sağlayıcı çağırmaz. Production kapsamını yalnız `core/admission.py` açar. Değerlendirme ve testler `begin_offline_accounting` ile kendi çağrı/USD tavanını açar; bu kapsam production/staging'de ve Cloud Run'da açılamaz.
- Her sağlayıcı çağrısı `core/gateway.py` üzerinden geçer. TA-005B'den beri geçit sağlayıcıdan bağımsızdır: adaptörler (`core/openai_adapter.py`, `core/anthropic_adapter.py`) yalnız geçidin tek kullanımlık geçiş belgesiyle çağrılabilir; kota, bütçe, tavan, rezervasyon, şema doğrulaması ve günlük ortak katmandadır. Fiyatlar `core/model_catalog.json` dosyasındadır ([ADR TA-005B](architecture/adr-ta-005b-provider-gateway.md)). Çıktı sınırı işlem başına ayarlanır (`TEACHERAI_MAX_OUTPUT_TOKENS_BY_OPERATION`, varsayılan 4096 / 4096 / 16384). Reasoning düzeyi yalnızca destekleyen modelde gönderilir (`TEACHERAI_REASONING_EFFORT_BY_OPERATION`).
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
