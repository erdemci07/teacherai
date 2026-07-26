# API and Database Architecture

## 1. API Structure

TeacherAI APIs are organized by bounded context. Routes are transport contracts only; they call application use cases and never contain business logic.

```text
/api/v1/auth/*
/api/v1/tenants/*
/api/v1/classrooms/*
/api/v1/students/*
/api/v1/questions/*
/api/v1/lesson-plans/*
/api/v1/learning-sessions/*
/api/v1/teacher/reviews/*
/api/v1/teacher/datasets/*
/api/v1/admin/providers/*
/api/v1/admin/models/*
/api/v1/admin/policies/*
/api/v1/analytics/events
```

## 2. API Decisions

- Use REST for resource lifecycle APIs such as uploads, reviews, datasets, and admin configuration.
- Use streaming or WebSocket/SSE channels for generation progress, whiteboard playback coordination, and live tutoring sessions.
- Use asynchronous event contracts for workflow transitions such as `LessonPlanGenerated`, `LessonVerified`, `TeacherApprovedLesson`, and `DatasetVersionCreated`.
- Use generated typed clients for frontends so portals do not hand-code API shapes.
- Version all external API contracts and event schemas.
- Require tenant, actor, role, trace, and idempotency context for state-changing operations.

## 3. Database Structure

TeacherAI uses database-per-bounded-context ownership. A physical database may be shared early, but schemas and ownership stay separate so modules can later scale independently.

### 3.1 Relational Operational Store

Primary relational entities:

| Context | Tables |
| --- | --- |
| Identity | tenants, schools, users, roles, permissions, classrooms, enrollments |
| Question Intake | question_submissions, upload_assets, extraction_jobs |
| Lesson | question_analyses, lesson_plans, lesson_plan_versions, lesson_steps, verification_reports |
| Rendering | render_jobs, render_artifacts, whiteboard_documents |
| Voice | voice_jobs, voice_artifacts, captions, narration_timings |
| Learning | learning_sessions, student_turns, attempts, hints, mastery_snapshots |
| Teacher Review | review_items, review_decisions, teacher_edits, rubrics, teaching_styles |
| Dataset | dataset_candidates, dataset_versions, dataset_examples, dataset_exports |
| Training | training_jobs, evaluation_runs, model_registry, rollout_policies |
| Admin | provider_configs, feature_flags, audit_logs, retention_policies |

### 3.2 Object Storage

Object storage contains:

- Original uploads.
- Extracted images and diagrams.
- Rendered whiteboard assets.
- Audio files and captions.
- Dataset exports.
- Training artifacts and evaluation reports.

Decision: binary and large generated artifacts do not belong in relational rows.

### 3.3 Vector Store

The vector store supports:

- Similar question retrieval.
- Teaching example retrieval.
- Misconception retrieval.
- Teacher-approved explanation retrieval.
- Personalization and remediation suggestions.

Decision: vector search is an adapter. Core pedagogy must not depend on one vendor-specific vector database.

### 3.4 Warehouse and Analytics Store

The warehouse supports:

- Student weakness trends.
- Lesson quality metrics.
- Teacher review throughput.
- Provider cost and latency analysis.
- Model evaluation and drift monitoring.

Decision: analytics schemas are optimized for read-heavy reporting and are separate from operational transaction schemas.

## 4. Data Ownership Rules

1. Each bounded context owns its write model.
2. Other modules access data through APIs, events, or read models, not direct table joins.
3. Cross-context replication uses events.
4. Deletions, retention, and exports are policy-driven and auditable.
5. Dataset records retain source lineage, consent policy, approval state, and artifact versions.
6. Student personally identifiable information is separated from learning artifacts wherever possible.
7. Teacher-approved artifacts are immutable once published; changes create new versions.

## 5. Core Events

```text
QuestionSubmitted
QuestionExtracted
QuestionAnalyzed
LessonPlanGenerated
LessonPlanVerified
LessonRendered
VoiceGenerated
LearningSessionStarted
StudentInteractionRecorded
TeacherReviewRequested
TeacherEditedLesson
TeacherApprovedLesson
DatasetCandidateCreated
DatasetVersionCreated
TrainingJobCompleted
ModelPromoted
```

Decision: events create loose coupling between student runtime, teacher review, dataset generation, training, and analytics.
