# AI Engine Architecture

## 1. Purpose

TeacherAI's AI architecture is divided into independent engines. Each engine owns one capability, exposes explicit contracts, and can be scaled, replaced, tested, and improved without forcing changes in unrelated engines.

This document is architecture only. It does not implement prompts, models, business logic, provider calls, rendering code, or training pipelines.

## 2. Long-Term AI Design Principles

- AI is a collection of replaceable engines, not one monolithic LLM call.
- Every engine communicates through structured contracts, not free-form hidden text.
- TeacherAI must support many model providers and future TeacherAI-trained models.
- AI-generated artifacts must be versioned, reviewable, auditable, reproducible, and eligible for teacher feedback.
- The system must separate understanding, pedagogy, verification, rendering, voice, dataset curation, feedback, and training.
- AI must never directly draw on the whiteboard; Renderer Engine consumes structured lesson artifacts.
- Long-running and expensive AI work must run asynchronously with idempotency, traceability, retries, and fallback policies.
- Teacher-approved content is the highest-trust signal for dataset and training workflows.

## 3. Engine Overview

```text
Question Upload
  -> Vision Engine
  -> Pedagogy Engine
  -> Lesson Planner
  -> Math Verification Engine
  -> Renderer Engine
  -> Voice Engine
  -> Student Learning Session
  -> Teacher Feedback Engine
  -> Dataset Engine
  -> Training Engine
  -> Model Registry / Provider Router
```

The flow is not a rigid synchronous chain. Engines communicate through APIs, events, and immutable artifact versions so work can be retried, reviewed, replayed, or replaced independently.

## 4. Engine Responsibility Matrix

| Engine | Primary Responsibility | Primary Output | Must Not Own |
| --- | --- | --- | --- |
| Vision Engine | Understand uploaded visual/textual math content. | Structured extraction artifact. | Pedagogy strategy, final lesson plans, rendering. |
| Pedagogy Engine | Decide how to teach based on objectives, student context, and misconceptions. | Pedagogy plan. | OCR, drawing, voice synthesis, model training. |
| Lesson Planner | Create structured lesson plans from analysis and pedagogy strategy. | Versioned lesson plan. | Whiteboard drawing commands, audio files, dataset approval. |
| Math Verification Engine | Validate mathematical correctness and step consistency. | Verification report. | Pedagogical style, UI rendering, voice generation. |
| Renderer Engine | Convert structured lesson artifacts into target-specific visual artifacts. | Whiteboard/video/PDF render artifacts. | Lesson generation, mathematical reasoning, LLM provider routing. |
| Voice Engine | Generate speech, captions, transcripts, and timing metadata. | Voice artifact. | Lesson correctness, whiteboard rendering, dataset policy. |
| Teacher Feedback Engine | Capture teacher review, edits, ratings, approvals, and corrections. | Feedback and reviewed artifact versions. | Automatic model training, raw provider calls. |
| Dataset Engine | Curate approved artifacts into versioned datasets. | Dataset versions and exports. | Teacher approval decisions, online tutoring. |
| Training Engine | Fine-tune, evaluate, register, and roll out models. | Model candidates, evaluation reports, registry entries. | Runtime lesson orchestration, teacher review UI. |

## 5. Vision Engine

### Responsibilities

- Accept uploaded images, PDFs, screenshots, camera captures, and text submissions.
- Extract printed text, handwritten math, equations, diagrams, labels, tables, graph axes, and layout relationships.
- Normalize extracted content into a canonical question-understanding artifact.
- Attach confidence scores and ambiguity markers.
- Preserve links back to original upload regions for teacher review and debugging.
- Emit extraction events for downstream analysis and analytics.

### Inputs

- Original upload asset references.
- Tenant, student, locale, grade, and accessibility context where allowed.
- Extraction policy, privacy policy, provider routing policy, and trace IDs.

### Outputs

- Extracted text.
- Structured equation candidates.
- Diagram and layout metadata.
- Confidence report.
- Ambiguity report.
- Source-region references.

### Design Decisions

The Vision Engine is independent because OCR, handwriting recognition, and multimodal reasoning will change rapidly. A future TeacherAI vision model must be replaceable without changing pedagogy, lesson planning, rendering, or teacher review.

## 6. Pedagogy Engine

### Responsibilities

- Determine teaching strategy for a student, class, topic, and difficulty level.
- Identify prerequisite knowledge and likely misconceptions.
- Choose scaffolding depth, hint strategy, questioning style, and checks for understanding.
- Apply teacher-defined teaching styles when available.
- Adapt strategy using student history, mastery data, accessibility needs, and teacher preferences.
- Produce a structured pedagogy plan for the Lesson Planner and Interaction Engine.

### Inputs

- Canonical question artifact.
- Question classification and learning objectives.
- Student mastery profile.
- Teacher style profile.
- Curriculum standards and classroom context.
- Historical misconception signals.

### Outputs

- Teaching strategy.
- Scaffolding plan.
- Misconception plan.
- Hint policy.
- Check-for-understanding plan.
- Tone and language guidance.

### Design Decisions

Pedagogy must be separate from LLM generation because teaching quality is not just text generation. This engine is where TeacherAI becomes an experienced teacher: it controls how much to reveal, when to ask, when to scaffold, and how to diagnose misunderstanding.

## 7. Lesson Planner

### Responsibilities

- Convert question understanding and pedagogy strategy into a structured lesson plan.
- Produce ordered lesson steps, explanations, mathematical statements, examples, checks for understanding, misconceptions, and optional practice prompts.
- Maintain strict output schemas so lessons are reviewable, verifiable, renderable, localizable, and reusable as datasets.
- Version generated lesson plans and preserve model/provider metadata.
- Request verification before a lesson becomes trusted for student playback.

### Inputs

- Canonical question artifact.
- Question classification.
- Pedagogy plan.
- Curriculum and grade context.
- Teacher style constraints.
- LLM provider policy.

### Outputs

- Structured lesson plan.
- Lesson step graph.
- Narration draft.
- Misconception explanations.
- Practice suggestions.
- Generation metadata and trace data.

### Design Decisions

The Lesson Planner is not a renderer and not a voice engine. It produces educational structure. Keeping the output structured allows teachers to edit steps, math verifiers to validate claims, renderers to produce multiple formats, and dataset pipelines to use approved lessons.

## 8. Math Verification Engine

### Responsibilities

- Validate algebraic transformations, arithmetic, units, geometry statements, graph interpretations, and final answers where possible.
- Compare generated lesson steps against the original question and target learning objective.
- Flag unverifiable, ambiguous, unsupported, or risky mathematical claims.
- Produce machine-readable verification reports for teacher review, student safety, and model evaluation.
- Support multiple verification strategies: symbolic solvers, numeric checks, theorem rules, graph validators, and LLM-assisted critique behind strict controls.

### Inputs

- Structured lesson plan.
- Original/canonical question artifact.
- Expected answer if teacher-provided.
- Verification policy.
- Subject-specific verifier adapters.

### Outputs

- Step-level correctness status.
- Final-answer status.
- Confidence score.
- Error and warning list.
- Suggested correction targets.
- Verifier trace metadata.

### Design Decisions

Verification must be independent from lesson generation because the model that creates an explanation should not be the only authority on correctness. Independent verification improves safety, teacher trust, and training-data quality.

## 9. Renderer Engine

### Responsibilities

- Convert structured lesson plans into target-specific visual artifacts.
- Support whiteboard scenes first, and later video frames, PDFs, images, mobile-native scene graphs, and accessibility-first text views.
- Enforce deterministic rendering from structured lesson artifacts.
- Synchronize visual frames with lesson steps and voice timings.
- Emit render metadata for playback, analytics, and debugging.

### Inputs

- Verified structured lesson plan.
- Renderer target and device constraints.
- Accessibility settings.
- Theme and brand settings.
- Optional voice timing metadata.

### Outputs

- Whiteboard document.
- Scene graph.
- Frame timing map.
- Rendered assets.
- Accessibility alternatives.
- Render trace metadata.

### Design Decisions

AI providers must never directly draw. The Renderer Engine is the only system allowed to create drawable artifacts from lesson plans. This keeps rendering deterministic, testable, accessible, portable, and independent from AI providers.

## 10. Voice Engine

### Responsibilities

- Generate spoken narration from lesson narration text.
- Produce audio assets, captions, transcripts, word timings, and scene timing metadata.
- Support multiple voices, locales, accessibility settings, speed preferences, and teacher/school policies.
- Regenerate voice artifacts without changing lesson content.
- Coordinate with Renderer Engine so whiteboard scenes can synchronize with narration.

### Inputs

- Lesson narration text.
- Lesson step identifiers.
- Voice policy.
- Locale and accessibility settings.
- Teacher or school voice preferences.

### Outputs

- Audio files.
- Captions.
- Transcript.
- Word/phrase timings.
- Step-to-audio synchronization map.
- Voice provider metadata.

### Design Decisions

Voice is separate because audio generation, localization, accessibility, and provider capabilities evolve independently from lesson planning. A lesson should remain stable while narration can be re-voiced or localized.

## 11. Teacher Feedback Engine

### Responsibilities

- Capture teacher approvals, rejections, edits, explanations, rubrics, ratings, and correction notes.
- Compare AI-generated versions with teacher-edited versions.
- Create structured feedback signals for quality monitoring, dataset eligibility, and training.
- Maintain audit trails of reviewer identity, timestamps, changes, and rationale.
- Route low-confidence, high-impact, or flagged lessons into teacher review queues.

### Inputs

- Generated lesson plan.
- Verification report.
- Render and voice artifacts.
- Student interaction outcomes.
- Teacher edits and review decisions.

### Outputs

- Reviewed lesson version.
- Feedback event.
- Quality score.
- Correction labels.
- Dataset candidate signal.
- Review audit record.

### Design Decisions

Teacher feedback is an engine because TeacherAI improves through expert review, not by blindly training on all AI output. This engine protects educational quality and creates the bridge between product usage and model improvement.

## 12. Dataset Engine

### Responsibilities

- Convert teacher-approved artifacts into dataset candidates.
- Apply privacy, consent, quality, deduplication, licensing, curriculum, and safety filters.
- Create versioned datasets for evaluation, retrieval, fine-tuning, and regression testing.
- Preserve lineage from dataset examples back to source lesson versions, teacher approvals, and model metadata.
- Export datasets to training infrastructure without exposing unauthorized student data.

### Inputs

- Teacher-approved lesson versions.
- Teacher feedback signals.
- Student outcome signals where policy allows.
- Privacy and retention policies.
- Curriculum taxonomy and quality gates.

### Outputs

- Dataset candidates.
- Dataset versions.
- Evaluation sets.
- Fine-tuning exports.
- Retrieval indexes.
- Dataset lineage metadata.

### Design Decisions

Dataset curation must be independent from teacher review and training. The Dataset Engine is the quality gate that prevents raw AI output, private student data, or unapproved content from entering model improvement workflows.

## 13. Training Engine

### Responsibilities

- Run fine-tuning, evaluation, regression testing, and model comparison workflows.
- Track model candidates, datasets, hyperparameters, prompts, metrics, safety evaluations, and deployment status.
- Register models in a model registry.
- Support controlled rollout, rollback, A/B evaluation, and provider routing policies.
- Feed evaluation results back to Admin, Teacher Feedback, Dataset, and Analytics systems.

### Inputs

- Versioned datasets.
- Evaluation suites.
- Baseline model registry entries.
- Training policy and budget constraints.
- Safety and quality thresholds.

### Outputs

- Model candidates.
- Evaluation reports.
- Safety reports.
- Model registry records.
- Rollout recommendations.
- Regression findings.

### Design Decisions

Training must be separate from runtime tutoring. Runtime student learning requires reliability and safety; training requires experimentation. Separating them allows careful promotion of improved TeacherAI models without destabilizing production lessons.

## 14. End-to-End Data Flow

### 14.1 Lesson Creation Flow

```text
Upload Asset
  -> Vision Engine creates Question Extraction Artifact
  -> Classification service creates Question Analysis
  -> Pedagogy Engine creates Pedagogy Plan
  -> Lesson Planner creates Structured Lesson Plan
  -> Math Verification Engine creates Verification Report
  -> Renderer Engine creates Whiteboard Artifact
  -> Voice Engine creates Voice Artifact
  -> Learning Session opens for student playback
```

### 14.2 Teacher Review and Improvement Flow

```text
Generated Lesson + Verification + Render + Voice + Student Outcomes
  -> Teacher Feedback Engine creates review task
  -> Teacher approves/edits/rejects
  -> Reviewed Artifact Version is created
  -> Dataset Engine evaluates eligibility
  -> Dataset Version is produced
  -> Training Engine evaluates/fine-tunes model candidate
  -> Admin-approved model rollout updates Provider Router
```

### 14.3 Student Interaction Flow

```text
Student asks question or requests hint
  -> Learning Session context is loaded
  -> Pedagogy Engine chooses response strategy
  -> Lesson Planner or Interaction Planner creates structured response
  -> Math Verification Engine validates mathematical claims
  -> Renderer Engine updates visual artifact if needed
  -> Voice Engine generates optional narration
  -> Teacher Feedback Engine may receive flagged interaction
  -> Analytics records learning signals
```

## 15. Engine Communication Rules

1. Engines communicate through versioned artifacts, APIs, and events.
2. Engines do not directly read each other's private databases.
3. Every engine input and output includes tenant, trace, version, and policy context.
4. Engine outputs are immutable once published; corrections create new versions.
5. Runtime engines do not depend on training infrastructure availability.
6. Dataset and Training Engines do not consume unapproved student content unless policy explicitly allows it.
7. Provider-specific metadata is stored for audit and debugging but does not leak into domain contracts.
8. Failed engine jobs are replayable from immutable inputs.

## 16. Engine Events

```text
VisionExtractionRequested
VisionExtractionCompleted
QuestionAnalysisCompleted
PedagogyPlanCreated
LessonPlanCreated
LessonVerificationCompleted
RenderArtifactCreated
VoiceArtifactCreated
TeacherReviewRequested
TeacherFeedbackSubmitted
ReviewedLessonVersionCreated
DatasetCandidateCreated
DatasetVersionCreated
TrainingRunStarted
TrainingRunCompleted
ModelCandidateRegistered
ModelPromotionApproved
ModelRolloutStarted
ModelRollbackRequested
```

## 17. Engine Scaling Model

| Engine | Scaling Strategy |
| --- | --- |
| Vision Engine | Queue-based workers; GPU/multimodal capacity isolated from API traffic. |
| Pedagogy Engine | Stateless policy and model workers; cache reusable strategy templates. |
| Lesson Planner | Queue-based LLM orchestration with provider routing, rate limits, and fallbacks. |
| Math Verification Engine | CPU-heavy verifier workers; subject-specific verifier pools. |
| Renderer Engine | Horizontally scalable render workers; target-specific worker pools. |
| Voice Engine | Queue-based TTS workers; locale/provider-specific pools. |
| Teacher Feedback Engine | Relational workflow service plus event stream. |
| Dataset Engine | Batch and streaming curation workers with lineage storage. |
| Training Engine | Offline batch/GPU jobs isolated from runtime workloads. |

## 18. Observability and Governance

Every engine must emit:

- Trace IDs across engine boundaries.
- Input artifact version and output artifact version.
- Provider/model identifiers where applicable.
- Latency, cost, retry, and fallback metrics.
- Quality, confidence, and verification metrics.
- Safety and policy decisions.
- Teacher feedback and correction linkage when available.

Decision: observability is required because AI quality cannot be managed if outputs, versions, costs, provider choices, and teacher corrections are not traceable.

## 19. Implementation Guardrails

When implementation begins:

1. Define artifact schemas before provider adapters.
2. Build engine ports before engine implementations.
3. Add one engine at a time behind queues and idempotent job contracts.
4. Require verification before student-visible lesson playback.
5. Require teacher approval before dataset inclusion.
6. Keep training jobs isolated from runtime systems.
7. Add observability from the first engine implementation.
8. Never let a frontend or API route call an AI provider directly.
9. Never let an LLM provider output renderer-specific drawing commands.
10. Never train on unversioned, unapproved, or lineage-free artifacts.
