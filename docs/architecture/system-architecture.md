# TeacherAI System Architecture

## 1. Architecture Goal

TeacherAI must scale to millions of students, thousands of teachers, many schools, multiple AI vendors, multiple rendering targets, and future TeacherAI-owned models. The platform is designed as a modular education system, not a single math-answering service.

Every architectural decision is optimized for the next five years:

- Replace AI providers without changing lesson, portal, or renderer code.
- Replace databases without changing business policies.
- Replace renderers without changing lesson planning.
- Add teacher, student, admin, analytics, dataset, and training capabilities independently.
- Preserve teacher reviewability and auditability for every AI-generated explanation.
- Support asynchronous workloads for vision, planning, rendering, voice, verification, analytics, and training.

## 2. Architectural Style

TeacherAI uses Clean Architecture with modular service boundaries.

```text
Presentation Layer
  -> Application Layer
    -> Domain Layer
      <- Infrastructure Adapters
```

Dependency direction is always inward. Domain policies never depend on frameworks, databases, queues, AI SDKs, cloud providers, or UI frameworks.

## 3. System Context

```text
Student Portal      Teacher Portal      Admin Portal
      |                   |                  |
      +-------------------+------------------+
                          |
                    API Gateway / BFF
                          |
                  Application Services
                          |
      +-------------------+-------------------+------------------+
      |                   |                   |                  |
 AI Orchestration   Lesson Services   Portal Services   Analytics
      |                   |                   |                  |
 Vision Providers   Renderers          Databases         Event Bus
 LLM Providers      Voice Providers    Object Storage    Warehouses
 Math Verifiers     Whiteboard Output  Search Indexes    Training Jobs
```

## 4. Backend Architecture

### 4.1 Backend Layers

| Layer | Responsibility | Must Not Contain |
| --- | --- | --- |
| API / Transport | Authentication, request validation, response mapping, rate limits. | Teaching logic, prompts, provider SDK calls. |
| Application | Use cases, workflow orchestration, authorization decisions, transaction boundaries. | Vendor SDK details, SQL-specific business behavior. |
| Domain | Lesson, pedagogy, review, dataset, student-learning, and school rules. | Framework imports, database clients, HTTP clients. |
| Infrastructure | Database repositories, AI adapters, renderers, queues, object storage, observability. | Domain policy ownership. |

### 4.2 Backend Services

| Service | Responsibility | Scaling Model |
| --- | --- | --- |
| Identity & Tenant Service | Users, roles, organizations, classrooms, permissions. | Stateless API plus relational database. |
| Question Intake Service | Upload handling, object metadata, submission lifecycle. | API workers plus object storage. |
| Vision Orchestration Service | OCR, diagram extraction, handwritten math extraction. | Queue-based GPU/AI worker pool. |
| Question Analysis Service | Topic, subtopic, difficulty, objective classification. | Stateless AI orchestration workers. |
| Lesson Planning Service | Pedagogical plan generation. | Queue workers with provider routing. |
| Math Verification Service | Symbolic checks, numeric validation, step correctness. | CPU workers, optional CAS adapters. |
| Rendering Service | Converts lesson plans to whiteboard/video/PDF scenes. | Horizontally scalable rendering workers. |
| Voice Service | Converts narration into speech assets. | Queue workers with provider routing. |
| Learning Session Service | Student interactions, hints, attempts, progress state. | Stateful domain persisted in database; stateless APIs. |
| Teacher Review Service | Review queues, edits, approvals, rubrics, feedback. | Relational workflow plus event stream. |
| Dataset Service | Curates approved examples, labels, styles, model-eval data. | Append-only datasets plus object storage. |
| Training Service | Fine-tuning jobs, evaluations, model registry. | Batch jobs and experiment tracking. |
| Analytics Service | Events, dashboards, weakness tracking, quality metrics. | Event streaming into warehouse. |
| Notification Service | Email, in-app, school alerts. | Queue-based delivery. |

## 5. Frontend Architecture

TeacherAI has three primary portals and shared frontend packages.

### 5.1 Student Portal

Responsibilities:

- Upload or capture math questions.
- View whiteboard lessons with synchronized voice.
- Ask follow-up questions.
- Practice similar questions.
- Track weaknesses, mastery, streaks, and learning paths.
- Resume learning sessions across devices.

Design decisions:

- The student portal consumes lesson/session APIs; it does not run lesson planning logic.
- Whiteboard playback uses renderer output, not raw AI text.
- Interaction events are emitted to analytics for personalization and teacher visibility.

### 5.2 Teacher Portal

Responsibilities:

- Review AI-generated lessons.
- Edit explanations, steps, examples, and misconceptions.
- Upload canonical solutions.
- Approve or reject AI outputs.
- Create teaching styles and rubrics.
- Build datasets from approved lessons.
- Monitor class and student weaknesses.

Design decisions:

- Teacher edits create versioned lesson artifacts instead of mutating history.
- Teacher-approved content is the highest-trust source for datasets and evaluations.
- Review queues are separated from student runtime so review workloads cannot block learning sessions.

### 5.3 Admin Portal

Responsibilities:

- Manage schools, tenants, billing, roles, policies, feature flags, and abuse reviews.
- Configure AI provider routing and cost limits.
- View platform health, model quality, and usage dashboards.
- Manage compliance, retention, export, and deletion workflows.

Design decisions:

- Administrative policies are centralized and audited.
- Provider and model settings are configuration data, never hardcoded in application flows.

### 5.4 Shared Frontend Packages

Shared packages should include:

- Design system components.
- Whiteboard player SDK.
- Auth/session client.
- API client generated from API contracts.
- Telemetry client.
- Accessibility and internationalization utilities.

## 6. Module Responsibilities

| Module | Responsibility | Output |
| --- | --- | --- |
| Vision | Extract text, equations, diagrams, labels, and layout from uploaded content. | `QuestionUnderstandingInput`. |
| Question Understanding | Normalize the problem and identify missing/ambiguous information. | Canonical question representation. |
| Classification | Determine topic, subtopic, difficulty, standards, and learning objectives. | `QuestionAnalysis`. |
| Pedagogy Engine | Select teaching strategy, scaffolding, misconceptions, hints, and checks. | Pedagogy plan. |
| Lesson Planner | Produce structured lesson plans. | `LessonPlan`. |
| Math Verifier | Validate each mathematical step and final answer. | Verification report. |
| Renderer | Convert lesson plans into whiteboard/video/PDF/app-specific scenes. | Render artifact. |
| Voice Engine | Generate synchronized narration audio and timing metadata. | Voice artifact. |
| Interaction Engine | Manage student turns, hints, attempts, and follow-up questions. | Session updates. |
| Teacher Review | Manage human review, edits, approvals, and feedback. | Reviewed lesson versions. |
| Dataset Manager | Transform approved content into training/evaluation examples. | Versioned datasets. |
| Training Manager | Run fine-tuning, evaluation, model promotion, rollback. | Model registry entries. |
| Analytics | Capture learning, quality, cost, latency, and safety events. | Metrics and dashboards. |

## 7. Abstraction Strategy

### 7.1 LLM Provider Abstraction

All LLM providers implement one contract:

```text
LLMProvider.generateStructured(request) -> validated structured response
```

The request contains task name, prompt version, model policy, tenant policy, input payload, output schema, tracing IDs, and safety constraints. The application layer depends only on this provider contract. Vendor adapters handle SDK calls, retries, token accounting, model-specific formats, and rate-limit behavior.

Decision: structured generation is mandatory because lesson plans, analyses, rubrics, and feedback must be testable, reviewable, and reusable as datasets.

### 7.2 Vision Abstraction

Vision providers implement:

```text
VisionProvider.extract(request) -> extracted math content, diagrams, confidence, layout
```

Providers may include multimodal LLMs, OCR engines, handwritten math recognizers, or TeacherAI-trained vision models.

Decision: vision is isolated because OCR/diagram extraction evolves independently from pedagogy and lesson planning.

### 7.3 Renderer Abstraction

Renderers implement:

```text
Renderer.render(lessonPlan, target) -> render artifact
```

Targets include interactive whiteboard, video, PDF, image sequence, mobile-native scenes, and accessibility-first text mode.

Decision: AI cannot directly draw because rendering must be deterministic, accessible, testable, localizable, and portable across devices.

### 7.4 Voice Abstraction

Voice providers implement:

```text
VoiceProvider.synthesize(narration, voicePolicy) -> audio asset and timing metadata
```

Decision: voice is separate from lesson planning so narration can be reviewed, localized, re-voiced, sped up, muted, captioned, and regenerated without changing the lesson plan.

## 8. Dependency Rules

1. Domain modules cannot import infrastructure, transport, framework, SDK, or database code.
2. Application modules depend on domain modules and ports only.
3. Infrastructure modules implement ports defined by application or domain boundaries.
4. API routes/controllers call use cases only; they never contain business logic.
5. Prompts are versioned configuration assets, not inline route strings.
6. Provider selection is policy-based and configurable, not hardcoded.
7. Renderers consume lesson plans; AI providers never output renderer-specific drawing commands.
8. Teacher edits create new versions and audit records.
9. Dataset generation only uses content that passes configured approval and quality gates.
10. Analytics events are emitted asynchronously and must not block student learning flows.

## 9. Scalability Decisions

- Use stateless APIs behind load balancers for student, teacher, and admin traffic.
- Use queues for expensive AI, rendering, voice, verification, analytics, and training tasks.
- Store original uploads and generated media in object storage, not relational rows.
- Partition large event and interaction tables by tenant and time.
- Use read models/search indexes for dashboards and portals.
- Use idempotency keys for uploads, generation jobs, teacher approvals, and payment/admin actions.
- Use provider routing for cost, latency, reliability, quality, and regional constraints.
- Use event-driven dataset creation so teacher approvals can asynchronously improve models.
- Keep lesson artifacts immutable and versioned for auditability and reproducibility.
