// Soru netleştirme görünüm modeli (TA-003). Saf modüldür; kök TS testlerinden sınanır.
// Öğrenciye teknik ad (AST, OCR, bütünlük motoru) gösterilmez.

import type { IntegrityReport, SourceUncertainty } from './education.generated.ts';

export type ClarificationOption = { id: string; text: string; latex: string | null };

export type QuestionState =
  | { kind: 'proceed' }
  | { kind: 'clarify'; uncertainty: SourceUncertainty; prompt: string; options: ClarificationOption[] }
  | { kind: 'crop'; message: string }
  | { kind: 'retake'; message: string }
  | { kind: 'unsupported'; message: string };

const PROMPTS: Partial<Record<SourceUncertainty['category'], string>> = {
  radical_scope: 'Kök işaretinin nerede bittiğini tam ayırt edemedim. Sorunda hangisi yazıyor?',
  fraction_scope: 'Kesrin payını ve paydasını tam ayırt edemedim. Sorunda hangisi yazıyor?',
  exponent_scope: 'Üssün hangi sayıya ait olduğunu tam ayırt edemedim. Sorunda hangisi yazıyor?',
  sign: 'Buradaki işareti tam ayırt edemedim. Sorunda hangisi yazıyor?',
  decimal: 'Bu sayının ondalık mı yoksa binlik ayırıcıyla mı yazıldığını ayırt edemedim. Hangisi doğru?',
  grouping: 'Parantezlerin nerede açılıp kapandığını tam ayırt edemedim. Sorunda hangisi yazıyor?',
  negation: 'Soru cümlesinin ne istediğini tam ayırt edemedim. Soruda hangisi yazıyor?',
  answer_choice: 'Bu seçeneği tam okuyamadım. Seçenekte hangisi yazıyor?',
  diagram: 'Şekildeki bu değeri tam okuyamadım. Şekilde hangisi yazıyor?',
  graph: 'Grafikteki bu değeri tam okuyamadım. Grafikte hangisi yazıyor?',
  table: 'Tablodaki bu değeri tam okuyamadım. Tabloda hangisi yazıyor?',
};
const DEFAULT_PROMPT = 'Sorunun bir kısmını tam ayırt edemedim. Sorunda hangisi yazıyor?';

export const RETAKE_MESSAGES = {
  retake_required: 'Bu kısmı daha net çekebilir misin? Sorunun tamamı görünecek şekilde yeni bir fotoğraf yeterli.',
  unreadable: 'Fotoğraf biraz bulanık görünüyor. Soruyu net okuyabilmem için biraz daha yakından ve sabit şekilde tekrar çekebilir misin? 🙂',
  incomplete: 'Sorunun bir kısmı kadraj dışında kalmış gibi görünüyor. Sorunun tamamını görebileceğim şekilde tekrar çekebilir misin? 🙂',
  no_question: 'Bu görselde çözebileceğim bir matematik sorusu göremedim 🙂 Sorunun bulunduğu kısmı tekrar çekip gönderebilirsin.',
} as const;

export function questionState(report: IntegrityReport | null | undefined): QuestionState {
  if (!report || report.decision === 'ready' || report.decision === 'ready_with_noncritical_uncertainty') return { kind: 'proceed' };
  if (report.decision === 'unsupported_subject') {
    return { kind: 'unsupported', message: 'Bu soruyu tanıdım ama bu alanda ders anlatımı henüz hazır değil. Şimdilik matematik ve geometri sorularında yardımcı olabilirim.' };
  }
  if (report.decision === 'clarification_required') {
    if (report.recovery === 'crop') {
      return { kind: 'crop', message: 'Görselde birden fazla soru var. Çözmemi istediğin soruyu tek başına çekebilir ya da kırparak gönderebilir misin?' };
    }
    const uncertainty = (report.uncertainties ?? []).find(item => item.impact !== 'noncritical' && item.resolution === 'unresolved' && (item.alternatives?.length ?? 0) > 0);
    if (uncertainty && uncertainty.recognized) {
      const options: ClarificationOption[] = [
        { id: 'recognized', text: uncertainty.recognized, latex: latexOf(uncertainty.recognized) },
        ...(uncertainty.alternatives ?? []).map(item => ({ id: item.id, text: item.text, latex: item.latex ?? latexOf(item.text) })),
      ];
      return { kind: 'clarify', uncertainty, prompt: PROMPTS[uncertainty.category] ?? DEFAULT_PROMPT, options };
    }
  }
  const key = report.decision in RETAKE_MESSAGES ? report.decision as keyof typeof RETAKE_MESSAGES : 'retake_required';
  return { kind: 'retake', message: RETAKE_MESSAGES[key] };
}

// Metin LaTeX komutu içeriyorsa güvenli KaTeX gösterimi için aday sayılır; değilse düz metin gösterilir.
function latexOf(text: string): string | null {
  return /\\[a-zA-Z]+|\^|_/.test(text) ? text : null;
}

export function choiceMismatchNotice(status: string | null | undefined): string | null {
  return status === 'no_match'
    ? 'Bulduğum sonuç seçeneklerin hiçbiriyle uyuşmadı. Seçenekleri bir de kendin kontrol etmeni öneririm; sonucu seçenek harfi olmadan gösteriyorum.'
    : null;
}
