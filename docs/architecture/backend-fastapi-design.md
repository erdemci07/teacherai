# Backend Design: Python FastAPI Clean Architecture

## 1. Purpose

TeacherAI backend will be built with Python and FastAPI, but the framework is only a delivery mechanism. The backend must preserve Clean Architecture, feature isolation, dependency injection, and provider replaceability from the first implementation milestone.

This document is a design contract only. It does not implement business logic.

## 2. Backend Principles

- Use FastAPI for HTTP transport, request validation integration, OpenAPI generation, dependency wiring, and async endpoints.
- Use Clean Architecture so domain and application rules do not depend on FastAPI, SQLAlchemy, Redis, cloud SDKs, AI SDKs, or queue libraries.
- Use feature-based modules so every bounded capability owns its API, service, repository contract, models, schemas, domain rules, and tests.
- Use dependency injection for repositories, services, provider adapters, settings, transaction managers, and background job clients.
- Keep API routes thin: routes authenticate, validate, authorize, call services/use cases, and map responses.
- Do not put prompts, AI provider calls, rendering logic, SQL queries, or teaching decisions directly in routes.
- Keep all modules independently testable with mocked ports and in-memory repositories.

## 3. Proposed Backend Folder Structure

```text
backend/
  pyproject.toml
  README.md
  alembic.ini

  app/
    main.py                         # FastAPI application factory only.
    core/
      config.py                     # Typed environment and tenant/provider config loading.
      container.py                  # Dependency injection container composition root.
      security.py                   # Auth primitives and current actor dependency.
      errors.py                     # Application error mapping to HTTP responses.
      logging.py                    # Structured logging and tracing setup.
      pagination.py                 # Shared pagination primitives.
      idempotency.py                # Idempotency key contracts.

    shared/
      domain/
        entity.py                   # Base entity/value-object conventions.
        events.py                   # Domain event base contracts.
        identifiers.py              # Strong ID types.
      application/
        unit_of_work.py             # Transaction boundary port.
        clock.py                    # Time provider port.
        event_bus.py                # Event publishing port.
      infrastructure/
        database.py                 # Database session adapter setup.
        queue.py                    # Queue adapter setup.
        object_storage.py           # Object storage adapter setup.
      api/
        dependencies.py             # Shared API dependencies only.
        responses.py                # Standard response envelopes.

    features/
      identity/
        api/
          routes.py
          dependencies.py
        service/
          commands.py
          queries.py
          service.py
        repository/
          interface.py
          sqlalchemy.py
        models/
          orm.py
          read_models.py
        schemas/
          requests.py
          responses.py
        domain/
          entities.py
          value_objects.py
          policies.py
          events.py
        tests/
          test_api_contracts.py
          test_service.py
          test_repository_contract.py

      question_intake/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      vision/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      question_analysis/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      pedagogy/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      lesson_planning/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      math_verification/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      rendering/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      voice/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      learning_session/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      teacher_review/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      dataset/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      training/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

      analytics/
        api/
        service/
        repository/
        models/
        schemas/
        domain/
        tests/

    adapters/
      llm/
        openai/
        claude/
        gemini/
        deepseek/
        qwen/
        llama/
        teacherai_model/
      vision/
        ocr/
        multimodal_llm/
        handwriting/
      renderer/
        whiteboard/
        video/
        pdf/
      voice/
        tts_vendor/
        teacherai_voice/
      database/
        postgres/
      storage/
        s3_compatible/
      queue/
        redis/
        kafka/

  tests/
    integration/
    contract/
    e2e/
```

## 4. Feature Module Contract

Every feature must contain the same internal structure so engineers can move across the codebase without relearning architecture.

| Folder | Responsibility | Allowed Dependencies | Forbidden Dependencies |
| --- | --- | --- | --- |
| `api/` | FastAPI routers, route dependencies, request/response mapping. | Feature schemas, service interfaces, shared API dependencies. | SQLAlchemy queries, AI SDK calls, domain decisions. |
| `service/` | Application use cases, commands, queries, orchestration, transaction boundaries. | Feature domain, repository interfaces, provider ports, unit of work. | FastAPI request objects, vendor SDKs, ORM-specific queries. |
| `repository/` | Repository interfaces and persistence adapters. | Feature domain, ORM models, shared DB adapter. | FastAPI routes, external AI provider calls. |
| `models/` | Persistence models and read-model projections. | Database adapter primitives. | Business policy logic. |
| `schemas/` | Pydantic request/response schemas and API DTOs. | Primitive types, shared schema utilities. | ORM session usage, provider SDKs. |
| `domain/` | Entities, value objects, policies, domain events, invariants. | Shared domain primitives only. | FastAPI, SQLAlchemy, Pydantic transport schemas, SDKs. |
| `tests/` | Unit, contract, repository, and API tests for the feature. | Test fixtures and feature public contracts. | Cross-feature internals. |

## 5. Dependency Direction Inside a Feature

```text
api -> service -> domain
api -> schemas
service -> repository interfaces
repository implementations -> models
infrastructure adapters -> service ports
```

The domain layer is the center. It has no dependency on FastAPI, Pydantic API schemas, SQLAlchemy, cloud SDKs, or LLM clients.

## 6. Dependency Injection Design

FastAPI dependencies should be adapters around a central application container. The container is the composition root that wires settings, repositories, services, provider adapters, unit-of-work implementations, and event publishers.

Design rules:

1. Route functions receive services through dependency injection.
2. Services receive repository interfaces and provider ports through constructor injection.
3. Repository implementations receive database sessions through dependency injection.
4. Provider adapters receive typed configuration, HTTP clients, retry policies, and telemetry dependencies through constructor injection.
5. Tests replace providers and repositories with fakes without importing FastAPI.
6. The dependency container is the only place where concrete infrastructure classes are selected.

Decision: constructor injection keeps services deterministic and easy to test. FastAPI's dependency system should be used at the boundary, not throughout the domain.

## 7. FastAPI API Design

Routes are grouped by feature and mounted by API version.

```text
/api/v1/identity/*
/api/v1/questions/*
/api/v1/vision/jobs/*
/api/v1/question-analyses/*
/api/v1/lesson-plans/*
/api/v1/rendering/jobs/*
/api/v1/voice/jobs/*
/api/v1/learning-sessions/*
/api/v1/teacher/reviews/*
/api/v1/datasets/*
/api/v1/training/jobs/*
/api/v1/analytics/events
```

Route responsibilities:

- Parse and validate request DTOs.
- Resolve current actor, tenant, roles, locale, trace ID, and idempotency key.
- Call exactly one application service/use case per route.
- Convert application results into response DTOs.
- Map known application errors to HTTP status codes.

Route non-responsibilities:

- No SQL queries.
- No AI prompts.
- No direct provider SDK calls.
- No rendering decisions.
- No math verification rules.
- No teacher review policy rules.

## 8. Service Layer Design

The service layer contains application use cases. A service method represents a business action, not a database table operation.

Examples of future service actions:

- `SubmitQuestion`
- `StartVisionExtraction`
- `AnalyzeQuestion`
- `CreateLessonPlan`
- `VerifyLessonPlan`
- `RenderLessonPlan`
- `SynthesizeLessonVoice`
- `StartLearningSession`
- `RecordStudentInteraction`
- `RequestTeacherReview`
- `ApproveLessonVersion`
- `CreateDatasetVersion`
- `StartTrainingJob`

Design decisions:

- Services coordinate domain objects and ports.
- Services own transaction boundaries through a unit-of-work port.
- Services publish domain/application events after successful state changes.
- Long-running AI, rendering, voice, and training work is scheduled as jobs instead of executed inside request/response routes.

## 9. Repository Design

Each feature defines repository interfaces near the service/domain boundary and concrete implementations in infrastructure-facing files.

Repository rules:

- Repository interfaces speak in domain concepts, not ORM rows.
- Repository implementations translate between ORM models and domain entities.
- Cross-feature data access happens through service APIs, domain events, or read models, not direct repository imports.
- Repository contract tests validate all implementations against the same behavior.

Decision: repository interfaces make PostgreSQL replaceable and prevent SQL-specific logic from becoming business logic.

## 10. Models and Schemas

### 10.1 Domain Models

Domain models represent business concepts such as lesson plans, review decisions, dataset versions, learning sessions, and provider policies. They protect invariants and emit domain events.

### 10.2 Persistence Models

Persistence models represent storage tables and indexes. They are optimized for database integrity and querying, not API responses.

### 10.3 API Schemas

Pydantic schemas represent API contracts. They are versioned, validated, documented in OpenAPI, and mapped to/from application command/query objects.

Decision: separating domain models, persistence models, and API schemas prevents framework and database concerns from leaking into teaching logic.

## 11. Backend Feature Responsibilities

| Feature | Responsibility |
| --- | --- |
| Identity | Tenants, schools, users, roles, classrooms, enrollment, permissions. |
| Question Intake | Student uploads, asset metadata, submission state, idempotency. |
| Vision | OCR, handwriting extraction, diagram detection, extraction confidence. |
| Question Analysis | Topic, subtopic, difficulty, objective, standard, prerequisite classification. |
| Pedagogy | Teaching strategy, scaffold selection, hints, misconceptions, checks for understanding. |
| Lesson Planning | Structured lesson plan creation and versioning. |
| Math Verification | Mathematical correctness checks, symbolic validation, verification reports. |
| Rendering | Whiteboard, video, PDF, and accessibility render job orchestration. |
| Voice | Narration synthesis, captions, timing metadata, voice policy. |
| Learning Session | Student session state, attempts, interactions, hints, mastery snapshots. |
| Teacher Review | Review queues, teacher edits, approvals, rejections, rubrics, teaching styles. |
| Dataset | Candidate selection, quality gates, privacy filtering, dataset versioning, exports. |
| Training | Fine-tuning jobs, evaluations, model registry, rollout policies. |
| Analytics | Event intake, learning metrics, quality metrics, provider cost and latency signals. |

## 12. Provider Abstraction Ports

Provider ports live outside vendor implementations and are injected into services.

| Port | Purpose |
| --- | --- |
| `LLMProviderPort` | Structured text generation for analysis, planning, feedback, rubrics, and interaction. |
| `VisionProviderPort` | Extract mathematical content, layout, diagrams, and confidence from uploads. |
| `RendererPort` | Convert structured lesson plans into target-specific artifacts. |
| `VoiceProviderPort` | Produce audio, captions, and word/scene timing metadata. |
| `MathVerifierPort` | Validate equations, transformations, and final answers. |
| `ObjectStoragePort` | Store uploads, render artifacts, voice files, and dataset exports. |
| `EventBusPort` | Publish domain/application events. |
| `JobQueuePort` | Schedule asynchronous work. |

Decision: ports allow OpenAI, Claude, Gemini, DeepSeek, Qwen, Llama, TeacherAI models, renderers, voice providers, databases, queues, and storage systems to be replaced without changing application services.

## 13. Testing Design

Each feature owns its tests.

Required test types:

- Domain tests for invariants and policies.
- Service tests with fake repositories and fake provider ports.
- API contract tests for request/response behavior and authorization boundaries.
- Repository contract tests shared by all repository implementations.
- Adapter contract tests for LLM, vision, renderer, voice, storage, and queue adapters.
- Integration tests for database migrations, unit-of-work behavior, and event publication.

Testing rules:

- Domain and service tests must not boot FastAPI.
- API tests may use FastAPI's test client and dependency overrides.
- Provider tests must not call paid external services by default.
- Every asynchronous job must be testable with an in-memory queue fake.

## 14. Migration Path

Implementation should proceed in thin vertical slices while preserving the full architecture:

1. Create backend project skeleton and dependency container.
2. Add shared primitives and feature folder templates.
3. Implement Identity and Question Intake boundaries first.
4. Add Lesson Plan contracts before any LLM provider integration.
5. Add one provider adapter behind ports only after service contracts exist.
6. Add renderer and voice adapters only after structured lesson plans are stable.
7. Add Teacher Review before using outputs as datasets.
8. Add Dataset and Training after teacher approval flows exist.

Decision: the architecture is complete now, but implementation should remain incremental and production-grade. No feature may bypass its module contract for speed.
