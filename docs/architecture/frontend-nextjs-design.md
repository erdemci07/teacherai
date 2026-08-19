# Frontend Design: Next.js TypeScript App Router Architecture

## 1. Purpose

TeacherAI frontend will be built with Next.js, TypeScript, and the App Router. This document defines the frontend architecture only. It does not implement UI, routes, components, business logic, or API calls.

The frontend must support Student, Teacher, and Admin experiences while preserving long-term modularity for lesson viewing, whiteboard playback, future video lessons, future voice lessons, future AI chat, and future analytics.

## 2. Frontend Principles

- Use Next.js App Router for route groups, layouts, nested loading states, metadata, and server/client component boundaries.
- Use TypeScript everywhere with generated API types from backend contracts.
- Use feature-based modules so Student, Teacher, Admin, Authentication, Dashboard, History, Lesson Viewer, Whiteboard Viewer, AI Chat, Voice, Video, and Analytics can evolve independently.
- Keep business workflows in feature application modules, not directly inside pages.
- Keep rendering engines, media players, API clients, auth adapters, and analytics adapters replaceable.
- Separate portal shell, feature UI, domain-facing client models, and infrastructure adapters.
- Keep server components responsible for data loading and composition where appropriate; keep interactive playback, chat, whiteboard, and media controls in client components.
- Never allow frontend AI chat or whiteboard components to bypass backend lesson-plan, renderer, safety, or teacher-review workflows.

## 3. Proposed Frontend Folder Structure

```text
frontend/
  package.json
  tsconfig.json
  next.config.ts

  app/
    layout.tsx                         # Root HTML shell and global providers composition.
    error.tsx                          # Root error boundary.
    not-found.tsx

    (public)/
      login/
        page.tsx
      forgot-password/
        page.tsx

    (student)/
      layout.tsx                       # Student portal navigation and auth boundary.
      dashboard/
        page.tsx
      history/
        page.tsx
      lessons/
        [lessonId]/
          page.tsx
      whiteboard/
        [lessonId]/
          page.tsx
      practice/
        page.tsx
      chat/
        page.tsx                       # Future AI chat entry point.

    (teacher)/
      layout.tsx                       # Teacher portal navigation and auth boundary.
      dashboard/
        page.tsx
      reviews/
        page.tsx
        [reviewId]/
          page.tsx
      lessons/
        page.tsx
        [lessonId]/
          page.tsx
      datasets/
        page.tsx
      analytics/
        page.tsx                       # Future teacher analytics.

    (admin)/
      layout.tsx                       # Admin portal navigation and auth boundary.
      dashboard/
        page.tsx
      users/
        page.tsx
      tenants/
        page.tsx
      providers/
        page.tsx
      models/
        page.tsx
      analytics/
        page.tsx                       # Future platform analytics.

  src/
    core/
      config/                          # Runtime-safe public config and feature flags.
      routing/                         # Typed route definitions and portal route policies.
      auth/                            # Auth session contracts and auth adapter boundary.
      telemetry/                       # Frontend logging, metrics, and tracing ports.
      errors/                          # Frontend error classification and display rules.
      i18n/                            # Locale, formatting, and translation boundaries.
      accessibility/                   # Shared accessibility primitives and policies.

    shared/
      ui/                              # Design system primitives.
      layout/                          # Shared layout components.
      forms/                           # Form primitives and validation adapters.
      state/                           # Shared state utilities, not global business stores.
      api/                             # Generated API client boundary and request utilities.
      media/                           # Media primitives shared by video/voice/whiteboard.
      testing/                         # Shared test utilities.

    features/
      authentication/
        application/
        components/
        schemas/
        hooks/
        tests/

      student_dashboard/
        application/
        components/
        schemas/
        hooks/
        tests/

      teacher_dashboard/
        application/
        components/
        schemas/
        hooks/
        tests/

      admin_dashboard/
        application/
        components/
        schemas/
        hooks/
        tests/

      history/
        application/
        components/
        schemas/
        hooks/
        tests/

      lesson_viewer/
        application/
        components/
        schemas/
        hooks/
        tests/

      whiteboard_viewer/
        application/
        engine/
        components/
        schemas/
        hooks/
        tests/

      video_lessons/
        application/
        player/
        components/
        schemas/
        hooks/
        tests/

      voice_lessons/
        application/
        player/
        components/
        schemas/
        hooks/
        tests/

      ai_chat/
        application/
        components/
        schemas/
        hooks/
        tests/

      analytics/
        application/
        components/
        schemas/
        hooks/
        tests/

    adapters/
      auth/
        next_auth/
        custom_oidc/
      api/
        rest/
        streaming/
      whiteboard/
        canvas_renderer/
        svg_renderer/
        webgl_renderer/
      video/
        hls_player/
        mp4_player/
      voice/
        web_audio/
        html_audio/
      analytics/
        product_analytics/
        learning_analytics/
      storage/
        browser_cache/
        indexed_db/

    contracts/
      api/                             # Generated backend API types.
      events/                          # Frontend-consumed event types.
      lesson/                          # Shared lesson-viewer and renderer contracts.
      auth/                            # Session and role contracts.
```

## 4. App Router Design

Next.js route groups separate portals without changing URLs purely for folder organization.

| Route Group | Purpose | Access |
| --- | --- | --- |
| `(public)` | Login, password reset, public landing pages. | Anonymous or unauthenticated users. |
| `(student)` | Student dashboard, history, lesson viewer, whiteboard, practice, future chat. | Authenticated students and authorized guardians/teachers where applicable. |
| `(teacher)` | Teacher dashboard, reviews, datasets, lesson review, classroom analytics. | Authenticated teachers and school staff. |
| `(admin)` | Tenant, provider, model, user, policy, and platform analytics management. | Authenticated admins only. |

Design decisions:

- Each portal has its own `layout.tsx` so navigation, role checks, and portal-specific providers stay isolated.
- Pages compose feature modules; pages do not own application workflows.
- Server components should load initial read models when possible.
- Client components should be limited to interactive features such as whiteboard playback, media controls, chat input, optimistic UI, and real-time progress.

## 5. Feature Module Contract

Every frontend feature must use the same internal structure.

| Folder | Responsibility | Forbidden Content |
| --- | --- | --- |
| `application/` | Frontend use cases, view models, query orchestration, command orchestration, state machines. | JSX presentation details, direct browser APIs unless behind an adapter. |
| `components/` | Feature-specific UI components. | Backend business rules, raw API fetch logic, provider-specific SDK calls. |
| `schemas/` | Client-side validation schemas and typed form/input contracts. | Persistence or backend-only models. |
| `hooks/` | Feature-specific hooks that compose application services and UI state. | Cross-feature global business stores. |
| `tests/` | Component, hook, accessibility, and contract tests. | Tests depending on unrelated feature internals. |

Decision: the feature contract mirrors the backend's feature isolation so Student, Teacher, Admin, Lesson, Whiteboard, Chat, and Analytics teams can work independently.

## 6. Portal Responsibilities

### 6.1 Student Portal

Responsibilities:

- Show dashboard with active lessons, weaknesses, progress, and recommended next actions.
- Show history of submitted questions, generated lessons, practice sessions, and outcomes.
- Display Lesson Viewer with structured steps, explanations, checks for understanding, and teacher-approved versions.
- Display Whiteboard Viewer driven by renderer artifacts, not direct AI drawing commands.
- Support future video lessons and voice lessons as media layers over structured lessons.
- Support future AI chat through backend-mediated session APIs.

Design decision: the student portal is optimized for low-latency learning and resumability. It must not contain teacher review, provider selection, or prompt logic.

### 6.2 Teacher Portal

Responsibilities:

- Show teacher dashboard with pending reviews, class performance, lesson quality, and flagged student struggles.
- Review generated lessons, whiteboard output, voice narration, and verification reports.
- Edit lesson explanations, approve/reject lesson versions, and create teaching styles.
- View history for classes, students, reviewed lessons, and dataset candidates.
- Support future analytics for classroom mastery, misconceptions, and AI quality.

Design decision: teacher portal actions create versioned backend artifacts. The frontend never mutates generated lessons locally as the source of truth.

### 6.3 Admin Portal

Responsibilities:

- Manage tenants, schools, users, roles, provider configuration, model rollout, feature flags, and policy settings.
- View platform dashboard for usage, provider cost, latency, model quality, and operational incidents.
- Support future analytics for compliance, safety, dataset growth, and training quality.

Design decision: admin features are isolated from student and teacher bundles as much as practical to reduce accidental exposure and keep authorization boundaries clear.

## 7. Authentication and Authorization

Authentication is a cross-cutting feature with portal-specific authorization policies.

Design rules:

1. Authentication adapter is replaceable: NextAuth, custom OIDC, school SSO, or future enterprise identity can be swapped.
2. Session shape is defined in `contracts/auth`, not inside UI components.
3. Route groups enforce portal-level access through layouts and middleware.
4. Feature components receive actor capabilities, not raw permission tables.
5. Sensitive authorization decisions are enforced by the backend; frontend checks only improve UX and prevent accidental navigation.
6. Tokens and session state are handled through secure framework-supported mechanisms, not custom localStorage token logic.

## 8. Dashboard Architecture

Dashboards are read-model consumers. They should not compute authoritative learning mastery or AI quality in the browser.

| Dashboard | Data Source | Purpose |
| --- | --- | --- |
| Student Dashboard | Student learning read models. | Current lessons, weaknesses, recommendations, streaks, progress. |
| Teacher Dashboard | Teacher/classroom read models. | Review workload, student struggles, class mastery, lesson quality. |
| Admin Dashboard | Platform/admin read models. | Tenants, costs, provider health, model quality, incidents. |

Decision: dashboards use backend-created read models because analytics computation must be consistent, auditable, and scalable.

## 9. History Architecture

History is a shared feature with portal-specific views.

Student history includes uploads, lessons, sessions, attempts, and progress.
Teacher history includes reviews, edits, approvals, class lessons, and dataset candidates.
Admin history includes audit logs, provider changes, model rollouts, user changes, and policy changes.

Decision: history views should be query-driven and paginated. Infinite client-side history state must not become the source of truth.

## 10. Lesson Viewer Architecture

Lesson Viewer consumes structured lesson artifacts from backend APIs.

Responsibilities:

- Display lesson metadata, topic, subtopic, difficulty, learning objectives, steps, misconceptions, checks for understanding, and teacher approval state.
- Coordinate optional Whiteboard, Voice, Video, and Chat panels.
- Support accessibility modes such as text-only lesson view, captions, keyboard navigation, and reduced motion.
- Display version and review status when relevant for teachers.

Decision: Lesson Viewer is the composition layer for learning artifacts. It does not generate lessons and does not render raw AI output as trusted instruction.

## 11. Whiteboard Viewer Architecture

Whiteboard Viewer consumes renderer output produced by backend rendering services.

Responsibilities:

- Playback deterministic whiteboard scenes.
- Synchronize scene steps with narration timings.
- Support future renderer engines such as Canvas, SVG, WebGL, or native mobile rendering.
- Emit playback events for analytics and learning-session progress.
- Support pausing, replaying, stepping, zooming, reduced motion, and accessible text alternatives.

Decision: Whiteboard Viewer is an adapter-driven playback surface. It must not ask AI how to draw; it only consumes structured render artifacts.

## 12. Future Video Lessons

Video lessons should be treated as another renderer/media artifact, not a separate lesson source.

Design rules:

- Video player consumes video artifacts linked to a lesson version.
- Video timing should map back to lesson steps and narration segments.
- Captions and transcripts are required first-class artifacts.
- Video generation jobs remain backend-owned.

Decision: video remains downstream of structured lesson plans so teacher review and dataset lineage remain intact.

## 13. Future Voice Lessons

Voice lessons are synchronized narration artifacts over lesson steps.

Design rules:

- Voice player consumes backend voice artifacts and timing metadata.
- Voice can be regenerated without changing the lesson plan.
- Captions and transcript display must be supported.
- Voice controls are shared with video and whiteboard playback where possible.

Decision: separating voice from lesson content supports localization, accessibility, teacher review, and provider replacement.

## 14. Future AI Chat

AI Chat must be session-based and backend-mediated.

Design rules:

- Chat UI sends student turns to Learning Session APIs.
- Backend decides pedagogy, safety, math verification, provider routing, and memory retrieval.
- Chat responses are structured messages that can reference lesson steps, whiteboard frames, hints, or practice items.
- Chat events are stored for learning analytics and teacher review when policy requires it.
- Chat UI never calls LLM providers directly from the browser.

Decision: direct browser-to-LLM calls would bypass safety, cost controls, provider abstraction, teacher review, and student data protection.

## 15. Future Analytics

Frontend analytics is event capture and dashboard display, not authoritative metric computation.

Captured frontend events may include:

- Lesson opened.
- Lesson step viewed.
- Whiteboard frame played.
- Voice segment replayed.
- Hint requested.
- Chat message submitted.
- Practice answer submitted.
- Teacher review action started.
- Teacher approval submitted.

Design rules:

- Events use versioned contracts.
- Events include tenant, actor, session, lesson, trace, and client context where allowed.
- Events are buffered and retried safely.
- Analytics failures must not block learning interactions.
- Privacy policy controls what is captured and retained.

## 16. State Management

State is classified by ownership:

| State Type | Owner | Examples |
| --- | --- | --- |
| Server state | Backend APIs/read models | Lessons, history, dashboards, review queues. |
| Session interaction state | Learning Session backend plus local optimistic state. | Current chat turn, active hint, active whiteboard step. |
| UI state | Browser/client component. | Open panels, tabs, playback controls, modal state. |
| Auth state | Auth adapter and backend session. | Current actor, tenant, roles, capabilities. |
| Analytics buffer | Telemetry adapter. | Pending non-blocking events. |

Decision: do not create one global frontend store for everything. Server state, UI state, playback state, auth state, and analytics buffers have different lifecycles and consistency requirements.

## 17. API Client Architecture

Frontend API access uses generated TypeScript clients from backend contracts.

Design rules:

- Feature modules call application-level API wrappers, not raw `fetch` spread across components.
- API adapters add trace IDs, tenant context, auth credentials, locale, idempotency keys, and error mapping.
- Streaming adapters handle lesson generation progress, chat streams, and whiteboard synchronization events.
- API errors are mapped into user-safe messages and developer-observable telemetry.

Decision: generated clients prevent drift between FastAPI contracts and Next.js consumers.

## 18. Testing Strategy

Required frontend tests:

- Route contract tests for portal access boundaries.
- Component tests for feature UI states.
- Hook/application tests with fake API adapters.
- Accessibility tests for dashboards, lesson viewer, whiteboard controls, forms, and review flows.
- Visual regression tests for design-system and critical lesson playback screens.
- Contract tests against generated API types.
- End-to-end tests for login, dashboard navigation, lesson viewing, history, and review flows once implemented.

Testing rules:

- Feature tests should not import unrelated feature internals.
- Whiteboard, voice, video, and chat tests use fake artifacts and fake streaming adapters by default.
- No tests should call real LLM, voice, renderer, or analytics vendors.

## 19. Scalability and Performance Decisions

- Use route-level code splitting through App Router route groups.
- Keep admin-heavy code out of student-first paths where practical.
- Cache read-only dashboard and history data according to backend cache policy.
- Stream progress for long-running generation instead of blocking pages.
- Lazy-load whiteboard, video, voice, and chat engines when not immediately visible.
- Use CDN-backed media artifacts for whiteboard assets, video, audio, and thumbnails.
- Use accessibility and low-bandwidth modes for students with constrained devices.

## 20. Implementation Guardrails

When implementation begins:

1. Create route shells and feature folders before writing UI logic.
2. Add generated API contracts before feature API calls.
3. Implement authentication boundaries before protected portal pages.
4. Implement Lesson Viewer before Whiteboard Viewer, Voice, Video, or Chat.
5. Implement Whiteboard Viewer only against renderer artifacts.
6. Keep AI Chat backend-mediated from the first version.
7. Add accessibility tests before releasing student learning flows.
8. Add analytics capture as a non-blocking adapter, not inline UI business logic.
