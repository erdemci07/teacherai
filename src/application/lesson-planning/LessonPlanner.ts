import type { AiProvider } from '../../domain/ai/AiProvider.js';
import type { LessonPlan, QuestionAnalysis } from '../../domain/lesson/LessonPlan.js';

export interface LessonPlanningInput {
  readonly question: string;
  readonly analysis: QuestionAnalysis;
}

export interface LessonPlanner {
  createLessonPlan(input: LessonPlanningInput): Promise<LessonPlan>;
}

export class AiLessonPlanner implements LessonPlanner {
  public constructor(
    private readonly provider: AiProvider<LessonPlanningInput, LessonPlan>,
  ) {}

  public createLessonPlan(input: LessonPlanningInput): Promise<LessonPlan> {
    return this.provider.generate({
      name: 'lesson-planning',
      version: '1.0.0',
      input,
    });
  }
}
