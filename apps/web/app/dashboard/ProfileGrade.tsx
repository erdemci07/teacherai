'use client';

import { useEffect, useState } from 'react';
import { GRADE_OPTIONS, getProfile, parseGrade, saveProfile, type StudentProfile } from '../lib/student-api';

// TA-005B: sınıf yalnız öğrencinin kendi beyanıdır. Değişiklik yeni derslere uygulanır; geçmiş dersler
// üretildikleri andaki sınıfı korur.
export function ProfileGrade({ fallbackName }: { fallbackName: string }) {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [grade, setGrade] = useState('');
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  useEffect(() => {
    getProfile()
      .then((value) => {
        setProfile(value);
        setGrade(value?.grade ? String(value.grade) : '');
      })
      .catch(() => setState('error'));
  }, []);

  async function save() {
    setState('saving');
    try {
      const name = profile?.display_name || fallbackName;
      const saved = await saveProfile(name, profile?.exam_goal ?? null, parseGrade(grade));
      setProfile(saved);
      setState('saved');
    } catch {
      setState('error');
    }
  }

  return (
    <section className="memoryPanel">
      <h2>Sınıfın</h2>
      <p>Yöntem denetimi bu bilgiyle yapılır. Yeni derslere uygulanır; geçmiş dersler değişmez.</p>
      <form className="authForm" onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <label>
          Sınıf
          <select value={grade} onChange={(event) => { setGrade(event.target.value); setState('idle'); }}>
            <option value="">Belirtmek istemiyorum</option>
            {GRADE_OPTIONS.map((value) => <option key={value} value={value}>{value}. sınıf</option>)}
          </select>
        </label>
        {state === 'error' && <p role="alert" className="authError">Sınıf kaydedilemedi. Bağlantını kontrol et.</p>}
        {state === 'saved' && <p role="status">Kaydedildi.</p>}
        <button className="secondaryButton" disabled={state === 'saving'}>{state === 'saving' ? 'Bekle…' : 'Kaydet'}</button>
      </form>
    </section>
  );
}
