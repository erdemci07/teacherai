# TeacherAI

Ortak proje ilkeleri ve çalışan sözleşme için [proje bağlamını](docs/PROJECT_CONTEXT.md), son doğrulama için [TA-002 raporunu](docs/phase-reports/TA-002.md), önceki [TA-001B](docs/phase-reports/TA-001B.md) ve [TA-001](docs/phase-reports/TA-001.md) raporlarını kullanın. Ortak eğitim çekirdeğinin kararları [ADR TA-002](docs/architecture/adr-ta-002-education-core.md) içindedir. Web değişikliklerinde apps/web/AGENTS.md talimatları da geçerlidir.

Değişmez kurallar:

- **Ücretli çağrı yasağı:** Testler ve geliştirme sırasında OpenAI veya başka bir sağlayıcıya gerçek istek atılmaz. Testler sahte istemci (`apps/api/tests/fake_openai.py`) ve yerel Firestore emülatörü kullanır. Ücretli model değerlendirmesi yalnızca proje sahibinin onayıyla, `python -m scripts.evaluate_models run --allow-paid --max-usd … --max-calls …` ile yapılır.
- Üretime deploy, Firebase/GCP ayarı, billing ve canlı veri işlemi yapılmaz. Toplu veri betikleri yalnızca emülatörde denenir.
- Test, lint kuralı veya uyarı bastırılmaz.
- Kullanıcıya bağlı her yeni kalıcı yazma, aynı Firestore işleminde hesap silme işaretini denetler (`apps/api/app/features/account/guard.py`) ve bir sahip alanı taşır.
- Sağlayıcı çağrıları yalnızca `apps/api/app/core/gateway.py` üzerinden yapılır. İşlem adları `core/operations.py` içindeki `Operation` enum’undan gelir.
- Eğitim sözleşmesinin kaynağı `apps/api/app/features/education/` altındaki Pydantic modelleridir. Model değişince `python -m scripts.education_contracts` çalıştırılır. Üretilen `education.generated.ts` ve `docs/contracts/education-v2.schema.json` elle düzenlenmez. CI `--check` ile eskimiş dosyayı reddeder.
- Doğrulayıcısı olmayan bir alan veya iddia başarılı doğrulanmış gösterilmez. Sağlayıcı çıktısı doğrulama, müfredat veya öğretmen onayı belirleyemez. Üretimi olmayan alan matematik hattına yönlendirilmez.
