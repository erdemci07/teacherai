// TA-006: salt okunur müfredat uçları. Sağlayıcı çağrısı ve kota yoktur; istekler önbelleğe alınabilir.
import type { Capabilities, CurriculumResolution, ModeSupport } from './education.generated.ts';
import { requestHeaders } from './request-headers.ts';

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_TEACHERAI_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export interface ProgramSummary {
  id: string; label: string; subject: string; framework: string; terminology: string; covered_grades: number[];
  document_title: string; document_url: string; applies: Record<string, number[]>; outcome_count: number;
}
export interface SubjectSummary { subject: string; capabilities: Capabilities; modes: ModeSupport[] }
export interface CatalogView {
  curriculum_version: string; knowledge_version: string; programs: ProgramSummary[]; subjects: SubjectSummary[]; rights_notice: string;
}
export interface BrowseOutcome { id: string; code: string; description_tr: string | null; description_review: string | null; page: number }
export interface BrowseTopic { id: string; code: string; title_tr: string; discipline: string; outcomes: BrowseOutcome[] }
export interface BrowseUnit extends BrowseTopic { topics: BrowseTopic[] }
export interface BrowseView {
  program: ProgramSummary; grade: number; units: BrowseUnit[]; knowledge_drafts: number;
  // TA-007: yetkili onaylı girdiler taslak olarak etiketlenmez. Eski sunucu bu alanı göndermeyebilir.
  knowledge_approved?: number; rights_notice: string;
}
export type Exam = 'LGS' | 'TYT' | 'AYT';
export type SchoolTrack = 'general' | 'science_high_school' | 'basic_level';

async function get<T>(path: string): Promise<T> {
  const headers = await requestHeaders();
  if (!headers.Authorization) throw new Error('authentication_required');
  const response = await fetch(`${BASE}${path}`, { headers });
  if (!response.ok) throw new Error('curriculum_api_error');
  return (await response.json()).data as T;
}

export const getCatalog = () => get<CatalogView>('/curriculum/catalog');
export const browseProgram = (programId: string, grade: number) =>
  get<BrowseView>(`/curriculum/programs/${encodeURIComponent(programId)}/grades/${grade}`);

export function resolveCurriculum(input: { subject: string; grade?: number | null; academicYear?: string | null;
  learnerStatus?: 'student' | 'graduate' | null; exam?: Exam | null; exams?: readonly Exam[]; track?: SchoolTrack | null }) {
  const params = new URLSearchParams({ subject: input.subject });
  if (input.grade) params.set('grade', String(input.grade));
  if (input.academicYear) params.set('academic_year', input.academicYear);
  if (input.learnerStatus) params.set('learner_status', input.learnerStatus);
  // TA-007: birden çok sınav hedefi (ör. TYT ve AYT) ayrı ayrı gönderilir; hiçbiri kaybolmaz.
  for (const exam of new Set([...(input.exams ?? []), ...(input.exam ? [input.exam] : [])])) params.append('exam', exam);
  if (input.track) params.set('track', input.track);
  return get<CurriculumResolution>(`/curriculum/resolve?${params.toString()}`);
}
