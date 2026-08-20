import type { LessonPlan } from '../../../domain/lesson/LessonPlan.js';
import type { LessonRenderer, WhiteboardDocument } from '../../../application/rendering/LessonRenderer.js';

export class StructuredWhiteboardRenderer implements LessonRenderer<WhiteboardDocument> {
  public async render(lessonPlan: LessonPlan): Promise<WhiteboardDocument> {
    return {
      lessonPlanId: lessonPlan.id,
      frames: lessonPlan.steps.map((step) => ({
        id: step.id,
        narration: step.teacherNarration,
        elements: [
          { type: 'heading', text: step.title },
          { type: 'math', latex: step.mathematicalStatement },
          ...step.checksForUnderstanding.map((text) => ({ type: 'prompt' as const, text })),
        ],
      })),
    };
  }
}
