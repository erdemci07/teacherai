'use client';

import { useState } from 'react';
import type { LessonView } from '../lib/education.generated';
import { getLessonView } from '../lib/student-api';
import { EducationBoard } from './EducationBoard';

export function LessonReading({ lessonId }: { lessonId: string }) {
  const [view, setView] = useState<LessonView | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function open() {
    setPending(true);
    setError('');
    try { setView(await getLessonView(lessonId)); }
    catch { setError('Ders anlatımı açılamadı. Tekrar deneyebilirsin.'); }
    finally { setPending(false); }
  }
  if (view) return <EducationBoard view={view} />;
  return <div><button type="button" disabled={pending} onClick={open}>{pending ? 'Yükleniyor…' : 'Ders anlatımını aç'}</button>
    {error && <p role="alert">{error}</p>}</div>;
}
