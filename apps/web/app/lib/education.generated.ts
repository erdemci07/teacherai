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

export type AnswerTarget = {
  kind: "variable_value" | "expression_value" | "sum" | "difference" | "product" | "ratio" | "solution_count" | "root_sum" | "root_product" | "solution_set" | "interval" | "minimum" | "maximum" | "comparison" | "proposition_truth" | "statement_combination" | "physical_quantity" | "chemical_quantity" | "scientific_interpretation" | "textual_explanation" | "unresolved";
  origin: "deterministic" | "legacy_default" | "unresolved";
  variable?: string | null;
  expression?: string | null;
  latex?: string | null;
  source?: string | null;
  integer_only?: boolean;
  markers?: Array<string>;
};

export type Axis = {
  name: string;
  unit?: UnitSpec | null;
  scale: "explicit_linear" | "explicit_nonlinear" | "unknown";
  origin?: "explicit" | "unknown";
};

export type BlockCheck = {
  id: string;
  scope: "block" | "answer" | "lesson";
  target?: string | null;
  mapping?: "mapped" | "unmapped";
  dimension: "calculation" | "transformation" | "domain" | "answer_target" | "answer_choice" | "source_consistency" | "units" | "stoichiometry" | "evidence_consistency" | "scientific" | "curriculum" | "method" | "pedagogy";
  verifier: "mathai" | "integrity" | "units" | "chemistry" | "evidence" | "registry" | "none";
  outcome: "passed" | "failed" | "partially_checked" | "unsupported" | "not_checked" | "not_applicable";
  reason: string;
  evidence?: Array<EvidenceRef>;
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

export type CircuitElement = {
  id: string;
  kind: "resistor" | "bulb" | "battery" | "switch" | "ammeter" | "voltmeter" | "wire";
  nodes: Array<string>;
  value?: string | null;
  internal_resistance?: string | null;
  positive_node?: string | null;
  closed?: boolean | null;
  connection_certain?: boolean;
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
};

export type CircuitModel = {
  nodes: Array<string>;
  elements: Array<CircuitElement>;
};

export type Claim = {
  id: string;
  text: string;
  x?: string | null;
  y: string;
  relation: "increases" | "decreases" | "no_change" | "differs" | "equal";
  causal?: boolean;
  groups?: Array<string>;
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
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

export type Collision = {
  id: string;
  bodies: Array<string>;
  kind?: "elastic" | "perfectly_inelastic" | "inelastic" | "explosion" | "unknown";
  velocities_before?: Array<string | null>;
  velocities_after?: Array<string | null>;
  external_impulse?: "none_stated" | "negligible_assumed" | "present" | "unknown";
};

export type Condition = {
  variable: string;
  value: string;
};

export type ConditionClaim = {
  condition: string;
  state: "satisfied" | "violated" | "unknown";
  basis: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
};

export type ContextAttempt = {
  purpose: "initial" | "verification_correction" | "method_correction";
  levels: Array<"normal" | "emergency" | "unknown">;
  accepted: boolean;
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

export type CurriculumRegistry = {
  schema_name: "teacherai.curriculum_registry";
  version: "1.0.0";
  program_note: string;
  outcomes?: Array<Outcome>;
  policies?: Array<MethodPolicy>;
};

export type CurriculumResolution = {
  status: "resolved" | "ambiguous" | "unresolved";
  subject: Subject;
  academic_year: string;
  academic_year_origin: "declared" | "server_clock";
  grade?: number | null;
  learner_status?: "student" | "graduate" | null;
  exam?: "LGS" | "TYT" | "AYT" | null;
  exams?: Array<"LGS" | "TYT" | "AYT">;
  exam_scope_ids?: Array<string>;
  track?: "general" | "science_high_school" | "basic_level" | null;
  program_ids?: Array<string>;
  candidate_program_ids?: Array<string>;
  exam_scope_id?: string | null;
  reasons?: Array<"grade_unknown" | "subject_unsupported" | "schedule_unverified" | "program_document_missing" | "by_exclusion" | "academic_year_transition" | "graduate_exam_scope" | "exam_scope_unverified" | "exam_scope_verified" | "explicit_program" | "explicit_program_not_applicable" | "multiple_programs" | "no_program_for_grade" | "track_unspecified_general_assumed" | "track_specific_program" | "track_rule_missing_general_used" | "multiple_exam_goals">;
};

export type CurriculumSource = {
  document: string;
  url: string;
  pages?: string | null;
};

export type DataTable = {
  id: string;
  figure?: string | null;
  headers: Array<string>;
  units?: Array<UnitSpec | null>;
  rows: Array<Array<string | null>>;
};

export type DerivationStepBlock = {
  id: string;
  relates_to?: Array<string>;
  references?: Array<Reference>;
  kind: "derivation_step";
  step_index: number;
  title?: string | null;
  explanation: string;
  inputs?: Array<EvidenceRef>;
  outputs?: Array<EvidenceRef>;
  operation?: "add_both_sides" | "subtract_both_sides" | "multiply_both_sides" | "divide_both_sides" | "expand" | "factor" | "complete_square" | "square_both_sides" | "isolate_variable" | "substitute" | "compare" | "evaluate" | "rewrite" | "case_split" | "apply_principle" | "calculate_quantity" | "convert_unit" | "compare_observations" | "infer_sequence" | "evaluate_premise" | "interpret_visual" | "explain" | "state_result" | "unknown";
  operation_origin?: "deterministic" | "v1_step_type" | "fixture" | "unknown";
  method_ref?: string | null;
  assumptions?: Array<string>;
  preconditions?: Array<string>;
  conclusions?: Array<EvidenceRef>;
  narration_ref?: string | null;
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
  blocks: Array<ProseBlock | ExpressionBlock | CalculationBlock | ExampleBlock | TableBlock | VisualBlock | DerivationStepBlock>;
  answer?: MathAnswer | NumberAnswer | QuantityAnswer | ChoiceAnswer | TextAnswer | TableAnswer | null;
  takeaway: string;
  narration?: Array<NarrationSegment>;
};

export type EducationalProvenance = {
  curriculum_version: string;
  knowledge_version: string;
  resolution: CurriculumResolution;
  topic_key?: string | null;
  match: "topic_key" | "alias" | "taxonomy" | "none";
  outcome_ids?: Array<string>;
  knowledge_ids?: Array<string>;
  excluded_draft_knowledge: number;
  payload_bytes: number;
  included_in_prompt: boolean;
  selection_mode?: "deterministic_production" | null;
  topic_mapping?: "structural" | "single" | "ambiguous" | "none" | null;
  topic_candidates?: Array<string>;
  knowledge_refs?: Array<KnowledgeRef>;
  excluded_knowledge?: Array<ExcludedKnowledge>;
  compacted_knowledge?: Array<string>;
  method_policy_ids?: Array<string>;
  inactive_method_policies?: number;
  verification_capabilities?: Array<string>;
  transmission?: "normal" | "emergency" | "mixed" | null;
  transmitted_knowledge_ids?: Array<string>;
  excluded_methods?: Array<ExcludedMethod>;
  attempts?: Array<ContextAttempt>;
  advanced_requested?: boolean;
};

export type Entity = {
  id: string;
  kind: "object" | "body" | "vehicle" | "planet" | "field" | "charge" | "circuit_element" | "lens" | "particle" | "species" | "substance" | "solution" | "apparatus" | "cell" | "organelle" | "organism" | "population" | "structure" | "process_stage" | "gene" | "point" | "segment" | "angle" | "region" | "axis" | "other";
  label?: string | null;
  figure?: string | null;
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
};

export type EvidenceRef = {
  kind: "block" | "source_expression" | "source_choice" | "source_statement" | "source_region" | "observation" | "quantity" | "entity" | "relation" | "figure" | "table_cell" | "check";
  id: string;
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

export type ExcludedKnowledge = {
  id: string;
  reason: "not_runtime_eligible" | "exceeds_record_budget" | "exceeds_total_budget" | "limit_reached" | "above_learner_level" | "learner_level_unknown" | "level_unspecified" | "exam_level_mismatch" | "subject_mismatch";
};

export type ExcludedMethod = {
  policy_id: string;
  reason: "exceeds_total_budget" | "limit_reached";
};

export type ExperimentGroup = {
  id: string;
  conditions: Array<Condition>;
};

export type ExperimentalModel = {
  objective?: string | null;
  hypothesis?: string | null;
  variables: Array<Variable>;
  independent?: Array<string>;
  dependent?: Array<string>;
  controlled?: Array<string>;
  groups?: Array<ExperimentGroup>;
  measurements?: Array<Measurement>;
  claims?: Array<Claim>;
  limitations?: Array<string>;
};

export type ExpressionBlock = {
  id: string;
  relates_to?: Array<string>;
  references?: Array<Reference>;
  kind: "expression";
  latex: string;
};

export type Figure = {
  id: string;
  kind: "geometry_figure" | "force_diagram" | "circuit" | "optics" | "planetary_system" | "motion_diagram" | "reaction_diagram" | "molecular_structure" | "particle_model" | "apparatus" | "cell_diagram" | "biological_system" | "process_diagram" | "experimental_setup" | "graph" | "table" | "other";
  panel_label?: string | null;
  region?: SourceRegion | null;
  scale?: string | null;
  legend?: Array<string>;
};

export type ForbiddenOperation = {
  operation: "add_both_sides" | "subtract_both_sides" | "multiply_both_sides" | "divide_both_sides" | "expand" | "factor" | "complete_square" | "square_both_sides" | "isolate_variable" | "substitute" | "compare" | "evaluate" | "rewrite" | "case_split" | "apply_principle" | "calculate_quantity" | "convert_unit" | "compare_observations" | "infer_sequence" | "evaluate_premise" | "interpret_visual" | "explain" | "state_result" | "unknown" | "derivative" | "integral" | "limit" | "logarithm" | "trigonometry" | "complex_number" | "quadratic_formula";
  reason: string;
};

export type ForceSpec = {
  id: string;
  kind: "gravity" | "normal" | "tension" | "static_friction" | "kinetic_friction" | "applied" | "spring" | "electric" | "magnetic" | "buoyancy" | "drag" | "other";
  on: string;
  by?: string | null;
  magnitude?: string | null;
  direction: "+x" | "-x" | "+y" | "-y" | "up_incline" | "down_incline" | "angle";
  angle_deg?: string | null;
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
};

export type Grade = {
  value: number;
  origin: "declared" | "profile";
};

export type GraphSeries = {
  id: string;
  figure: string;
  x: Axis;
  y: Axis;
  points?: Array<Array<string>>;
  points_origin?: "printed_values" | "none";
};

export type IntegrityCheck = {
  code: "clean" | "normalized_notation" | "decimal_comma_resolved" | "mixed_number_convention" | "unsupported_notation" | "invalid_structure" | "latex_exponent_scope" | "decimal_ambiguity" | "duplicate_expression" | "duplicate_choice_labels" | "missing_choice_label" | "unlabeled_choices" | "equivalent_choice_values" | "single_choice" | "missing_statements" | "duplicate_statement_labels" | "polarity_conflict" | "negation_present" | "missing_question_text" | "provider_uncertainty_material" | "provider_uncertainty_noncritical" | "equivalent_alternatives" | "alternative_not_applicable" | "legacy_uncertainty" | "multiple_questions" | "target_question_unclear" | "invalid_region_omitted" | "essential_visual_without_facts" | "essential_visual_text_sufficient" | "essential_visual_insufficient" | "visual_supplied_by_recheck" | "legacy_uncertainty_material" | "legacy_uncertainty_formatting" | "legacy_uncertainty_context_absent" | "legacy_uncertainty_unclassified" | "legacy_uncertainty_merged" | "recheck_confirmed" | "recheck_equivalent" | "recheck_disagreement" | "recheck_illegible" | "recheck_unavailable" | "recheck_budget_exhausted" | "student_selected" | "student_rejected" | "unsupported_subject" | "not_a_question" | "unreadable_source" | "incomplete_source";
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

export type KnowledgeRef = {
  id: string;
  version: number;
  content_digest: string;
};

export type LawUse = {
  law: string;
  system?: Array<string>;
  conditions?: Array<ConditionClaim>;
};

export type LessonIntent = {
  mode: "question_solving" | "topic_explanation" | "conversation" | "interactive_whiteboard" | "practice" | "student_feedback" | "voice_narration";
  subject: Subject;
  topic_key?: string | null;
  outcome_ids?: Array<string>;
  source_analysis_id?: string | null;
  presentations?: Array<"steps" | "board" | "chat" | "voice">;
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
  problem?: ScientificProblemModel | null;
};

export type LessonView = {
  lesson: LessonPlanV2;
  panels: Array<BoardPanel>;
  created_at: string;
  provenance?: EducationalProvenance | null;
};

export type MathAnswer = {
  kind: "math";
  expressions: Array<string>;
  description: string;
};

export type Measurement = {
  group: string;
  variable: string;
  value: string;
  unit?: UnitSpec | null;
};

export type MethodEvidence = {
  step: string;
  used?: Array<"add_both_sides" | "subtract_both_sides" | "multiply_both_sides" | "divide_both_sides" | "expand" | "factor" | "complete_square" | "square_both_sides" | "isolate_variable" | "substitute" | "compare" | "evaluate" | "rewrite" | "case_split" | "apply_principle" | "calculate_quantity" | "convert_unit" | "compare_observations" | "infer_sequence" | "evaluate_premise" | "interpret_visual" | "explain" | "state_result" | "unknown" | "derivative" | "integral" | "limit" | "logarithm" | "trigonometry" | "complex_number" | "quadratic_formula">;
  mentioned?: Array<"derivative" | "integral" | "limit" | "logarithm" | "trigonometry" | "complex_number" | "quadratic_formula">;
  rejected?: Array<"derivative" | "integral" | "limit" | "logarithm" | "trigonometry" | "complex_number" | "quadratic_formula">;
  identifiable?: boolean;
  unparsed?: number;
};

export type MethodPolicy = {
  id: string;
  grade: number;
  topic: string;
  allowed_operations?: Array<"add_both_sides" | "subtract_both_sides" | "multiply_both_sides" | "divide_both_sides" | "expand" | "factor" | "complete_square" | "square_both_sides" | "isolate_variable" | "substitute" | "compare" | "evaluate" | "rewrite" | "case_split" | "apply_principle" | "calculate_quantity" | "convert_unit" | "compare_observations" | "infer_sequence" | "evaluate_premise" | "interpret_visual" | "explain" | "state_result" | "unknown" | "derivative" | "integral" | "limit" | "logarithm" | "trigonometry" | "complex_number" | "quadratic_formula">;
  forbidden_operations?: Array<ForbiddenOperation>;
  preferred_representations?: Array<string>;
  outcome_ids?: Array<string>;
  status: "draft" | "approved";
  authored_by: "claude-draft" | "teacher";
  approved_by?: string | null;
  approved_on?: string | null;
  approval_digest?: string | null;
};

export type ModeSupport = {
  mode: "question_solving" | "topic_explanation" | "conversation" | "interactive_whiteboard" | "practice" | "student_feedback" | "voice_narration";
  subject: Subject;
  available: boolean;
  planned_phase?: string | null;
  reason: "available" | "planned" | "subject_generation_unavailable";
};

export type MotionPhase = {
  id: string;
  entity: string;
  axis?: "horizontal" | "vertical" | "incline";
  acceleration_kind?: "constant" | "zero" | "varying" | "unknown";
  acceleration_basis?: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed" | null;
  initial_velocity?: string | null;
  final_velocity?: string | null;
  displacement?: string | null;
  distance?: string | null;
  duration?: string | null;
  acceleration?: string | null;
  graph?: string | null;
  free_fall?: boolean;
};

export type NarrationSegment = {
  id: string;
  order: number;
  block: string;
  text: string;
  emphasis?: Array<string>;
  pause_after_ms?: number;
};

export type NarrativeSegment = {
  id: string;
  start: number;
  end: number;
  role: "scenario" | "initial_state" | "event" | "given" | "constraint" | "requested" | "unclassified";
  provenance?: "source_text";
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

export type Observation = {
  id: string;
  statement: string;
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
  evidence?: Array<EvidenceRef>;
  figure?: string | null;
  source?: string | null;
};

export type Outcome = {
  subject: "mathematics";
  grade: number;
  unit: string;
  topic: string;
  outcome_id: string;
  outcome_text_tr?: string | null;
  source: CurriculumSource;
  source_status: "sourced" | "pending";
};

export type PhysicalBody = {
  entity: string;
  mass?: string | null;
  surface?: string | null;
};

export type PhysicsModel = {
  domain: "kinematics" | "dynamics" | "energy" | "momentum" | "dc_circuit" | "other";
  sign_convention?: string | null;
  bodies?: Array<PhysicalBody>;
  surfaces?: Array<Surface>;
  forces?: Array<ForceSpec>;
  strings?: Array<StringLink>;
  phases?: Array<MotionPhase>;
  collisions?: Array<Collision>;
  circuit?: CircuitModel | null;
  laws?: Array<LawUse>;
  equations?: Array<string>;
  target?: PhysicsTarget | null;
};

export type PhysicsTarget = {
  quantity?: string | null;
  kind: string;
  entity?: string | null;
  state?: string | null;
  representation?: "magnitude" | "component" | "unspecified";
  unit?: UnitSpec | null;
  element?: string | null;
  between?: Array<string>;
};

export type PolicyCheck = {
  dimension: "method" | "curriculum";
  state: "passed" | "failed" | "partially_checked" | "not_checked";
  reason: string;
  grade?: number | null;
  topic?: string | null;
  step?: string | null;
  operations?: Array<"add_both_sides" | "subtract_both_sides" | "multiply_both_sides" | "divide_both_sides" | "expand" | "factor" | "complete_square" | "square_both_sides" | "isolate_variable" | "substitute" | "compare" | "evaluate" | "rewrite" | "case_split" | "apply_principle" | "calculate_quantity" | "convert_unit" | "compare_observations" | "infer_sequence" | "evaluate_premise" | "interpret_visual" | "explain" | "state_result" | "unknown" | "derivative" | "integral" | "limit" | "logarithm" | "trigonometry" | "complex_number" | "quadratic_formula">;
  policy_ids?: Array<string>;
  outcome_ids?: Array<string>;
  detail?: string | null;
  evidence?: Array<MethodEvidence>;
  topic_candidates?: Array<string>;
  inactive_policy_ids?: Array<string>;
};

export type Premise = {
  label: string;
  text: string;
  status?: "supported" | "contradicted" | "not_decidable" | "true_not_deducible" | "unevaluated";
  evaluator?: "evidence_check" | "none";
  evidence?: Array<EvidenceRef>;
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

export type QuantityValue = {
  id: string;
  symbol?: string | null;
  name?: string | null;
  magnitude?: string | null;
  original?: string | null;
  unit?: UnitSpec | null;
  significant_digits?: number | null;
  direction?: "none" | "positive" | "negative" | "left" | "right" | "up" | "down" | "into" | "out_of" | "unclear";
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
  evidence?: Array<EvidenceRef>;
  entity?: string | null;
  kind?: string | null;
  state?: string | null;
  representation?: "magnitude" | "component" | "unspecified";
  constant_source?: string | null;
  derivation?: string | null;
  confidence?: number | null;
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

export type Relation = {
  id: string;
  type: "connected_to" | "contains" | "part_of" | "points_to" | "measured_at" | "labeled_as" | "precedes" | "increases" | "decreases" | "adjacent_to" | "acts_on";
  subject: string;
  object: string;
  figure?: string | null;
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
  direction_clear?: boolean;
  interpretation?: string | null;
  interpretation_provenance?: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed" | null;
};

export type SchemaIdentity = {
  name: "teacherai.lesson_plan";
  version: "2.0.0" | "2.1.0" | "2.2.0";
};

export type ScientificProblemModel = {
  schema_version?: "1.0.0";
  subject: Subject;
  source_revision?: number | null;
  narrative?: Array<NarrativeSegment>;
  observations?: Array<Observation>;
  entities?: Array<Entity>;
  relations?: Array<Relation>;
  known?: Array<QuantityValue>;
  unknown?: Array<QuantityValue>;
  assumptions?: Array<Observation>;
  constraints?: Array<string>;
  initial_conditions?: Array<string>;
  boundary_conditions?: Array<string>;
  principles?: Array<Reference>;
  candidate_models?: Array<string>;
  target?: AnswerTarget | null;
  figures?: Array<Figure>;
  graphs?: Array<GraphSeries>;
  tables?: Array<DataTable>;
  experiment?: ExperimentalModel | null;
  premises?: Array<Premise>;
  uncertainties?: Array<string>;
  notes?: Array<string>;
  physics?: PhysicsModel | null;
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
  evidence?: Array<"clean" | "normalized_notation" | "decimal_comma_resolved" | "mixed_number_convention" | "unsupported_notation" | "invalid_structure" | "latex_exponent_scope" | "decimal_ambiguity" | "duplicate_expression" | "duplicate_choice_labels" | "missing_choice_label" | "unlabeled_choices" | "equivalent_choice_values" | "single_choice" | "missing_statements" | "duplicate_statement_labels" | "polarity_conflict" | "negation_present" | "missing_question_text" | "provider_uncertainty_material" | "provider_uncertainty_noncritical" | "equivalent_alternatives" | "alternative_not_applicable" | "legacy_uncertainty" | "multiple_questions" | "target_question_unclear" | "invalid_region_omitted" | "essential_visual_without_facts" | "essential_visual_text_sufficient" | "essential_visual_insufficient" | "visual_supplied_by_recheck" | "legacy_uncertainty_material" | "legacy_uncertainty_formatting" | "legacy_uncertainty_context_absent" | "legacy_uncertainty_unclassified" | "legacy_uncertainty_merged" | "recheck_confirmed" | "recheck_equivalent" | "recheck_disagreement" | "recheck_illegible" | "recheck_unavailable" | "recheck_budget_exhausted" | "student_selected" | "student_rejected" | "unsupported_subject" | "not_a_question" | "unreadable_source" | "incomplete_source">;
  region?: SourceRegion | null;
  note?: string | null;
};

export type StringLink = {
  id: string;
  bodies: Array<string>;
  over_pulley?: boolean;
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
};

export type Subject = "mathematics" | "geometry" | "physics" | "chemistry" | "biology" | "science" | "unknown";

export type Surface = {
  id: string;
  kind: "horizontal" | "incline" | "vertical";
  angle_deg?: string | null;
  friction?: "none" | "present" | "unknown";
  mu_static?: string | null;
  mu_kinetic?: string | null;
  provenance: "source_text" | "visual_reading" | "student_confirmed" | "background_knowledge" | "modeling_assumption" | "inferred" | "derived" | "problem_convention" | "standard_constant" | "provider_proposed";
};

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

export type TargetResolution = {
  target: AnswerTarget;
  given?: Array<string>;
  intermediate?: Array<string>;
  requested?: Array<string>;
  provider_claim?: Array<string>;
  claim_role: "target" | "intermediate" | "none" | "unparsed";
  outcome: "passed" | "failed" | "partially_checked" | "unsupported" | "not_checked" | "not_applicable";
  reason: "target_value_matched" | "target_value_mismatch" | "intermediate_not_requested" | "claim_missing" | "claim_unparsed" | "target_unresolved" | "target_not_computable" | "model_unsupported" | "multiplicity_or_complex_roots" | "domain_excluded" | "not_finite" | "unbounded_extremum" | "multiple_values";
  selected_option?: string | null;
  option_origin?: "independent" | "provider" | "none";
};

export type TextAnswer = {
  kind: "text";
  text: string;
};

export type UnitSpec = {
  original: string;
  status: "parsed" | "ambiguous" | "unsupported";
  canonical?: string | null;
  dimension?: Array<number>;
  scale?: string | null;
  affine?: boolean;
  normalization?: "none" | "alias" | "defined_conversion";
};

export type Variable = {
  id: string;
  name: string;
  unit?: UnitSpec | null;
};

export type VerificationReport = {
  structural: "passed";
  scientific: "passed" | "failed" | "partially_checked" | "unsupported" | "not_checked" | "not_applicable";
  calculation: "passed" | "failed" | "partially_checked" | "unsupported" | "not_checked" | "not_applicable";
  source_consistency: "passed" | "failed" | "partially_checked" | "unsupported" | "not_checked" | "not_applicable";
  curriculum: "passed" | "partially_checked" | "not_checked";
  method: "passed" | "failed" | "partially_checked" | "not_checked";
  pedagogy: "not_checked";
  engine?: string | null;
  checked_claims?: Array<string>;
  block_checks?: Array<BlockCheck>;
  target?: TargetResolution | null;
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
