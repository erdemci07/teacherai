# TeacherAI Architecture

TeacherAI is designed as a production AI education platform for millions of students and thousands of teachers. The architecture optimizes for long-term replaceability, observability, safety, and teacher-led improvement.

## Principles

- Clean Architecture: domain models and application use cases do not depend on frameworks, databases, AI providers, or renderers.
- SOLID design: each module has one reason to change and depends on abstractions.
- Provider replaceability: OpenAI, Claude, Gemini, DeepSeek, Qwen, Llama, and future fine-tuned TeacherAI models share one AI provider contract.
- Renderer replaceability: lesson plans are rendered through renderer interfaces so whiteboard, video, PDF, and future experiences can evolve independently.
- No hardcoded prompts in routes: prompt selection and provider execution belong behind application ports.
- Teacher improvement loop: teacher reviews, datasets, styles, and feedback are first-class future modules.

## Module Boundaries

| Module | Responsibility | Depends On |
| --- | --- | --- |
| Vision | Extract math content from uploaded images or documents. | AI provider ports, storage ports |
| Question Analysis | Determine topic, subtopic, difficulty, and learning objectives. | Domain models, AI provider ports |
| Lesson Planner | Create structured pedagogical lesson plans. | Domain models, pedagogy ports, AI provider ports |
| Pedagogy Engine | Select teaching strategy, scaffolding, hints, and misconceptions. | Domain models |
| Math Verifier | Validate mathematical correctness of solution steps. | Domain models, symbolic/verifier ports |
| Whiteboard Renderer | Convert lesson plans into drawable scenes. | Lesson plan contracts |
| Voice Engine | Convert lesson narration into speech. | Voice provider ports |
| Teacher Portal | Review, edit, and approve AI explanations and datasets. | Application use cases |
| Student Portal | Learning sessions, practice, weaknesses, and paths. | Application use cases |
| Analytics | Learning effectiveness, engagement, and quality signals. | Event ports |
| Dataset Manager | Curate teacher-approved examples and training data. | Storage ports |
| Training Manager | Fine-tuning and evaluation workflows. | Dataset and model provider ports |
| LLM Provider | Vendor-specific AI implementations. | External APIs only |

## Dependency Direction

```text
interfaces / infrastructure -> application -> domain
```

The domain layer never imports infrastructure. Application use cases depend on ports. Infrastructure adapters implement those ports.

## Lesson Plan Separation

AI-generated content must be structured as a `LessonPlan`. Renderers consume that structure and produce output-specific instructions.

```text
QuestionAnalysis -> LessonPlanningUseCase -> LessonPlan -> WhiteboardRenderer -> WhiteboardDocument
```

This preserves teacher reviewability, renderer replaceability, and future training-data quality.
