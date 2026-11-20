import { requestHeaders } from './request-headers';
import type { GeneratedLesson } from './lesson-api';

export type FeedbackRating = 'positive' | 'negative';
export type FeedbackReason =
  | 'clear'
  | 'correct_solution'
  | 'good_explanation'
  | 'useful'
  | 'wrong_solution'
  | 'misread_question'
  | 'step_error'
  | 'unclear_explanation'
  | 'formula_rendering_error'
  | 'too_long'
  | 'other';

export interface SubmitFeedbackPayload {
  rating: FeedbackRating;
  reasons: FeedbackReason[];
  comment: string;
  result: GeneratedLesson;
}

export interface SubmitFeedbackResult {
  feedback_id: string;
  created: boolean;
  critical: boolean;
  notification_attempted: boolean;
}

export class FeedbackApiError extends Error {
  constructor(public code: string) {
    super(code);
  }
}

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_TEACHERAI_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function submitFeedback(payload: SubmitFeedbackPayload): Promise<SubmitFeedbackResult> {
  const headers = await requestHeaders();
  const response = await fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify({ rating: payload.rating, reasons: payload.reasons, lesson_id: payload.result.lesson.lesson_plan_id, comment: payload.comment.trim() || null }),
  });
  const body = await response.json();
  if (!response.ok) throw new FeedbackApiError(body.error ?? 'feedback_error');
  return body.data;
}
