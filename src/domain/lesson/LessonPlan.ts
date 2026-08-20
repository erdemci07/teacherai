export type Difficulty = 'introductory' | 'developing' | 'proficient' | 'advanced';

export interface LearningObjective {
  readonly id: string;
  readonly description: string;
}

export interface QuestionAnalysis {
  readonly topic: string;
  readonly subtopic: string;
  readonly difficulty: Difficulty;
  readonly learningObjectives: readonly LearningObjective[];
}

export interface LessonStep {
  readonly id: string;
  readonly title: string;
  readonly teacherNarration: string;
  readonly mathematicalStatement: string;
  readonly checksForUnderstanding: readonly string[];
}

export interface LessonPlan {
  readonly id: string;
  readonly question: string;
  readonly analysis: QuestionAnalysis;
  readonly steps: readonly LessonStep[];
  readonly commonMisconceptions: readonly string[];
}
