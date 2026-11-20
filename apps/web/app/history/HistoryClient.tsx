'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../auth/AuthProvider';
import { getHistory, type LessonHistory } from '../lib/student-api';
import { LessonReading } from './LessonReading';

function HistoryRecords() {
  const [items, setItems] = useState<LessonHistory[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    getHistory().then(data => { if (active) setItems(data); })
      .catch(() => { if (active) setError('Geçmiş yüklenemedi.'); });
    return () => { active = false; };
  }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!items) return <p>Geçmiş yükleniyor…</p>;
  return <div className="historyList">{items.map(x => <details key={x.lesson_id}>
    <summary><strong>{x.topic}</strong><span>{new Date(x.created_at).toLocaleDateString('tr-TR')} • {x.exam_context ?? 'Genel'} • {x.difficulty}</span></summary>
    <p>{x.question_summary}</p><p><b>Cevap:</b> {x.final_answer}</p>
    {x.verification_status === 'legacy_unverified' ? <small>Eski kayıt · doğrulama kaynağı belirsiz</small>
      : <><small>{x.verification_status}</small><LessonReading lessonId={x.lesson_id} /></>}
  </details>)}{!items.length && <p>Henüz kaydedilmiş bir dersin yok.</p>}</div>;
}

export function HistoryClient() {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => { if (!loading && !user) router.replace('/login'); }, [loading, user, router]);
  if (loading || !user) return <p>Oturum yükleniyor…</p>;
  return <HistoryRecords key={user.uid} />;
}
