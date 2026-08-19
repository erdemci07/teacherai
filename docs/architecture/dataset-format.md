# TeacherAI Dataset Format Architecture

## 1. Purpose

TeacherAI datasets must support teacher review, student learning analytics, retrieval, evaluation, and future fine-tuning. The dataset format must preserve educational quality, source lineage, privacy policy, and artifact versions.

This document is architecture only. It defines dataset structure and JSON examples. It does not implement dataset pipelines, training jobs, storage code, validation code, or provider-specific fine-tuning adapters.

## 2. Dataset Design Principles

- Teacher-approved content is the highest-trust training signal.
- Every dataset example must be versioned, auditable, and traceable to source artifacts.
- Question images, OCR output, lesson plans, teacher explanations, solutions, teacher corrections, student mistakes, metadata, difficulty, and learning objectives must be represented as structured fields.
- Raw student personally identifiable information must not be included in training exports.
- Fine-tuning exports must be derived from canonical dataset examples, not directly from raw production records.
- Dataset examples should support multiple training tasks: vision extraction, OCR correction, question classification, pedagogy planning, lesson planning, math verification, teacher feedback prediction, misconception detection, and AI tutoring responses.
- Dataset schemas must be versioned so future models can reproduce training runs.

## 3. Dataset Package Structure

A dataset release is a versioned package, not a single file.

```text
dataset_release/
  manifest.json
  examples/
    example_000001.json
    example_000002.json
  assets/
    question-images/
    teacher-uploads/
    rendered-whiteboards/
  splits/
    train.jsonl
    validation.jsonl
    test.jsonl
    evaluation.jsonl
  exports/
    fine-tuning/
    retrieval/
    evaluation/
  lineage/
    source-artifacts.jsonl
    teacher-review-events.jsonl
  privacy/
    consent-report.json
    redaction-report.json
```

Decision: packaging datasets with manifests, examples, assets, splits, exports, lineage, and privacy reports makes training reproducible and auditable.

## 4. Top-Level Dataset Manifest

The manifest describes the dataset release.

```json
{
  "dataset_id": "teacherai_math_v1",
  "dataset_version": "2026.07.26",
  "schema_version": "1.0.0",
  "created_at": "2026-07-26T00:00:00Z",
  "created_by": "dataset_engine",
  "status": "approved_for_evaluation",
  "description": "Teacher-approved algebra lesson dataset for lesson planning and verification evaluation.",
  "source_filters": {
    "teacher_approved_only": true,
    "minimum_quality_score": 0.92,
    "allowed_grade_bands": ["middle_school", "high_school"],
    "allowed_subjects": ["mathematics"],
    "exclude_personal_data": true
  },
  "counts": {
    "examples": 125000,
    "question_images": 83000,
    "teacher_explanations": 118000,
    "student_mistake_patterns": 41000
  },
  "splits": {
    "train": "splits/train.jsonl",
    "validation": "splits/validation.jsonl",
    "test": "splits/test.jsonl",
    "evaluation": "splits/evaluation.jsonl"
  },
  "privacy": {
    "consent_report": "privacy/consent-report.json",
    "redaction_report": "privacy/redaction-report.json",
    "contains_student_pii": false
  },
  "lineage": {
    "source_artifacts": "lineage/source-artifacts.jsonl",
    "teacher_review_events": "lineage/teacher-review-events.jsonl"
  }
}
```

## 5. Canonical Dataset Example Schema

A canonical example is the source record from which task-specific training exports are generated.

```json
{
  "example_id": "ex_algebra_000001",
  "schema_version": "1.0.0",
  "dataset_version": "2026.07.26",
  "status": "teacher_approved",
  "source": {
    "tenant_id_hash": "tenant_hash_8f21",
    "classroom_id_hash": "class_hash_239a",
    "lesson_plan_id": "lesson_01HZY",
    "lesson_plan_version": "3",
    "question_submission_id": "submission_01HX1",
    "teacher_review_id": "review_01J2A",
    "created_at": "2026-07-10T14:22:11Z",
    "approved_at": "2026-07-11T09:02:44Z"
  },
  "question": {
    "canonical_text": "Solve for x: 2x + 3 = 11.",
    "question_images": [
      {
        "asset_id": "asset_question_001",
        "uri": "assets/question-images/asset_question_001.png",
        "mime_type": "image/png",
        "width": 1280,
        "height": 720,
        "sha256": "examplechecksum001",
        "redaction_status": "redacted",
        "source_regions": [
          {
            "region_id": "r1",
            "label": "equation",
            "bbox": { "x": 210, "y": 180, "width": 420, "height": 90 }
          }
        ]
      }
    ],
    "ocr": {
      "raw_text": "Solve for x: 2x + 3 = 11",
      "normalized_text": "Solve for x: 2x + 3 = 11.",
      "confidence": 0.98,
      "engine": "vision_engine_v1",
      "regions": [
        {
          "region_id": "r1",
          "text": "2x + 3 = 11",
          "confidence": 0.99,
          "bbox": { "x": 210, "y": 180, "width": 420, "height": 90 }
        }
      ],
      "teacher_corrections": []
    }
  },
  "metadata": {
    "subject": "mathematics",
    "topic": "algebra",
    "subtopic": "linear_equations_one_variable",
    "grade_band": "middle_school",
    "curriculum_standards": ["CCSS.Math.Content.8.EE.C.7"],
    "language": "en",
    "locale": "en-US",
    "difficulty": {
      "label": "introductory",
      "score": 0.28,
      "rationale": "One-variable two-step equation with integer operations."
    },
    "learning_objectives": [
      {
        "objective_id": "lo_linear_equations_001",
        "description": "Solve two-step linear equations in one variable using inverse operations.",
        "mastery_level": "developing"
      }
    ],
    "prerequisites": ["integer_arithmetic", "inverse_operations"],
    "tags": ["two_step_equation", "inverse_operations", "middle_school_algebra"]
  },
  "solution": {
    "final_answer": "x = 4",
    "steps": [
      {
        "step_id": "sol_1",
        "statement": "2x + 3 = 11",
        "explanation": "Start with the original equation.",
        "latex": "2x + 3 = 11"
      },
      {
        "step_id": "sol_2",
        "statement": "2x = 8",
        "explanation": "Subtract 3 from both sides.",
        "latex": "2x = 8"
      },
      {
        "step_id": "sol_3",
        "statement": "x = 4",
        "explanation": "Divide both sides by 2.",
        "latex": "x = 4"
      }
    ],
    "verification": {
      "status": "verified",
      "verified_by": "math_verification_engine_v1",
      "confidence": 1.0,
      "checks": [
        { "check_id": "chk_1", "type": "algebraic_equivalence", "status": "passed" },
        { "check_id": "chk_2", "type": "substitution", "status": "passed" }
      ]
    }
  },
  "lesson_plan": {
    "lesson_plan_id": "lesson_01HZY",
    "version": "3",
    "title": "Solving a Two-Step Equation",
    "teaching_strategy": "guided_inverse_operations",
    "steps": [
      {
        "step_id": "lesson_step_1",
        "title": "Understand the goal",
        "teacher_narration": "We want x by itself, so we undo the operations around x in reverse order.",
        "math_expression": "2x + 3 = 11",
        "visual_intents": [
          { "type": "title", "text": "Goal: isolate x" },
          { "type": "box", "purpose": "highlight_goal", "target": "x" }
        ],
        "checks_for_understanding": ["What does it mean to isolate x?"]
      },
      {
        "step_id": "lesson_step_2",
        "title": "Undo addition",
        "teacher_narration": "Subtract 3 from both sides so the equation stays balanced.",
        "math_expression": "2x + 3 - 3 = 11 - 3",
        "visual_intents": [
          { "type": "arrow", "from": "+3", "to": "-3", "meaning": "inverse_operation" },
          { "type": "check_mark", "target": "balanced_operation" }
        ],
        "checks_for_understanding": ["Why do we subtract 3 from both sides?"]
      }
    ],
    "common_misconceptions": [
      "Subtracting 3 from only one side.",
      "Dividing 11 by 2 before removing the +3."
    ]
  },
  "teacher_explanation": {
    "teacher_id_hash": "teacher_hash_91ab",
    "style_id": "style_guided_questions_v1",
    "explanation_text": "First remove the constant term by subtracting 3 from both sides. Then divide by the coefficient of x.",
    "approved_lesson_step_ids": ["lesson_step_1", "lesson_step_2"],
    "quality_rating": 5,
    "review_notes": "Clear and age-appropriate. Keep the balance metaphor."
  },
  "teacher_corrections": [
    {
      "correction_id": "corr_001",
      "target_type": "lesson_step",
      "target_id": "lesson_step_2",
      "before": "Move 3 to the other side.",
      "after": "Subtract 3 from both sides so the equation stays balanced.",
      "reason": "Avoids teaching an informal shortcut before conceptual understanding.",
      "correction_label": "pedagogy_clarity"
    }
  ],
  "student_mistakes": [
    {
      "mistake_id": "mistake_001",
      "anonymized_student_group": "cohort_hash_a1",
      "attempt_text": "2x = 11 - 3, x = 8",
      "normalized_error": "forgot_to_divide_by_coefficient",
      "misconception": "Student removed the constant but did not undo multiplication by 2.",
      "frequency": 0.18,
      "recommended_feedback": "You correctly subtracted 3. What operation is still applied to x?"
    }
  ],
  "training": {
    "eligible_tasks": [
      "question_classification",
      "lesson_planning",
      "pedagogy_strategy",
      "math_verification_evaluation",
      "teacher_feedback_modeling",
      "student_misconception_detection"
    ],
    "excluded_tasks": [],
    "quality_score": 0.97,
    "safety_status": "approved",
    "privacy_status": "redacted",
    "fine_tuning_weight": 1.0
  }
}
```

## 6. Field Responsibilities

| Field | Purpose | Training Value |
| --- | --- | --- |
| `question.question_images` | Stores redacted question-image asset references and regions. | Vision, OCR, multimodal understanding, diagram recognition. |
| `question.ocr` | Stores raw OCR, normalized OCR, confidence, regions, and OCR corrections. | OCR correction, vision evaluation, multimodal grounding. |
| `metadata.difficulty` | Stores difficulty label, score, and rationale. | Difficulty prediction and curriculum sequencing. |
| `metadata.learning_objectives` | Stores target learning goals. | Lesson planning, personalization, evaluation grouping. |
| `solution` | Stores verified answer and step-by-step solution. | Math reasoning evaluation and verifier benchmarking. |
| `lesson_plan` | Stores structured teacher-reviewable instructional plan. | Lesson planning fine-tuning and renderer input generation. |
| `teacher_explanation` | Stores teacher-authored or teacher-approved explanation. | High-quality explanation modeling. |
| `teacher_corrections` | Stores before/after corrections with labels and reasons. | Preference modeling, error reduction, pedagogy improvement. |
| `student_mistakes` | Stores anonymized mistake patterns and feedback. | Misconception detection and adaptive tutoring. |
| `training` | Stores task eligibility, safety, privacy, quality, and weighting. | Controls fine-tuning, evaluation, and retrieval export. |

## 7. Teacher Explanation Format

Teacher explanations must be structured enough for training and review.

```json
{
  "teacher_explanation_id": "texp_001",
  "teacher_id_hash": "teacher_hash_91ab",
  "lesson_plan_id": "lesson_01HZY",
  "target_step_id": "lesson_step_2",
  "explanation_type": "conceptual_guidance",
  "text": "Subtract 3 from both sides because equations stay true only when we do the same operation to both sides.",
  "tone": "encouraging",
  "pedagogy_tags": ["balance_model", "inverse_operations", "conceptual_before_shortcut"],
  "approved": true,
  "quality_rating": 5
}
```

## 8. Teacher Correction Format

Teacher corrections preserve the difference between AI output and teacher-approved instruction.

```json
{
  "correction_id": "corr_482",
  "review_id": "review_01J2A",
  "target": {
    "artifact_type": "lesson_plan",
    "artifact_id": "lesson_01HZY",
    "artifact_version": "2",
    "path": "steps[1].teacher_narration"
  },
  "before": "Move the 3 over and it becomes negative.",
  "after": "Subtract 3 from both sides so the equation stays balanced.",
  "reason": "The original wording encourages memorized symbol movement instead of conceptual inverse operations.",
  "labels": ["conceptual_accuracy", "pedagogy_clarity"],
  "severity": "medium",
  "approved_for_training": true
}
```

## 9. Student Mistake Format

Student mistakes must be anonymized and aggregated when used for training.

```json
{
  "mistake_pattern_id": "mp_103",
  "source_lesson_plan_id": "lesson_01HZY",
  "anonymization_level": "cohort_aggregated",
  "attempt": {
    "text": "x = 8",
    "latex": "x = 8",
    "step_context": "after_subtracting_constant"
  },
  "classification": {
    "error_type": "incomplete_inverse_operations",
    "misconception": "Student did not divide by the coefficient after isolating 2x.",
    "difficulty_link": "introductory_two_step_equations"
  },
  "frequency": {
    "count": 42,
    "cohort_size": 230,
    "rate": 0.183
  },
  "recommended_feedback": "You got to 2x = 8. What should we do to undo multiplying by 2?",
  "approved_for_training": true
}
```

## 10. OCR and Vision Training Example

A task-specific export can be generated from canonical examples for OCR/vision training.

```json
{
  "task": "vision_ocr_extraction",
  "schema_version": "1.0.0",
  "input": {
    "image_uri": "assets/question-images/asset_question_001.png",
    "regions": [
      { "region_id": "r1", "bbox": { "x": 210, "y": 180, "width": 420, "height": 90 } }
    ]
  },
  "target": {
    "normalized_text": "Solve for x: 2x + 3 = 11.",
    "equations": [
      { "latex": "2x + 3 = 11", "region_id": "r1" }
    ]
  },
  "metadata": {
    "example_id": "ex_algebra_000001",
    "difficulty": "introductory",
    "topic": "algebra",
    "privacy_status": "redacted"
  }
}
```

## 11. Lesson Planning Fine-Tuning Example

A future fine-tuning export should transform canonical examples into task-specific supervised records.

```json
{
  "task": "lesson_planning",
  "schema_version": "1.0.0",
  "input": {
    "question": "Solve for x: 2x + 3 = 11.",
    "topic": "algebra",
    "subtopic": "linear_equations_one_variable",
    "difficulty": "introductory",
    "learning_objectives": [
      "Solve two-step linear equations in one variable using inverse operations."
    ],
    "pedagogy_plan": {
      "strategy": "guided_inverse_operations",
      "misconceptions_to_address": [
        "Subtracting from one side only.",
        "Forgetting to divide by the coefficient."
      ]
    }
  },
  "target": {
    "lesson_plan": {
      "title": "Solving a Two-Step Equation",
      "steps": [
        {
          "title": "Understand the goal",
          "teacher_narration": "We want x by itself, so we undo the operations around x in reverse order.",
          "math_expression": "2x + 3 = 11"
        },
        {
          "title": "Undo addition",
          "teacher_narration": "Subtract 3 from both sides so the equation stays balanced.",
          "math_expression": "2x + 3 - 3 = 11 - 3"
        }
      ]
    }
  },
  "training_metadata": {
    "source_example_id": "ex_algebra_000001",
    "teacher_approved": true,
    "quality_score": 0.97,
    "fine_tuning_weight": 1.0
  }
}
```

## 12. Teacher Correction Preference Example

Teacher corrections support preference tuning and evaluator training.

```json
{
  "task": "teacher_preference_modeling",
  "schema_version": "1.0.0",
  "input": {
    "question": "Solve for x: 2x + 3 = 11.",
    "lesson_step_context": "Undo addition before division.",
    "candidate_explanation": "Move the 3 over and it becomes negative."
  },
  "preferred_output": "Subtract 3 from both sides so the equation stays balanced.",
  "rejected_output": "Move the 3 over and it becomes negative.",
  "preference_reason": "The preferred output teaches conceptual inverse operations instead of a shortcut.",
  "labels": ["conceptual_accuracy", "pedagogy_clarity"],
  "training_metadata": {
    "source_correction_id": "corr_482",
    "teacher_approved": true,
    "severity": "medium"
  }
}
```

## 13. Student Mistake Training Example

Student mistake records support misconception detection and adaptive feedback.

```json
{
  "task": "student_misconception_detection",
  "schema_version": "1.0.0",
  "input": {
    "question": "Solve for x: 2x + 3 = 11.",
    "current_step": "2x = 8",
    "student_answer": "x = 8"
  },
  "target": {
    "error_type": "incomplete_inverse_operations",
    "misconception": "Student forgot to divide both sides by 2.",
    "feedback": "You correctly subtracted 3. Now 2 is multiplying x, so divide both sides by 2."
  },
  "training_metadata": {
    "source_mistake_pattern_id": "mp_103",
    "anonymization_level": "cohort_aggregated",
    "approved_for_training": true
  }
}
```

## 14. Math Verification Evaluation Example

Verification datasets help evaluate whether models and symbolic systems catch invalid math.

```json
{
  "task": "math_verification_evaluation",
  "schema_version": "1.0.0",
  "input": {
    "question": "Solve for x: 2x + 3 = 11.",
    "candidate_steps": [
      "2x + 3 = 11",
      "2x = 11 - 3",
      "x = 8"
    ]
  },
  "target": {
    "status": "incorrect",
    "first_error_step_index": 2,
    "error_type": "forgot_to_divide_by_coefficient",
    "corrected_step": "x = 4"
  },
  "metadata": {
    "difficulty": "introductory",
    "topic": "algebra",
    "source_example_id": "ex_algebra_000001"
  }
}
```

## 15. Dataset Quality and Safety Gates

Before an example can be used for future fine-tuning, it must pass gates:

1. Teacher approval or trusted expert source approval.
2. Math verification success or documented verification exception.
3. Privacy redaction and consent policy validation.
4. Dataset deduplication.
5. Curriculum and learning-objective tagging.
6. Difficulty validation.
7. Safety and age-appropriateness review.
8. Source lineage completeness.
9. License and usage-right validation.
10. Training-task eligibility assignment.

## 16. Fine-Tuning Export Rules

- Export only task-specific records derived from canonical examples.
- Include source IDs, schema version, dataset version, quality score, and privacy status in every record.
- Do not export raw student identifiers, raw classroom identifiers, or unredacted images.
- Keep train/validation/test/evaluation splits stable for reproducibility.
- Prevent leakage by ensuring near-duplicate questions do not appear across train and test splits.
- Preserve teacher correction pairs for preference tuning separately from supervised lesson-plan examples.
- Preserve student mistake patterns as anonymized misconception examples, not raw chat logs.

## 17. Versioning and Lineage

Every dataset example must track:

- Dataset schema version.
- Dataset release version.
- Source question submission ID.
- Source lesson plan ID and version.
- Source teacher review ID.
- Source verification report ID.
- Source renderer artifact IDs where used.
- Source model/provider metadata where policy allows.
- Privacy/redaction status.
- Training eligibility and exclusion reasons.

Decision: future model quality depends on being able to reproduce exactly what data trained or evaluated a model.
