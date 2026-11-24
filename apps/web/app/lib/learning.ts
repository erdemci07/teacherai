// TA-006: öğrenme arayüzünün saf yardımcıları. React ve tarayıcı API'si kullanmaz; node:test ile sınanır.
import type { CurriculumResolution, ModeSupport } from './education.generated.ts';

export interface NavItem { href: '/' | '/konular' | '/solve' | '/history' | '/dashboard'; label: string; icon: string }

// Yalnız bugün çalışan ekranlar. Konuşma, ses ve canlı tahta TA-013–TA-015'e aittir ve menüde yer almaz.
export const NAV_ITEMS: readonly NavItem[] = [
  { href: '/', label: 'Ana sayfa', icon: '⌂' },
  { href: '/konular', label: 'Konular', icon: '☰' },
  { href: '/solve', label: 'Soru çöz', icon: '✎' },
  { href: '/history', label: 'Geçmiş', icon: '↺' },
  { href: '/dashboard', label: 'Panel', icon: '◎' },
];

export function isCurrent(pathname: string, href: NavItem['href']): boolean {
  if (href === '/') return pathname === '/';
  return pathname === href || pathname.startsWith(`${href}/`);
}

export const SUBJECT_LABELS: Record<string, string> = {
  mathematics: 'Matematik', science: 'Fen Bilimleri', physics: 'Fizik', chemistry: 'Kimya', biology: 'Biyoloji',
};

const REASONS: Record<string, string> = {
  grade_unknown: 'Sınıfını seçmediğin için program belirlenemedi; sorudan sınıf tahmin edilmez.',
  subject_unsupported: 'Bu alan için öğretim programı kaydı yok.',
  schedule_unverified: 'Bu öğretim yılı ve sınıf için resmî uygulama takvimi doğrulanmadı.',
  program_document_missing: 'O yıl uygulanan program belgesi kayıtta yok.',
  by_exclusion: 'Resmî metin yeni programı bu sınıf için saymıyor; önceki programın sürdüğü varsayıldı.',
  academic_year_transition: 'Yaz döneminde biten ve başlayacak öğretim yılı karışabilir; öğretim yılını seç.',
  graduate_exam_scope: 'Mezun öğrenci 12. sınıf öğrencisi sayılmaz; sınav kapsamı esas alınır.',
  exam_scope_unverified: 'Sınavın kapsamı resmî kaynaktan doğrulanmadı.',
  exam_scope_verified: 'Sınav kapsamı resmî kaynaktan doğrulandı.',
  explicit_program: 'Seçtiğin program kullanılıyor.',
  explicit_program_not_applicable: 'Seçtiğin program bu yıl bu sınıfta uygulanmıyor görünüyor.',
  multiple_programs: 'Birden fazla program uygulanabilir.',
  no_program_for_grade: 'Bu sınıfta bu ders ayrı bir program olarak okutulmuyor.',
  track_unspecified_general_assumed: 'Okul türünü seçmediğin için genel program kullanıldı; fen lisesindeysen okul türünü seç.',
  track_specific_program: 'Seçtiğin okul türünün programı kullanılıyor.',
  track_rule_missing_general_used: 'Seçtiğin okul türü için ayrı program doğrulanmadı; genel program kullanıldı.',
  multiple_exam_goals: 'Birden çok sınav hedefi dikkate alındı.',
};

export function resolutionMessage(resolution: CurriculumResolution): { tone: 'ok' | 'warn'; text: string } {
  const details = resolution.reasons?.map((reason: string) => REASONS[reason]).filter(Boolean).join(' ') ?? '';
  if (resolution.status === 'resolved') return { tone: 'ok', text: `Program belirlendi (${resolution.academic_year}). ${details}`.trim() };
  if (resolution.status === 'ambiguous') return { tone: 'warn', text: `Birden çok olasılık var. ${details}`.trim() };
  return { tone: 'warn', text: details || 'Program belirlenemedi.' };
}

export interface SubjectAction { label: string; href?: '/solve'; disabled: boolean; note: string }

// Yalnız desteklenen işlemler etkin gösterilir; FKB üretimi kapalıdır ve işlevsel gösterilmez.
export function subjectActions(modes: ModeSupport[]): SubjectAction[] {
  const solving = modes.find((mode) => mode.mode === 'question_solving');
  const topic = modes.find((mode) => mode.mode === 'topic_explanation');
  const actions: SubjectAction[] = [];
  if (solving?.available) actions.push({ label: 'Bu konudan soru çöz', href: '/solve', disabled: false, note: 'Fotoğrafını yükle; çözüm matematiksel olarak denetlenir.' });
  else actions.push({ label: 'Soru çözümü henüz yok', disabled: true,
    note: solving?.reason === 'subject_generation_unavailable' ? 'Bu alanda ders üretimi henüz açılmadı (TA-009–TA-011).' : 'Henüz kullanılamıyor.' });
  actions.push({ label: 'Konu anlatımı', disabled: !topic?.available, note: topic?.available ? '' : `Planlandı: ${topic?.planned_phase ?? 'sonraki faz'}.` });
  return actions;
}

export const CURRENT_ACADEMIC_YEARS = ['2026-2027', '2025-2026'] as const;

// Profildeki serbest sınav hedefinden tek ve açık sınav adı; "YKS" tek başına belirsizdir.
export type ExamGoal = 'LGS' | 'TYT' | 'AYT';
const EXAM_WORDS: Record<string, readonly ExamGoal[]> = { LGS: ['LGS'], TYT: ['TYT'], AYT: ['AYT'], YKS: ['TYT', 'AYT'] };
// Türkçe çekim ekleri (sunucudaki ``topics.SUFFIX`` ile aynı amaç; tam liste değildir).
const SUFFIX = /^(?:L[AE]R)?(?:[IİUÜ]|S[IİUÜ]|N[IİUÜ]N|[IİUÜ]N|Y?[AE]|[DT][AE]|[DT][AE]N|Y?L[AE]|[DT][IİUÜ]R|N[IİUÜ])?(?:N?[DT][AE]N?|N?[IİUÜ]N|Y?[AE]|K[Iİ]|L[AE]R)?$/;

// TA-007: serbest metinden sınav hedefleri ("LGS'ye", "TYT ve AYT", "YKS" = TYT + AYT). Tanınmayan metin boş liste.
export function examGoals(goal: string | null | undefined): ExamGoal[] {
  const words = (goal ?? '').toLocaleUpperCase('tr-TR').replace(/['’]/g, '').split(/[^A-ZÇĞİÖŞÜ]+/);
  const found: ExamGoal[] = [];
  for (const word of words) {
    for (const [key, exams] of Object.entries(EXAM_WORDS)) {
      if (word === key || (word.startsWith(key) && SUFFIX.test(word.slice(key.length)))) {
        for (const exam of exams) if (!found.includes(exam)) found.push(exam);
      }
    }
  }
  return found;
}

export function examFromGoal(goal: string | null | undefined): ExamGoal | null {
  const found = examGoals(goal);
  return found.length === 1 ? found[0]! : null;
}

// TA-007: yetkili onaylı bilgi girdisi taslak olarak etiketlenmez; taslaklar ayrıca sayılır.
export function knowledgeNote(tree: { knowledge_drafts: number; knowledge_approved?: number }): string {
  const parts = [];
  if ((tree.knowledge_approved ?? 0) > 0) parts.push(` Bu sınıfa bağlı ${tree.knowledge_approved} bilimsel bilgi girdisi öğretmen onaylıdır ve derslerde kullanılabilir.`);
  if (tree.knowledge_drafts > 0) parts.push(` ${tree.knowledge_drafts} bilimsel bilgi taslağı öğretmen incelemesi bekliyor ve derslerde kullanılmıyor.`);
  return parts.join('');
}
