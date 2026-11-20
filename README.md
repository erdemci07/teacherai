# TeacherAI

TeacherAI, öğrencinin çözüm yöntemini öğrenmesini amaçlayan çok disiplinli bir öğretmen projesidir. Mevcut uygulama matematik sorularının görsel analizini, yapılandırılmış ders üretimini, sınırlı sembolik doğrulamayı ve etkileşimli tahtayı içerir.

## Geliştirme

Node.js 24 ve Python 3.12 kullanılır. Depo kökünden çalıştırın.

```sh
npm ci
python -m pip install -r apps/api/requirements-dev.lock
npm run dev:web
# Ayrı terminal
python -m uvicorn apps.api.app.main:app --reload
```

Ücretli işlemler için geçerli Firebase oturumu, Firestore erişimi ve sağlayıcı yapılandırması gerekir. Yerel testler sahte sağlayıcılarla çalışır. Ayarlar ve emülatör komutları [TA-001 raporunda](docs/phase-reports/TA-001.md), uygulanan ve planlanan özellikler [proje bağlamında](docs/PROJECT_CONTEXT.md) açıklanır.

## Mimari taslaklar

- [`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md) defines the complete scalable system architecture.
- [`docs/architecture/folder-structure.md`](docs/architecture/folder-structure.md) defines the future repository and module layout.
- [`docs/architecture/data-flow.md`](docs/architecture/data-flow.md) defines the end-to-end learning, review, dataset, and model-improvement flows.
- [`docs/architecture/api-and-database.md`](docs/architecture/api-and-database.md) defines API boundaries and database ownership.
- [`docs/architecture/backend-fastapi-design.md`](docs/architecture/backend-fastapi-design.md) defines the Python FastAPI backend architecture, feature modules, and dependency injection design.
- [`docs/architecture/frontend-nextjs-design.md`](docs/architecture/frontend-nextjs-design.md) defines the Next.js TypeScript App Router frontend architecture and portal design.
- [`docs/architecture/ai-engine-architecture.md`](docs/architecture/ai-engine-architecture.md) defines the independent AI engines, responsibilities, data flow, and long-term improvement architecture.
- [`docs/architecture/whiteboard-rendering-engine.md`](docs/architecture/whiteboard-rendering-engine.md) defines the extensible LessonPlan-to-visual-artifact rendering architecture.
- [`docs/architecture/dataset-format.md`](docs/architecture/dataset-format.md) defines the complete AI-training-ready dataset format and JSON examples.
- [`docs/architecture/lessonplan-json-standard.md`](docs/architecture/lessonplan-json-standard.md) defines the core LessonPlan JSON language used by AI, verification, rendering, voice, video, review, and datasets.
