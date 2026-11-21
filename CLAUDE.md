# TeacherAI

Ortak proje ilkeleri ve çalışan sözleşme için [proje bağlamını](docs/PROJECT_CONTEXT.md), son doğrulama için [TA-005 raporunu](docs/phase-reports/TA-005.md), önceki [TA-004](docs/phase-reports/TA-004.md), [TA-003](docs/phase-reports/TA-003.md), [TA-002](docs/phase-reports/TA-002.md), [TA-001B](docs/phase-reports/TA-001B.md) ve [TA-001](docs/phase-reports/TA-001.md) raporlarını kullanın. Kararlar [ADR TA-002](docs/architecture/adr-ta-002-education-core.md), [ADR TA-003](docs/architecture/adr-ta-003-question-integrity.md), [ADR TA-004](docs/architecture/adr-ta-004-reasoning-verification.md) ve [ADR TA-005](docs/architecture/adr-ta-005-single-project.md) içindedir. Canlı proje geçişi [runbook](docs/migration/TA-005-runbook.md) ile ve yalnız onayla yapılır. Web değişikliklerinde apps/web/AGENTS.md talimatları da geçerlidir.

Doğruluk ilkesi (TA-003): TeacherAI şu beş boyutu ayrı ayrı değerlendirir ve birini diğerinin kanıtı saymaz:

1. Doğru soruyu mu anladık? (kaynak bütünlüğü, TA-003)
2. Cevap matematiksel veya bilimsel olarak doğru mu ve sorunun *istediği* hedefe mi ait? (TA-004: sınırlı MathAI ve çevrimdışı FKB denetimleri; tam alan motorları TA-008–TA-011)
3. Öğretim yöntemi bu öğrenciye uygun mu? (TA-006, TA-007)
4. Açıklama, tahta ve cevap birbiriyle uyumlu mu? (kısmi: TA-004 adım/blok kontrolleri; ses ve tahta TA-014)
5. Öğrenci gerçekten öğreniyor mu? (TA-012, TA-013)

Matematik doğrulaması görselin doğru okunduğunu kanıtlamaz. Denklemin çözümü her zaman istenen cevap değildir; seçenek yalnızca istenen hedefin bağımsız değeriyle eşlenir. Doğru birim formülün doğru yasa olduğunu, dengeli denklem tepkimenin gerçekleştiğini kanıtlamaz. Olağan soru öğrenciye onay sordurmadan çözülür. Önemsiz belirsizlik çözümü durdurmaz. Önce belirlenimci Python, gerekirse tek hedefli yeniden okuma, en son öğrenci açıklaması kullanılır. Kritik kaynak bilgisi tahminle doldurulmaz.

Değişmez kurallar:

- **Ücretli çağrı yasağı:** Testler ve geliştirme sırasında OpenAI veya başka bir sağlayıcıya gerçek istek atılmaz. Testler sahte istemci (`apps/api/tests/fake_openai.py`) ve yerel Firestore emülatörü kullanır. Ücretli model değerlendirmesi yalnızca proje sahibinin onayıyla, `python -m scripts.evaluate_models run --allow-paid --max-usd … --max-calls …` ile yapılır.
- Üretime deploy, Firebase/GCP ayarı, billing ve canlı veri işlemi yapılmaz. Toplu veri betikleri yalnızca emülatörde denenir.
- Test, lint kuralı veya uyarı bastırılmaz.
- Kullanıcıya bağlı her yeni kalıcı yazma, aynı Firestore işleminde hesap silme işaretini denetler (`apps/api/app/features/account/guard.py`) ve bir sahip alanı taşır.
- Sağlayıcı çağrıları yalnızca `apps/api/app/core/gateway.py` üzerinden yapılır. İşlem adları `core/operations.py` içindeki `Operation` enum’undan gelir.
- Eğitim sözleşmesinin kaynağı `apps/api/app/features/education/` altındaki Pydantic modelleridir. Model değişince `python -m scripts.education_contracts` çalıştırılır. Üretilen `education.generated.ts` ve `docs/contracts/education-v2.schema.json` elle düzenlenmez. CI `--check` ile eskimiş dosyayı reddeder.
- Ek sağlayıcı çağrıları mantıksal istek tavanına tabidir (`Settings.provider_call_budget`). Yeni yeniden deneme döngüsü bu tavanı aşamaz; zorunlu ek çağrı eklenmez.
- Matematik ifadeleri yalnızca `features/integrity/expression.py` ayrıştırıcısıyla işlenir; `eval`, `exec`, `ast.parse`, `sympify` kullanılmaz.
- Bilimsel denetimler (`features/reasoning/`) saf Python’dur ve sağlayıcı çağırmaz. Denetleyicisi olmayan bilimsel iddia `unsupported`/`not_checked` kalır; öncül birleşimi uydurulmaz. Blok kontrolleri yalnızca sunucu doğrulayıcılarından gelir. `python -m scripts.science_matrix --check` ve `python -m scripts.question_pack --check` CI’da çalışır.
- Doğrulayıcısı olmayan bir alan veya iddia başarılı doğrulanmış gösterilmez. Sağlayıcı çıktısı doğrulama, müfredat veya öğretmen onayı belirleyemez. Üretimi olmayan alan matematik hattına yönlendirilmez.
