// Üretilen dosya · python -m scripts.education_contracts

export type Alternative = {
  id: string;
  text: string;
  latex?: string | null;
  origin: "vision" | "vision_recheck" | "deterministic";
};

export type AnswerChoice = {
  id: string;
  order: number;
  label?: string | null;
  label_origin: "printed" | "none";
  content?: string | null;
  kind: "expression" | "number" | "text" | "statement_combination" | "visual" | "empty";
  canonical?: string | null;
  latex?: string | null;
  statement_refs?: Array<string>;
};

export type BoardPanel = {
  blocks: Array<string>;
};

export type CalculationBlock = {
  id: string;
  relates_to?: Array<string>;
  references?: Array<Reference>;
  kind: "calculation";
  expression: string;
  result: MathAnswer | NumberAnswer | QuantityAnswer | ChoiceAnswer | TextAnswer | TableAnswer;
};

export type Capabilities = {
  representable: boolean;
  recognition: boolean;
  generation: boolean;
  verification: "bounded_math" | "unsupported";
  practice: boolean;
  rendering: boolean;
};

export type ChoiceAnswer = {
  kind: "choice";
  choices: Array<string>;
  selected: number;
};

export type ChoiceMatch = {
  status: "matched" | "multiple_equivalent" | "no_match" | "choice_dependent" | "unsupported";
  value_origin: "independent" | "provider" | "none";
  value?: string | null;
  provider_label?: string | null;
  matched_labels?: Array<string>;
};

export type ClarificationRecord = {
  uncertainty_id: string;
  selection: string;
  from_revision: number;
};

export type ClarificationRequest = {
  expected_revision: number;
  uncertainty_id: string;
  selection: string;
};

export type ContextValue = {
  value: string;
  origin: "declared" | "profile" | "inferred";
};

export type Correction = {
  element: string;
  original: string;
  corrected: string;
  uncertainty_id: string;
  from_revision: number;
};

export type EducationContext = {
  subject: Subject;
  language: string;
  system?: ContextValue | null;
  stage?: ContextValue | null;
  grade?: Grade | null;
  academic_year?: ContextValue | null;
  exam?: ContextValue | null;
  source_exam?: ContextValue | null;
  references?: Array<Reference>;
};

export type EducationalDraft = {
  activity: "question_solution" | "topic_lesson" | "worked_example" | "guided_practice" | "independent_practice" | "diagnostic_question" | "review";
  objectives: Array<string>;
  references?: Array<Reference>;
  blocks: Array<ProseBlock | ExpressionBlock | CalculationBlock | ExampleBlock | TableBlock | VisualBlock>;
  answer?: MathAnswer | NumberAnswer | QuantityAnswer | ChoiceAnswer | TextAnswer | TableAnswer | null;
  takeaway: string;
};

export type ExampleBlock = {
  id: string;
  relates_to?: Array<string>;
  references?: Array<Reference>;
  kind: "worked_example";
  prompt: string;
  explanation: string;
  answer: MathAnswer | NumberAnswer | QuantityAnswer | ChoiceAnswer | TextAnswer | TableAnswer;
};

export type ExpressionBlock = {
  id: string;
  relates_to?: Array<string>;
  references?: Array<Reference>;
  kind: "expression";
  latex: string;
};

export type Grade = {
  value: number;
  origin: "declared" | "profile";
};

export type IntegrityCheck = {
  code: "clean" | "normalized_notation" | "decimal_comma_resolved" | "mixed_number_convention" | "unsupported_notation" | "invalid_structure" | "latex_exponent_scope" | "decimal_ambiguity" | "duplicate_expression" | "duplicate_choice_labels" | "missing_choice_label" | "unlabeled_choices" | "equivalent_choice_values" | "single_choice" | "missing_statements" | "duplicate_statement_labels" | "polarity_conflict" | "negation_present" | "missing_question_text" | "provider_uncertainty_material" | "provider_uncertainty_noncritical" | "equivalent_alternatives" | "alternative_not_applicable" | "legacy_uncertainty" | "multiple_questions" | "target_question_unclear" | "invalid_region_omitted" | "essential_visual_without_facts" | "recheck_confirmed" | "recheck_equivalent" | "recheck_disagreement" | "recheck_illegible" | "recheck_unavailable" | "recheck_budget_exhausted" | "student_selected" | "student_rejected" | "unsupported_subject" | "not_a_question" | "unreadable_source" | "incomplete_source";
  impact: "noncritical" | "material" | "fatal";
  element?: string | null;
};

export type IntegrityReport = {
  schema_version?: "1.0.0";
  revision: number;
  revision_origin: "vision" | "vision_recheck" | "student_clarification" | "legacy";
  decision: "ready" | "ready_with_noncritical_uncertainty" | "targeted_recheck" | "clarification_required" | "retake_required" | "incomplete" | "unreadable" | "no_question" | "unsupported_subject";
  recovery: "none" | "choose_alternative" | "retake" | "crop";
  subject: Subject;
  subject_origin: "canonical_label" | "vision_math_gate" | "unknown";
  intent: QuestionIntent;
  expressions?: Array<SourceExpression>;
  choices?: Array<AnswerChoice>;
  uncertainties?: Array<SourceUncertainty>;
  checks?: Array<IntegrityCheck>;
  image?: Array<"small_image" | "downscaled" | "low_contrast" | "underexposed" | "overexposed" | "possible_glare" | "possible_blur" | "possible_clipping" | "uneven_lighting" | "transparency_flattened" | "orientation_corrected" | "metadata_removed">;
  rechecks_used: number;
  recheck_limit: number;
  corrections?: Array<Correction>;
  clarifications?: Array<ClarificationRecord>;
};

export type IntentMarker = {
  marker: string;
  category: "negation" | "polarity" | "extremum" | "quantifier" | "possibility" | "count" | "operation";
};

export type LessonPlanV2 = {
  schema: SchemaIdentity;
  lesson_id: string;
  source_id: string;
  context: EducationContext;
  source_revision?: number | null;
  source_decision?: "ready" | "ready_with_noncritical_uncertainty" | "targeted_recheck" | "clarification_required" | "retake_required" | "incomplete" | "unreadable" | "no_question" | "unsupported_subject" | null;
  content: EducationalDraft;
  provenance: Provenance;
  verification: VerificationReport;
};

export type LessonView = {
  lesson: LessonPlanV2;
  panels: Array<BoardPanel>;
  created_at: string;
};

export type MathAnswer = {
  kind: "math";
  expressions: Array<string>;
  description: string;
};

export type NormalizationNote = {
  rule: "unicode_minus" | "dash_as_minus" | "multiplication_sign" | "division_sign" | "superscript_digit" | "latex_spacing" | "latex_fraction_variant" | "decimal_comma" | "whitespace" | "unicode_relation" | "unicode_root" | "unicode_constant";
  original: string;
  normalized: string;
};

export type NumberAnswer = {
  kind: "number";
  value: number;
};

export type ProseBlock = {
  id: string;
  relates_to?: Array<string>;
  references?: Array<Reference>;
  title?: string | null;
  kind: "explanation" | "definition" | "warning" | "hint" | "checkpoint" | "result" | "summary";
  text: string;
};

export type Provenance = {
  provider: string;
  model: string;
};

export type Quantity = {
  value: number;
  unit: string;
  label?: string | null;
};

export type QuantityAnswer = {
  kind: "quantity";
  quantity: Quantity;
};

export type QuestionIntent = {
  kind: "find_value" | "find_variable" | "simplify" | "compare" | "identify_true" | "identify_false" | "find_all_valid" | "interpret_graph" | "interpret_table" | "identify_shape" | "determine_range" | "find_minimum" | "find_maximum" | "determine_possible" | "determine_impossible" | "count" | "unknown";
  markers?: Array<IntentMarker>;
  statement_labels?: Array<string>;
  choice_dependent: boolean;
  answer_strategy: "solve_first_hidden" | "derive_then_select" | "choice_dependent" | "open";
};

export type QuestionUnderstanding = {
  source_id: string;
  status: "educational" | "unreadable" | "incomplete" | "non_educational" | "unsupported_subject" | "unresolved_subject";
  context: EducationContext;
  secondary_subjects?: Array<Subject>;
  question?: string | null;
  requested?: string | null;
  facts?: Array<string>;
  choices?: Array<string>;
  expressions?: Array<string>;
  quantities?: Array<Quantity>;
  visuals?: Array<string>;
  tables?: Array<Table>;
  uncertainties?: Array<string>;
  revision?: number | null;
  integrity?: IntegrityReport | null;
};

export type Reference = {
  kind: "concept" | "outcome" | "method" | "prerequisite" | "curriculum" | "source" | "learner";
  key: string;
  review?: "unreviewed";
};

export type SchemaIdentity = {
  name: "teacherai.lesson_plan";
  version: "2.0.0" | "2.1.0";
};

export type SourceExpression = {
  id: string;
  index: number;
  role: "given" | "requested" | "answer_choice" | "premise" | "unknown";
  source: string;
  status: "parsed" | "unsupported" | "invalid";
  canonical?: string | null;
  latex?: string | null;
  reason?: string | null;
  normalizations?: Array<NormalizationNote>;
};

export type SourceRegion = {
  kind: "question" | "expression" | "choices" | "diagram" | "graph" | "table" | "annotation" | "other_question";
  x0: number;
  y0: number;
  x1: number;
  y1: number;
};

export type SourceUncertainty = {
  id: string;
  category: "symbol" | "sign" | "grouping" | "radical_scope" | "fraction_scope" | "exponent_scope" | "subscript" | "decimal" | "text" | "negation" | "answer_choice" | "diagram" | "graph" | "table" | "quantity" | "unit" | "source_selection";
  element?: string | null;
  recognized?: string | null;
  alternatives?: Array<Alternative>;
  impact: "noncritical" | "material" | "fatal";
  resolution: "unresolved" | "resolved_locally" | "confirmed_by_recheck" | "resolved_by_student" | "rejected_by_student";
  origin: "vision" | "vision_recheck" | "deterministic" | "legacy_text" | "student";
  evidence?: Array<"clean" | "normalized_notation" | "decimal_comma_resolved" | "mixed_number_convention" | "unsupported_notation" | "invalid_structure" | "latex_exponent_scope" | "decimal_ambiguity" | "duplicate_expression" | "duplicate_choice_labels" | "missing_choice_label" | "unlabeled_choices" | "equivalent_choice_values" | "single_choice" | "missing_statements" | "duplicate_statement_labels" | "polarity_conflict" | "negation_present" | "missing_question_text" | "provider_uncertainty_material" | "provider_uncertainty_noncritical" | "equivalent_alternatives" | "alternative_not_applicable" | "legacy_uncertainty" | "multiple_questions" | "target_question_unclear" | "invalid_region_omitted" | "essential_visual_without_facts" | "recheck_confirmed" | "recheck_equivalent" | "recheck_disagreement" | "recheck_illegible" | "recheck_unavailable" | "recheck_budget_exhausted" | "student_selected" | "student_rejected" | "unsupported_subject" | "not_a_question" | "unreadable_source" | "incomplete_source">;
  region?: SourceRegion | null;
  note?: string | null;
};

export type Subject = "mathematics" | "geometry" | "physics" | "chemistry" | "biology" | "science" | "unknown";

export type Table = {
  headers: Array<string>;
  rows: Array<Array<string>>;
};

export type TableAnswer = {
  kind: "table";
  table: Table;
};

export type TableBlock = {
  id: string;
  relates_to?: Array<string>;
  references?: Array<Reference>;
  kind: "table";
  table: Table;
};

export type TextAnswer = {
  kind: "text";
  text: string;
};

export type VerificationReport = {
  structural: "passed";
  scientific: "passed" | "failed" | "partially_checked" | "unsupported" | "not_checked" | "not_applicable";
  calculation: "passed" | "failed" | "partially_checked" | "unsupported" | "not_checked" | "not_applicable";
  source_consistency: "passed" | "failed" | "partially_checked" | "unsupported" | "not_checked" | "not_applicable";
  curriculum: "not_checked";
  method: "not_checked";
  pedagogy: "not_checked";
  engine?: string | null;
  checked_claims?: Array<string>;
};

export type VisualBlock = {
  id: string;
  relates_to?: Array<string>;
  references?: Array<Reference>;
  kind: "visual";
  visual_type: "number_line" | "source_figure" | "unsupported";
  description: string;
  positions?: Array<number>;
};
