// Üretilen dosya · python -m scripts.education_contracts

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

export type ContextValue = {
  value: string;
  origin: "declared" | "profile" | "inferred";
};

export type EducationContext = {
  subject: Subject;
  language: string;
  system?: ContextValue | null;
  stage?: ContextValue | null;
  grade?: Grade | null;
  academic_year?: ContextValue | null;
  exam?: ContextValue | null;
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

export type LessonPlanV2 = {
  schema: SchemaIdentity;
  lesson_id: string;
  source_id: string;
  context: EducationContext;
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
};

export type Reference = {
  kind: "concept" | "outcome" | "method" | "prerequisite" | "curriculum" | "source" | "learner";
  key: string;
  review?: "unreviewed";
};

export type SchemaIdentity = {
  name: "teacherai.lesson_plan";
  version: "2.0.0";
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
