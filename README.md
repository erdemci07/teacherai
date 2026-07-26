# TeacherAI

TeacherAI is a long-term AI education platform whose purpose is to teach mathematics like an experienced teacher, not merely answer math questions.

This repository currently contains the production architecture blueprint only. It intentionally avoids application code until the system design, module boundaries, contracts, data ownership, and scaling rules are clear.

## Vision

```text
Student uploads a math question
  -> AI understands the question
  -> AI determines topic, subtopic, difficulty, and learning objectives
  -> AI creates a structured lesson plan
  -> Renderer converts the lesson plan into a digital whiteboard
  -> Voice explains every step
  -> Student interacts with AI
  -> Teacher reviews explanations
  -> Teacher feedback improves TeacherAI
```

## Non-Negotiable Architecture Rule

AI must never directly draw on the whiteboard.

```text
AI Provider -> Structured Lesson Plan -> Renderer -> Whiteboard Output
```

This separation makes lessons reviewable by teachers, reusable for datasets, verifiable by math engines, renderable across many clients, and safe to improve over time.

## Architecture Documents

- [`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md) defines the complete scalable system architecture.
- [`docs/architecture/folder-structure.md`](docs/architecture/folder-structure.md) defines the future repository and module layout.
- [`docs/architecture/data-flow.md`](docs/architecture/data-flow.md) defines the end-to-end learning, review, dataset, and model-improvement flows.
- [`docs/architecture/api-and-database.md`](docs/architecture/api-and-database.md) defines API boundaries and database ownership.
- [`docs/architecture/backend-fastapi-design.md`](docs/architecture/backend-fastapi-design.md) defines the Python FastAPI backend architecture, feature modules, and dependency injection design.
