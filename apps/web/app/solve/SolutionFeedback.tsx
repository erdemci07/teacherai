'use client';

import { useEffect, useRef, useState } from 'react';
import type { GeneratedLesson } from '../lib/lesson-api';
import { FeedbackApiError, FeedbackRating, FeedbackReason, submitFeedback } from '../lib/feedback-api';

const MAX_COMMENT_LENGTH = 1000;
const POSITIVE_REASONS: { key: FeedbackReason; label: string }[] = [
  { key: 'clear', label: 'Anlaşılırdı' },
  { key: 'correct_solution', label: 'Çözüm doğruydu' },
  { key: 'good_explanation', label: 'Anlatım güzeldi' },
  { key: 'useful', label: 'İşime yaradı' },
  { key: 'other', label: 'Diğer' },
];
const NEGATIVE_REASONS: { key: FeedbackReason; label: string }[] = [
  { key: 'wrong_solution', label: 'Çözüm yanlış' },
  { key: 'misread_question', label: 'Soruyu yanlış okudu' },
  { key: 'step_error', label: 'Bir işlem/adım hatalı' },
  { key: 'unclear_explanation', label: 'Anlatım anlaşılmadı' },
  { key: 'formula_rendering_error', label: 'Formül/gösterim hatalı' },
  { key: 'too_long', label: 'Çok uzun / gereksiz' },
  { key: 'other', label: 'Diğer' },
];

export function SolutionFeedback({ result }: { result: GeneratedLesson }) {
  const [rating, setRating] = useState<FeedbackRating | null>(null);
  const [reasons, setReasons] = useState<FeedbackReason[]>([]);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const closeRef = useRef<HTMLButtonElement>(null);

  const open = (value: FeedbackRating) => {
    setRating(value);
    setReasons([]);
    setComment('');
    setError('');
    setSubmitted(false);
  };

  const close = () => {
    if (submitting) return;
    setRating(null);
  };

  useEffect(() => {
    if (!rating) return;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [rating, submitting]);

  const toggleReason = (reason: FeedbackReason) => {
    setReasons((current) => (current.includes(reason) ? current.filter((item) => item !== reason) : [...current, reason]));
  };

  const send = async () => {
    if (!rating || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      await submitFeedback({ rating, reasons, comment, result });
      setSubmitted(true);
    } catch (caught) {
      const code = caught instanceof FeedbackApiError ? caught.code : 'feedback_error';
      setError(code === 'validation_error' ? 'Geri bildirimin çok uzun veya eksik görünüyor.' : 'Geri bildirimin gönderilemedi. Tekrar deneyebilirsin.');
    } finally {
      setSubmitting(false);
    }
  };

  const options = rating === 'positive' ? POSITIVE_REASONS : NEGATIVE_REASONS;

  return (
    <section className="solutionFeedback feedbackMobileCard" aria-label="Çözüm geri bildirimi">
      <div className="feedbackPrompt">
        <span>Bu anlatım nasıldı?</span>
        <h3>TeacherAI doğru yolda mı?</h3>
        <p>Geri bildirimin TeacherAI'ı geliştirmemize yardımcı olur.</p>
      </div>
      <div className="feedbackQuickActions">
        <button type="button" aria-label="Olumlu geri bildirim ver" onClick={() => open('positive')}>
          <span aria-hidden="true">👍</span>
          <strong>Faydalıydı</strong>
        </button>
        <button type="button" aria-label="Olumsuz geri bildirim ver" onClick={() => open('negative')}>
          <span aria-hidden="true">👎</span>
          <strong>Geliştirilebilir</strong>
        </button>
      </div>

      {rating && (
        <div className="feedbackOverlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
          <div className="feedbackDialog" role="dialog" aria-modal="true" aria-labelledby="feedbackTitle">
            <header>
              <div>
                <span>{rating === 'positive' ? '👍' : '👎'}</span>
                <h3 id="feedbackTitle">{rating === 'positive' ? 'Neyi iyi buldun?' : 'Nerede sorun vardı?'}</h3>
              </div>
              <button ref={closeRef} type="button" className="feedbackClose" aria-label="Geri bildirim panelini kapat" onClick={close}>×</button>
            </header>
            {submitted ? (
              <div className="feedbackThanks" role="status">Teşekkürler! Geri bildirimin alındı.</div>
            ) : (
              <>
                <div className="feedbackReasons" aria-label="Geri bildirim nedenleri">
                  {options.map((option) => (
                    <button
                      key={option.key}
                      type="button"
                      aria-pressed={reasons.includes(option.key)}
                      className={reasons.includes(option.key) ? 'selected' : ''}
                      onClick={() => toggleReason(option.key)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <label className="feedbackComment">
                  <span>Biraz daha anlatmak ister misin?</span>
                  <textarea
                    value={comment}
                    maxLength={MAX_COMMENT_LENGTH}
                    onChange={(event) => setComment(event.target.value.slice(0, MAX_COMMENT_LENGTH))}
                    rows={4}
                  />
                  <small>{comment.length}/{MAX_COMMENT_LENGTH}</small>
                </label>
                {error && <p className="feedbackSubmitError" role="alert">{error}</p>}
                <button type="button" className="primaryButton feedbackSubmit" onClick={send} disabled={submitting}>
                  {submitting ? 'Gönderiliyor...' : 'Gönder'}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
