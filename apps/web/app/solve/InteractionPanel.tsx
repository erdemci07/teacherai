'use client';

import { useState } from 'react';
import type { LessonPlan } from '../lib/lesson-api';
import { interact, submitPractice, PracticeFeedback, InteractionAction, InteractionApiError, InteractionResponse } from '../lib/interaction-api';
import { errorMessage } from '../lib/error-messages';
import { AdaptiveBoard } from './AdaptiveBoard';
import { RichMathText } from './RichMathText';
import { BrandMark } from '../components/BrandMark';

const actions: { key: InteractionAction; label: string; helper: string; icon: string }[] = [
  { key: 'understood', label: 'Anladım', helper: 'Bu çözüm tamam', icon: '✓' },
  { key: 'simplify', label: 'Daha basit anlat', helper: 'Sadeleştir', icon: '↧' },
  { key: 'alternative', label: 'Başka yöntem göster', helper: 'Farklı yol', icon: '↔' },
  { key: 'hint', label: 'İpucu ver', helper: 'Küçük destek', icon: '?' },
  { key: 'similar_example', label: 'Benzer örnek göster', helper: 'Pratik yap', icon: '+' },
];

export function InteractionPanel({ lesson }: { lesson: LessonPlan }) {
  const [response, setResponse] = useState<InteractionResponse | null>(null);
  const [loading, setLoading] = useState<InteractionAction | null>(null);
  const [error, setError] = useState('');
  const [hintLevel, setHintLevel] = useState(1);

  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState<PracticeFeedback | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function checkAnswer(event: React.FormEvent) {
    event.preventDefault();
    if (!response?.practice || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      setFeedback(await submitPractice(lesson.lesson_plan_id, response.practice.practice_question_id, answer));
    } catch {
      setError('Yanıt kaydedilemedi. Yeniden deneyebilirsin.');
    } finally {
      setSubmitting(false);
    }
  }

  async function run(action: InteractionAction) {
    setLoading(action);
    setError('');
    try {
      const result = await interact(lesson, action, action === 'hint' ? hintLevel : 1);
      setAnswer('');
      setFeedback(null);
      setResponse(result);
      if (action === 'hint' && result.next_hint_level) setHintLevel(result.next_hint_level);
    } catch (e) {
      setError(e instanceof InteractionApiError && (e.code.startsWith('ai_') || e.code === 'maintenance_read_only' || e.code === 'service_moved') ? errorMessage(e.code) : e instanceof InteractionApiError && e.code === 'interaction_provider_unavailable' ? 'Öğretmen yanıtı şu anda hazırlanamadı. Tekrar deneyelim.' : e instanceof InteractionApiError && e.code === 'interaction_context_too_large' ? 'Bu çözüm çok ayrıntılı olduğu için ek anlatım şu anda hazırlanamadı.' : 'Bu etkileşim tamamlanamadı.');
    } finally {
      setLoading(null);
    }
  }

  return (
    <section className="postSolution teacherInteractionCard">
      <header className="postSolutionHeader">
        <BrandMark size="sm" />
        <div>
          <h3>Nasıl, burası oturdu mu?</h3>
          <p>İstersen anlatımı hemen değiştirebilirim.</p>
        </div>
      </header>
      <div className="interactionActions teacherActionList">
        {actions.map((action) => (
          <button disabled={!!loading || submitting} onClick={() => run(action.key)} key={action.key}>
            <span aria-hidden="true">{action.icon}</span>
            <strong>{loading === action.key ? 'Hazırlıyorum...' : action.label}</strong>
            <small>{action.helper}</small>
          </button>
        ))}
      </div>
      {error && <div className="interactionError" role="alert">{error}<button onClick={() => response ? run(response.action) : undefined}>Tekrar dene</button></div>}
      {response && (
        <div className="adaptiveResponse" aria-live="polite">
          <h4>{response.action === 'alternative' ? 'Başka bir yol' : response.action === 'hint' ? `İpucu ${hintLevel > 1 ? hintLevel - 1 : 1}` : 'TeacherAI'}</h4>
          <p><RichMathText text={response.message} /></p>
          {response.practice && <form onSubmit={checkAnswer}>
            <p><RichMathText text={response.practice.question_expression} /></p>
            <label>Cevabın <input value={answer} maxLength={200} required onChange={e => setAnswer(e.target.value)} /></label>
            <button disabled={submitting || !!loading || feedback?.correct || (feedback?.attempt_number ?? 0) >= 3}>Kontrol et</button>
            {feedback && <p role="status">{feedback.message}</p>}
          </form>}
          {response.board && <AdaptiveBoard board={response.board} />}
          {response.action === 'hint' && hintLevel <= 3 && <button className="moreHint" onClick={() => run('hint')}>Bir ipucu daha</button>}
        </div>
      )}
    </section>
  );
}
