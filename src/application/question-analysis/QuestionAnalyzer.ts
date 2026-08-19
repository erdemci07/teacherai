import type { AiProvider } from '../../domain/ai/AiProvider.js';
import type { QuestionAnalysis } from '../../domain/lesson/LessonPlan.js';

export interface QuestionAnalysisInput {
  readonly question: string;
}

export interface QuestionAnalyzer {
  analyze(input: QuestionAnalysisInput): Promise<QuestionAnalysis>;
}

export class AiQuestionAnalyzer implements QuestionAnalyzer {
  public constructor(
    private readonly provider: AiProvider<QuestionAnalysisInput, QuestionAnalysis>,
  ) {}

  public analyze(input: QuestionAnalysisInput): Promise<QuestionAnalysis> {
    return this.provider.generate({
      name: 'question-analysis',
      version: '1.0.0',
      input,
    });
  }
}
