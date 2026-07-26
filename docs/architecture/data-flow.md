# TeacherAI Data Flow

## 1. Student Lesson Generation Flow

```text
Student Portal
  -> API Gateway
  -> Question Intake Service
  -> Object Storage stores original upload
  -> Vision Orchestration extracts math content
  -> Question Analysis classifies topic, subtopic, difficulty, objectives
  -> Pedagogy Engine selects teaching strategy
  -> Lesson Planner creates structured LessonPlan
  -> Math Verifier validates steps
  -> Renderer creates WhiteboardDocument
  -> Voice Engine creates narration assets
  -> Learning Session Service opens session
  -> Student Portal plays synchronized lesson
  -> Analytics receives interaction events
```

Decision: the flow is asynchronous after intake because vision, LLM, verification, rendering, and voice workloads have variable latency and cost. The student portal receives progress updates and can resume sessions.

## 2. Student Interaction Flow

```text
Student asks follow-up or attempts answer
  -> Learning Session Service records turn
  -> Interaction Engine determines intent
  -> Pedagogy Engine decides hint/explanation strategy
  -> LLM Provider creates structured response when needed
  -> Math Verifier checks mathematical claims
  -> Renderer updates whiteboard scene if needed
  -> Voice Engine generates optional narration
  -> Student receives response
  -> Analytics records mastery and weakness signals
```

Decision: interactions are session-scoped and evented so personalization can improve without blocking the learning experience.

## 3. Teacher Review Flow

```text
Generated lesson or flagged interaction
  -> Teacher Review Queue
  -> Teacher reviews structured steps, narration, verification report, and student outcome
  -> Teacher edits or approves a new artifact version
  -> Approved version becomes trusted educational content
  -> Dataset Service evaluates eligibility
  -> Analytics updates quality metrics
```

Decision: teacher edits are versioned artifacts. The original AI output, teacher changes, reviewer identity, timestamps, and approval state remain auditable.

## 4. Dataset and Training Flow

```text
Teacher-approved lesson / solution / style / rubric
  -> Dataset Candidate Event
  -> Dataset Service applies quality, privacy, and policy filters
  -> Dataset version is created
  -> Evaluation suite is generated or updated
  -> Training Manager runs experiments
  -> Model Registry stores candidates and metrics
  -> Admin approves model promotion
  -> Provider Router gradually rolls out model
```

Decision: model improvement is gated by teacher approval, privacy policy, evaluation metrics, and controlled rollout. Training data must be reproducible by dataset version.

## 5. Analytics Flow

```text
Portal events + backend events + provider metrics
  -> Event Bus
  -> Stream processing
  -> Operational metrics store for alerts
  -> Warehouse for product and learning analytics
  -> Read models for dashboards
```

Decision: analytics is asynchronous. Learning sessions must not fail because dashboards or warehouses are unavailable.

## 6. Failure and Recovery Flow

- Every generation job has an idempotency key.
- Every external provider call has tracing, timeout, retry, fallback, and cost accounting.
- Partial artifacts are stored with explicit states: pending, processing, failed, verified, rendered, approved, archived.
- Failed jobs can be replayed from immutable inputs.
- Provider failures trigger policy-based fallback, not application code changes.
