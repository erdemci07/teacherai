'use client';

import { useEffect, useState } from 'react';
import { GRADE_OPTIONS, getProfile, parseGrade, saveLearnerProfile, type LearnerStatus, type StudentProfile } from '../lib/student-api';

// TA-005B: sınıf yalnız öğrencinin kendi beyanıdır. Değişiklik yeni derslere uygulanır; geçmiş dersler
// üretildikleri andaki sınıfı korur.
export function ProfileGrade({ fallbackName }: { fallbackName: string }) {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [grade, setGrade] = useState('');
  // TA-006: öğrenci/mezun durumu yalnız açık beyandır; mezun öğrenci 12. sınıf öğrencisi sayılmaz.
  const [status, setStatus] = useState<LearnerStatus | ''>('');
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  useEffect(() => {
    getProfile()
      .then((value) => {
        setProfile(value);
        setGrade(value?.grade ? String(value.grade) : '');
        setStatus(value?.learner_status ?? '');
      })
      .catch(() => setState('error'));
  }, []);

  async function save() {
    setState('saving');
    try {
      const name = profile?.display_name || fallbackName;
      // Sınıf alanı parseGrade(grade) ile doğrulanır; durum boşsa null gönderilir.
      const saved = await saveLearnerProfile(name, profile?.exam_goal ?? null, parseGrade(grade), status || null);
      setProfile(saved);
      setState('saved');
    } catch {
      setState('error');
    }
  }

  return (
    <section className="memoryPanel">
      <h2>Sınıfın</h2>
      <p>Yöntem denetimi ve konu programı bu bilgiyle seçilir. Yeni derslere uygulanır; geçmiş dersler değişmez.</p>
      <form className="authForm" onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <label>
          Sınıf
          <select value={grade} onChange={(event) => { setGrade(event.target.value); setState('idle'); }}>
            <option value="">Belirtmek istemiyorum</option>
            {GRADE_OPTIONS.map((value) => <option key={value} value={value}>{value}. sınıf</option>)}
          </select>
        </label>
        <label>
          Durum
          <select value={status} onChange={(event) => { setStatus(event.target.value as LearnerStatus | ''); setState('idle'); }}>
            <option value="">Belirtmek istemiyorum</option>
            <option value="student">Okuyorum</option>
            <option value="graduate">Mezunum (sınava hazırlanıyorum)</option>
          </select>
        </label>
        {state === 'error' && <p role="alert" className="authError">Sınıf kaydedilemedi. Bağlantını kontrol et.</p>}
        {state === 'saved' && <p role="status">Kaydedildi.</p>}
        <button className="secondaryButton" disabled={state === 'saving'}>{state === 'saving' ? 'Bekle…' : 'Kaydet'}</button>
      </form>
    </section>
  );
}
