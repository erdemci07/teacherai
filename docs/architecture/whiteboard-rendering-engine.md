# Whiteboard Rendering Engine Architecture

## 1. Purpose

The Whiteboard Rendering Engine converts structured `LessonPlan` JSON into deterministic visual artifacts. AI never draws. AI providers generate structured educational content; the renderer owns all drawing, layout, styling, export, animation, and media-target conversion.

This document is architecture only. It does not implement rendering code, SVG generation, canvas drawing, video generation, or business logic.

## 2. Non-Negotiable Rendering Rule

```text
AI Provider -> LessonPlan JSON -> Whiteboard Rendering Engine -> Visual Artifacts
```

The AI output must not contain raw SVG, canvas commands, image drawing instructions, arbitrary CSS, or renderer-specific imperative commands. It may only produce validated lesson structure such as titles, explanation steps, equations, relationships, graph descriptions, geometry descriptions, table data, and pedagogical annotations.

Decision: separating lesson planning from rendering makes output reviewable by teachers, verifiable by math engines, accessible, deterministic, localizable, portable across clients, and safe for future dataset/training workflows.

## 3. Renderer Goals

- Convert one structured lesson plan into many output targets: SVG, PNG, JPEG/JPG, PDF, animated whiteboard, and future video.
- Support reusable visual primitives: titles, boxes, equations, arrows, cross marks, check marks, graphs, geometry, tables, and handwriting styles.
- Keep rendering deterministic so the same lesson plan, renderer version, theme, and target produce reproducible artifacts.
- Keep render targets pluggable so future mobile-native, WebGL, interactive HTML, and video pipelines can be added without changing lesson planning.
- Support accessibility alternatives such as semantic text descriptions, captions, high-contrast themes, and reduced-motion animation plans.
- Support teacher review by preserving mapping between rendered elements and original lesson plan nodes.

## 4. Rendering Pipeline

```text
LessonPlan JSON
  -> Schema Validation
  -> Render Intent Builder
  -> Layout Planner
  -> Scene Graph Builder
  -> Style Resolver
  -> Target Renderer
  -> Export Adapter
  -> Render Artifact Registry
```

### Pipeline Stages

| Stage | Responsibility | Output |
| --- | --- | --- |
| Schema Validation | Validate `LessonPlan` against versioned contracts. | Validated lesson artifact or validation errors. |
| Render Intent Builder | Convert lesson steps into renderer-neutral visual intents. | Render intent tree. |
| Layout Planner | Determine frames, regions, spacing, grouping, pagination, and responsive constraints. | Layout plan. |
| Scene Graph Builder | Create deterministic scene nodes from layout and intents. | Renderer-neutral scene graph. |
| Style Resolver | Apply theme, handwriting style, colors, fonts, line weights, accessibility mode. | Styled scene graph. |
| Target Renderer | Render scene graph to SVG, raster, PDF, animation, or video pipeline input. | Target-specific intermediate artifact. |
| Export Adapter | Encode/export SVG, PNG, JPEG/JPG, PDF, animated whiteboard, future video. | Final artifact files and metadata. |
| Artifact Registry | Store artifact versions, checksums, dimensions, timing maps, and source mappings. | Render artifact record. |

Decision: the scene graph is the stable internal contract. Output adapters may change, but lesson planning and layout logic remain independent.

## 5. Core Input: LessonPlan JSON

The renderer consumes validated `LessonPlan` JSON. The plan is educational and semantic, not graphical.

Conceptual structure:

```json
{
  "lessonPlanId": "lesson_123",
  "version": "1.0",
  "title": "Solving Linear Equations",
  "steps": [
    {
      "id": "step_1",
      "title": "Isolate the variable",
      "narration": "Subtract three from both sides.",
      "content": [
        { "type": "equation", "latex": "x + 3 = 7" },
        { "type": "annotation", "intent": "highlight", "target": "equation_left" }
      ]
    }
  ]
}
```

The exact schema should be versioned in API contracts before implementation. The important rule is that the lesson plan describes meaning; the renderer decides visual representation.

## 6. Internal Render Contracts

### 6.1 Render Intent

Render Intent is a renderer-neutral description of what should appear and why.

Examples:

- Show title.
- Emphasize equation transformation.
- Draw a relationship arrow between two expressions.
- Mark an incorrect approach with a cross mark.
- Mark a correct step with a check mark.
- Show a coordinate graph for a function.
- Show a geometry diagram with labeled angles.
- Show a table of values.

Decision: Render Intent avoids coupling lesson planning to a specific visual implementation.

### 6.2 Scene Graph

The Scene Graph is the renderer's deterministic visual model.

Scene graph nodes include:

- `FrameNode`
- `GroupNode`
- `TitleNode`
- `TextNode`
- `BoxNode`
- `EquationNode`
- `ArrowNode`
- `CrossMarkNode`
- `CheckMarkNode`
- `GraphNode`
- `GeometryNode`
- `TableNode`
- `HandwritingStrokeNode`
- `ImageNode`
- `AccessibilityDescriptionNode`

Every node must include:

- Stable node ID.
- Source lesson plan node ID.
- Bounding box or layout constraints.
- Style token references.
- Accessibility label or description where relevant.
- Animation timing metadata where relevant.

Decision: the scene graph enables SVG, raster, PDF, animation, and future video outputs from a single renderer-neutral representation.

## 7. Supported Visual Elements

### 7.1 Titles

Titles support lesson titles, step titles, section titles, and subheadings.

Requirements:

- Responsive sizing.
- Semantic heading levels.
- Theme-controlled typography.
- Optional handwriting style.
- Source mapping back to lesson step.

### 7.2 Boxes

Boxes support grouping, emphasis, examples, final answers, warnings, and teacher notes.

Requirements:

- Rounded or square styles.
- Fill, stroke, shadow, and emphasis variants.
- Auto-sizing around content.
- Nesting with layout constraints.

### 7.3 Equations

Equations are first-class mathematical elements.

Requirements:

- LaTeX or math-structured input from the lesson plan.
- Deterministic math layout.
- Step-by-step transformation support.
- Highlighting terms, sides, operators, substitutions, and cancellations.
- Accessibility text for screen readers.

### 7.4 Arrows

Arrows show relationships, movement, transformations, graph directions, and explanatory flow.

Requirements:

- Straight, curved, elbow, and annotation arrows.
- Attach to elements using anchor points, not absolute AI coordinates.
- Collision-aware routing where possible.
- Animation support for drawing arrows progressively.

### 7.5 Cross Marks and Check Marks

Marks show incorrect/correct reasoning, verified steps, misconceptions, and teacher-approved points.

Requirements:

- Semantic status labels.
- Color and shape variants for accessibility.
- Animation support.
- Source mapping to verification or pedagogy annotations.

### 7.6 Graphs

Graphs support coordinate planes, functions, points, inequalities, number lines, bar charts, and future statistical plots.

Requirements:

- Graph descriptions come from structured data, not pixels.
- Axes, labels, scales, gridlines, functions, points, and shaded regions are renderer-owned.
- Support algebraic functions and table-generated plots.
- Provide textual descriptions for accessibility.

### 7.7 Geometry

Geometry supports points, segments, rays, lines, polygons, circles, arcs, angles, congruence marks, parallel marks, measurements, and labels.

Requirements:

- Geometry descriptions are semantic.
- Layout may use constraints such as equal sides, right angles, parallel lines, and labeled vertices.
- Renderer owns diagram construction and label placement.
- Future support for dynamic geometry interactions should not change lesson plan semantics.

### 7.8 Tables

Tables support values, worked examples, comparisons, definitions, and step summaries.

Requirements:

- Header, body, footer, merged-cell, alignment, and emphasis support.
- Responsive layout and pagination.
- Accessible table semantics.
- Export consistency across SVG, PDF, raster, and animation targets.

### 7.9 Handwriting Styles

Handwriting styles are renderer themes, not AI drawing commands.

Requirements:

- Style tokens for handwriting font, stroke width, jitter, baseline variation, and animation pacing.
- Deterministic seeded variation so renders are reproducible.
- Accessibility fallback to clean printed text.
- Teacher/school style configuration support.

Decision: handwriting is a presentation layer. It must never compromise legibility, accessibility, or deterministic artifact generation.

## 8. Output Targets

| Target | Purpose | Rendering Strategy |
| --- | --- | --- |
| SVG | Scalable web whiteboard and source-of-truth vector export. | Serialize styled scene graph to semantic SVG. |
| PNG | Thumbnails, previews, low-complexity sharing. | Rasterize scene graph or SVG at target density. |
| JPEG/JPG | Compressed previews and broad compatibility. | Rasterize with background flattening and quality settings. |
| PDF | Printable lessons, teacher review packets, offline study. | Paginate scene graph and embed vector/raster assets. |
| Animated Whiteboard | Interactive playback of lesson steps. | Use scene graph with timing and animation plan. |
| Future Video | Generated video lesson artifacts. | Convert animation timeline and voice timing into video frames/audio muxing pipeline. |

Decision: target renderers are adapters. Adding future video must not require AI or Lesson Planner changes.

## 9. Animated Whiteboard Architecture

Animated whiteboard output is produced from a timeline, not from AI-authored drawing commands.

```text
Styled Scene Graph
  -> Animation Planner
  -> Timeline Segments
  -> Playback Manifest
  -> Client Whiteboard Player
```

Timeline segment examples:

- `write_title`
- `draw_box`
- `reveal_equation`
- `highlight_term`
- `draw_arrow`
- `place_check_mark`
- `place_cross_mark`
- `plot_graph`
- `construct_geometry`
- `reveal_table_row`

The animation planner owns pacing, order, easing, reduced-motion alternatives, and synchronization with voice timings.

## 10. Future Video Architecture

Future video should be downstream of the animated whiteboard pipeline.

```text
LessonPlan JSON
  -> Scene Graph
  -> Animation Timeline
  -> Voice Timing Map
  -> Frame Renderer
  -> Encoder
  -> Video Artifact
```

Design rules:

- Video is generated from the same structured scene graph and timeline used by animated whiteboard playback.
- Captions and transcripts come from Voice Engine artifacts.
- Video artifacts preserve source mapping to lesson steps.
- Video generation runs asynchronously in rendering workers.
- Teacher review can compare lesson plan, scene graph, animation timeline, and final video.

## 11. Renderer Extensibility

The rendering engine is extensible through registries.

| Registry | Purpose |
| --- | --- |
| Element Registry | Adds new scene node types such as probability trees, 3D solids, or manipulatives. |
| Layout Registry | Adds layout strategies for algebra, geometry, graphing, tables, and multi-panel lessons. |
| Style Registry | Adds themes, handwriting styles, school branding, accessibility modes. |
| Export Registry | Adds output targets such as SVG, PNG, JPEG, PDF, animation, video, or native scene formats. |
| Animation Registry | Adds animation behaviors for writing, drawing, highlighting, transforming, and revealing. |
| Accessibility Registry | Adds text alternatives, captions, screen-reader descriptions, and reduced-motion modes. |

Decision: registries allow extension without modifying core rendering orchestration.

## 12. Renderer Module Boundaries

```text
rendering-engine/
  contracts/              # LessonPlan render input, scene graph, timeline, artifact metadata.
  validation/             # Schema and compatibility validation.
  intent/                 # LessonPlan-to-render-intent conversion.
  layout/                 # Layout planning and pagination.
  scene-graph/            # Renderer-neutral visual graph.
  styles/                 # Theme, handwriting, accessibility style resolution.
  elements/               # Titles, boxes, equations, arrows, marks, graphs, geometry, tables.
  animation/              # Timeline and playback manifest planning.
  exporters/              # SVG, PNG, JPEG, PDF, animated whiteboard, future video adapters.
  accessibility/          # Semantic descriptions and reduced-motion alternatives.
  artifacts/              # Artifact metadata, checksums, storage references, source maps.
  tests/                  # Contract, layout, exporter, visual regression, accessibility tests.
```

## 13. Renderer Data Flow

### 13.1 Static Artifact Flow

```text
LessonPlan JSON
  -> Validate schema and renderer compatibility
  -> Build render intent tree
  -> Plan layout and pagination
  -> Build scene graph
  -> Resolve style and handwriting theme
  -> Export SVG/PDF or raster PNG/JPEG
  -> Store artifact and metadata
```

### 13.2 Animated Whiteboard Flow

```text
LessonPlan JSON
  -> Build scene graph
  -> Resolve style
  -> Create animation timeline
  -> Synchronize optional voice timings
  -> Export playback manifest
  -> Store manifest, assets, source map, and accessibility alternatives
```

### 13.3 Future Video Flow

```text
Animated whiteboard timeline
  -> Merge with voice audio and captions
  -> Render frames
  -> Encode video
  -> Store video artifact, captions, thumbnail, transcript, and source map
```

## 14. Accessibility Requirements

The renderer must support accessibility from the architecture level.

- Every visual artifact should have a semantic source map.
- Equations need accessible text alternatives.
- Graphs need textual summaries of axes, plotted items, and key points.
- Geometry needs descriptions of shapes, labels, and relationships.
- Tables need semantic row/column descriptions.
- Animations need reduced-motion alternatives.
- Color-coded check/cross status must also use shape and labels.
- Handwriting styles must have legibility controls and printed-text fallback.

Decision: accessibility cannot be bolted on after rendering. It must be part of scene graph and export design.

## 15. Versioning and Reproducibility

Every render artifact must record:

- Lesson plan ID and version.
- Renderer version.
- Scene graph schema version.
- Export target and settings.
- Theme and handwriting style version.
- Input checksums.
- Output checksums.
- Source map from artifact elements to lesson plan nodes.
- Voice timing version when synchronized.

Decision: reproducibility is required for teacher review, debugging, analytics, compliance, and dataset/training lineage.

## 16. Scaling Model

- Rendering jobs run asynchronously through a job queue.
- SVG and animated manifests can be generated by general CPU workers.
- PNG/JPEG rasterization and PDF generation can use dedicated render workers.
- Future video encoding uses isolated media workers with separate autoscaling.
- Artifact storage uses object storage and CDN distribution.
- Render jobs are idempotent using lesson plan version, renderer version, target, theme, and export settings.
- Large lessons are split into frames/pages/scenes to avoid oversized artifacts.

## 17. Testing Strategy

Required renderer tests:

- Schema compatibility tests for renderable LessonPlan JSON.
- Render intent tests for supported educational elements.
- Layout tests for titles, boxes, equations, arrows, marks, graphs, geometry, and tables.
- Exporter contract tests for SVG, PNG, JPEG/JPG, PDF, animated whiteboard, and future video manifests.
- Visual regression tests for representative lessons.
- Accessibility tests for semantic descriptions and reduced-motion alternatives.
- Determinism tests proving identical inputs create identical artifact metadata and stable output where expected.
- Performance tests for large lessons and high-volume rendering queues.

## 18. Implementation Guardrails

When implementation begins:

1. Define `LessonPlan` render schemas before exporters.
2. Define scene graph contracts before SVG or raster output.
3. Build SVG export first because it preserves vector semantics and source mapping.
4. Add PNG/JPEG rasterization from the same scene graph or SVG source.
5. Add PDF pagination after static SVG output is stable.
6. Add animated whiteboard from timeline metadata, not AI commands.
7. Add future video from animation timeline and voice artifacts.
8. Never allow AI-generated raw SVG, canvas commands, CSS, or video instructions.
9. Never let frontend whiteboard clients invent lesson content; they only play render artifacts.
10. Require source maps, artifact metadata, and accessibility output for every target.
