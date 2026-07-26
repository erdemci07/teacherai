# TeacherAI

TeacherAI is a long-term AI education platform designed to teach mathematics like an experienced teacher, not merely solve questions.

The platform follows Clean Architecture so core learning workflows remain independent from AI providers, renderers, databases, API frameworks, and delivery channels.

## Core Flow

1. A student uploads a math question.
2. TeacherAI analyzes the question to identify topic, subtopic, difficulty, and learning objectives.
3. TeacherAI creates a structured lesson plan.
4. A renderer converts the lesson plan into whiteboard instructions.
5. A voice engine explains each step.
6. Students interact with the AI teacher.
7. Teachers review, edit, and improve explanations and datasets.

## Architectural Rule

AI providers must never directly draw on the whiteboard. AI produces structured lesson plans, and renderers convert those plans into visual experiences.

```text
AI Provider -> Lesson Planner -> Structured Lesson Plan -> Renderer -> Whiteboard
```

See [`docs/architecture.md`](docs/architecture.md) for the platform architecture and module boundaries.
