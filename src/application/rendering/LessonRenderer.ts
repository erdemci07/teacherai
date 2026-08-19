import type { LessonPlan } from '../../domain/lesson/LessonPlan.js';

export interface WhiteboardFrame {
  readonly id: string;
  readonly narration: string;
  readonly elements: readonly WhiteboardElement[];
}

export type WhiteboardElement =
  | { readonly type: 'heading'; readonly text: string }
  | { readonly type: 'math'; readonly latex: string }
  | { readonly type: 'prompt'; readonly text: string };

export interface WhiteboardDocument {
  readonly lessonPlanId: string;
  readonly frames: readonly WhiteboardFrame[];
}

export interface LessonRenderer<TDocument> {
  render(lessonPlan: LessonPlan): Promise<TDocument>;
}
