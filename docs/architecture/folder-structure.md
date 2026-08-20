# Future Folder Structure

This is the intended production repository structure. It is a design contract, not an instruction to implement all modules immediately.

```text
teacherai/
  apps/
    api-gateway/                 # Public API and BFF composition layer.
    student-portal/              # Student web/mobile frontend shell.
    teacher-portal/              # Teacher review and classroom frontend shell.
    admin-portal/                # Operations, tenant, policy, and provider admin UI.
    worker-runtime/              # Shared worker host for queue consumers.

  services/
    identity/                    # Tenants, schools, roles, classrooms, permissions.
    question-intake/             # Uploads and question submission lifecycle.
    vision-orchestration/        # OCR, handwriting, diagrams, multimodal extraction.
    question-analysis/           # Topic, subtopic, difficulty, objectives.
    pedagogy-engine/             # Teaching strategy, scaffolds, misconceptions.
    lesson-planning/             # Structured lesson plan generation.
    math-verification/           # Correctness validation and symbolic checks.
    rendering/                   # Whiteboard, video, PDF, image rendering.
    voice/                       # Narration, speech synthesis, captions, timing.
    learning-session/            # Student turns, hints, attempts, progress.
    teacher-review/              # Edits, approvals, rubrics, review queues.
    dataset/                     # Dataset curation, labeling, export.
    training/                    # Fine-tuning, evaluation, model registry.
    analytics/                   # Event processing, dashboards, weakness signals.
    notification/                # Email, in-app, and school notifications.

  packages/
    domain/                      # Enterprise-wide entities, value objects, policies.
    application/                 # Use-case contracts and ports shared by services.
    api-contracts/               # Versioned OpenAPI/AsyncAPI/GraphQL schemas.
    event-contracts/             # Versioned event schemas.
    config-contracts/            # Provider, tenant, safety, and feature config schemas.
    frontend-design-system/      # Shared UI components and accessibility primitives.
    frontend-api-client/         # Generated typed API client.
    whiteboard-player/           # Shared client-side whiteboard playback package.
    telemetry-client/            # Frontend/backend telemetry helpers.

  adapters/
    llm-providers/
      openai/
      claude/
      gemini/
      deepseek/
      qwen/
      llama/
      teacherai-model/
    vision-providers/
      ocr-engine/
      multimodal-llm/
      handwriting-model/
    renderers/
      whiteboard/
      video/
      pdf/
      mobile-native/
    voice-providers/
      text-to-speech-vendor/
      teacherai-voice-model/
    databases/
      postgres/
      document-store/
      vector-store/
      warehouse/
    queues/
      event-bus/
      job-queue/
    storage/
      object-storage/
      cdn/

  infrastructure/
    deployment/                  # Kubernetes, IaC, environments, secrets references.
    observability/               # Logging, tracing, metrics, alert definitions.
    security/                    # Policy templates, threat models, compliance controls.
    migrations/                  # Database migrations owned per bounded context.

  docs/
    architecture/
    product/
    runbooks/
    adr/                         # Architecture Decision Records.
```

## Folder Decisions

- `apps/` contains deployable entry points and no core business rules.
- `services/` contains bounded contexts that can start as modules and later split into independently deployable services.
- `packages/domain` and `packages/application` define stable policies and ports shared across services.
- `adapters/` isolates replaceable vendors and infrastructure implementations.
- `api-contracts` and `event-contracts` make integration boundaries explicit and versioned.
- `infrastructure/` contains deployment and operational assets, never product logic.
- `docs/adr` records irreversible or expensive architectural decisions.
