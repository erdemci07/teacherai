import { currentToken } from '../auth/AuthProvider';
import type { BoardPlan, GeneratedLesson, LessonContent } from './lesson-api';

export interface PublicLessonSnapshot {
  lesson_plan_id: string;
  learning_objectives: string[];
  concept_id: string;
  content: LessonContent;
}

export interface PublicSolutionSnapshot {
  share_id: string;
  created_at: string;
  updated_at: string;
  status: 'published' | 'revoked';
  expires_at: string | null;
  revoked_at: string | null;
  topic: string;
  subtopic: string | null;
  question_summary: string;
  final_answer: string;
  lesson_snapshot: PublicLessonSnapshot;
  board_snapshot: BoardPlan;
  app_version: string;
  source_lesson_plan_id: string;
}

export interface PublicShare {
  share_id: string;
  share_url: string;
  snapshot: PublicSolutionSnapshot;
}

export interface CreatedShare {
  share_id: string;
  share_url: string;
}

export const SHARE_COPY = {
  text: 'TeacherAI bu matematik sorusunu adım adım çözdü. Çözüm yoluna göz at 👇',
  created: 'Çözüm bağlantısı hazır.',
  copied: 'Çözüm bağlantısı kopyalandı.',
  failed: 'Paylaşım bağlantısı şu anda oluşturulamadı. Tekrar deneyebilirsin.',
};

interface ApiResponse<T> { success: boolean; data: T }

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_TEACHERAI_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function createShare(result: GeneratedLesson, existingShareId?: string): Promise<CreatedShare> {
  const token = await currentToken();
  const response = await fetch(`${BASE}/shares`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ result, existing_share_id: existingShareId ?? null }),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error ?? 'share_error');
  return (body as ApiResponse<CreatedShare>).data;
}

export async function getPublicShare(shareId: string): Promise<PublicShare> {
  const response = await fetch(`${BASE}/shares/${encodeURIComponent(shareId)}`);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error ?? 'share_not_found');
  return (body as ApiResponse<PublicShare>).data;
}
