# TeacherAI Architecture Index

TeacherAI architecture is documented as a complete system blueprint instead of application code.

- [`architecture/system-architecture.md`](architecture/system-architecture.md) explains the scalable backend, frontend, module, abstraction, dependency, and portal architecture.
- [`architecture/folder-structure.md`](architecture/folder-structure.md) defines the future repository layout and why each top-level area exists.
- [`architecture/data-flow.md`](architecture/data-flow.md) explains student learning, interaction, teacher review, dataset, training, analytics, and recovery flows.
- [`architecture/api-and-database.md`](architecture/api-and-database.md) defines API boundaries, database ownership, storage choices, and event contracts.
- [`architecture/backend-fastapi-design.md`](architecture/backend-fastapi-design.md) defines the Python FastAPI backend architecture, feature-module contract, dependency injection approach, and test strategy.
- [`architecture/frontend-nextjs-design.md`](architecture/frontend-nextjs-design.md) defines the Next.js TypeScript App Router architecture for Student, Teacher, Admin, lesson, whiteboard, media, chat, and analytics experiences.
- [`architecture/ai-engine-architecture.md`](architecture/ai-engine-architecture.md) defines the independent AI engines, their responsibilities, data flows, events, scaling, and governance rules.
- [`architecture/whiteboard-rendering-engine.md`](architecture/whiteboard-rendering-engine.md) defines the extensible rendering engine that converts LessonPlan JSON into SVG, PNG, JPEG/JPG, PDF, animated whiteboard, and future video artifacts.
- [`architecture/dataset-format.md`](architecture/dataset-format.md) defines the AI-training-ready dataset format for teacher explanations, lesson plans, question images, OCR, solutions, corrections, student mistakes, metadata, difficulty, learning objectives, and fine-tuning exports.
