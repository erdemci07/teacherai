# TeacherAI

Ortak proje ilkeleri ve çalışan sözleşme için [proje bağlamını](docs/PROJECT_CONTEXT.md), son doğrulama için [TA-001B raporunu](docs/phase-reports/TA-001B.md) ve önceki [TA-001 raporunu](docs/phase-reports/TA-001.md) kullanın. Web değişikliklerinde apps/web/AGENTS.md talimatları da geçerlidir.

Değişmez kurallar:

- **Ücretli çağrı yasağı:** Testler ve geliştirme sırasında OpenAI veya başka bir sağlayıcıya gerçek istek atılmaz. Testler sahte istemci (`apps/api/tests/fake_openai.py`) ve yerel Firestore emülatörü kullanır. Ücretli model değerlendirmesi yalnızca proje sahibinin onayıyla, `python -m scripts.evaluate_models run --allow-paid --max-usd … --max-calls …` ile yapılır.
- Üretime deploy, Firebase/GCP ayarı, billing ve canlı veri işlemi yapılmaz. Toplu veri betikleri yalnızca emülatörde denenir.
- Test, lint kuralı veya uyarı bastırılmaz.
- Kullanıcıya bağlı her yeni kalıcı yazma, aynı Firestore işleminde hesap silme işaretini denetler (`apps/api/app/features/account/guard.py`) ve bir sahip alanı taşır.
- Sağlayıcı çağrıları yalnızca `apps/api/app/core/gateway.py` üzerinden yapılır. İşlem adları `core/operations.py` içindeki `Operation` enum’undan gelir.
