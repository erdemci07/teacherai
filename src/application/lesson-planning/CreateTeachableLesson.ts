import type { LessonPlan } from '../../domain/lesson/LessonPlan.js';
import type { LessonPlanner } from './LessonPlanner.js';
import type { QuestionAnalyzer } from '../question-analysis/QuestionAnalyzer.js';

export interface CreateTeachableLessonInput {
  readonly question: string;
}

export class CreateTeachableLesson {
  public constructor(
    private readonly analyzer: QuestionAnalyzer,
    private readonly planner: LessonPlanner,
  ) {}

  public async execute(input: CreateTeachableLessonInput): Promise<LessonPlan> {
    const analysis = await this.analyzer.analyze({ question: input.question });

    return this.planner.createLessonPlan({
      question: input.question,
      analysis,
    });
  }
}
