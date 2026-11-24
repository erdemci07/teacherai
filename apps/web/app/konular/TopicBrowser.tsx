'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import type { CurriculumResolution } from '../lib/education.generated';
import {
  browseProgram, getCatalog, resolveCurriculum, type BrowseView, type CatalogView,
} from '../lib/curriculum-api';
import { CURRENT_ACADEMIC_YEARS, SUBJECT_LABELS, examFromGoal, resolutionMessage, subjectActions } from '../lib/learning';
import { GRADE_OPTIONS, getProfile } from '../lib/student-api';

type Status = 'student' | 'graduate';

// TA-006: gerçek müfredat kaydında gözatma. Sınıf ve öğrenci/mezun durumu yalnız öğrencinin seçimidir;
// başlangıç değeri profildendir. Seçim değiştirmek ders üretmez ve sağlayıcı çağırmaz.
export function TopicBrowser() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [catalog, setCatalog] = useState<CatalogView | null>(null);
  const [subject, setSubject] = useState('mathematics');
  const [grade, setGrade] = useState<number | null>(null);
  const [year, setYear] = useState<string>(CURRENT_ACADEMIC_YEARS[0]);
  const [status, setStatus] = useState<Status>('student');
  const [exam, setExam] = useState<'LGS' | 'TYT' | 'AYT' | null>(null);
  const [programId, setProgramId] = useState<string | null>(null);
  const [resolution, setResolution] = useState<CurriculumResolution | null>(null);
  const [loaded, setLoaded] = useState<{ key: string; view: BrowseView } | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace('/login');
    if (!user) return;
    getCatalog().then(setCatalog).catch(() => setError(true));
    getProfile().then((profile) => {
      if (profile?.grade) setGrade(profile.grade);
      if (profile?.learner_status) setStatus(profile.learner_status);
      setExam(examFromGoal(profile?.exam_goal));
    }).catch(() => undefined);
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    resolveCurriculum({ subject, grade: status === 'graduate' ? null : grade, academicYear: year, learnerStatus: status, exam })
      .then((value) => {
        setResolution(value);
        setProgramId(value.program_ids?.[0] ?? value.candidate_program_ids?.[0] ?? null);
      })
      .catch(() => setError(true));
  }, [user, subject, grade, year, status, exam]);

  const programs = useMemo(() => (catalog?.programs ?? []).filter((item) => item.subject === subject), [catalog, subject]);
  const program = programs.find((item) => item.id === programId) ?? null;
  const browseGrade = grade && program?.covered_grades.includes(grade) ? grade : program?.covered_grades[0] ?? null;

  const treeKey = program && browseGrade ? `${program.id}:${browseGrade}` : null;
  useEffect(() => {
    if (!program || !browseGrade || !treeKey) return;
    browseProgram(program.id, browseGrade).then((view) => setLoaded({ key: treeKey, view })).catch(() => setError(true));
  }, [program, browseGrade, treeKey]);
  const tree = loaded && loaded.key === treeKey ? loaded.view : null;

  const subjectInfo = catalog?.subjects.find((item) => item.subject === subject);
  const actions = subjectActions(subjectInfo?.modes ?? []);
  const message = resolution ? resolutionMessage(resolution) : null;

  return (
    <div className="taPage taSurface">
      <p className="eyebrow">Konular</p>
      <h1>Programındaki konular</h1>
      <p className="taLead">Resmî öğretim programlarından ünite, konu ve kazanım kodları. Sınıfını sen seçersin; soru fotoğrafından sınıf tahmin edilmez.</p>

      <div className="taTabs" role="group" aria-label="Ders">
        {(catalog?.subjects ?? []).map((item) => (
          <button key={item.subject} type="button" aria-pressed={item.subject === subject} onClick={() => setSubject(item.subject)}>
            {SUBJECT_LABELS[item.subject] ?? item.subject}
          </button>
        ))}
      </div>

      <div className="taControls">
        <label>Durum
          <select value={status} onChange={(event) => setStatus(event.target.value as Status)}>
            <option value="student">Okuyorum</option>
            <option value="graduate">Mezunum (sınava hazırlanıyorum)</option>
          </select>
        </label>
        {status === 'student' && (
          <label>Sınıf
            <select value={grade ?? ''} onChange={(event) => setGrade(event.target.value ? Number(event.target.value) : null)}>
              <option value="">Seçilmedi</option>
              {GRADE_OPTIONS.map((value) => <option key={value} value={value}>{value}. sınıf</option>)}
            </select>
          </label>
        )}
        <label>Öğretim yılı
          <select value={year} onChange={(event) => setYear(event.target.value)}>
            {CURRENT_ACADEMIC_YEARS.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label>Sınav hedefi
          <select value={exam ?? ''} onChange={(event) => setExam((event.target.value || null) as typeof exam)}>
            <option value="">Yok</option><option value="LGS">LGS</option><option value="TYT">TYT</option><option value="AYT">AYT</option>
          </select>
        </label>
        <label>Program
          <select value={programId ?? ''} onChange={(event) => setProgramId(event.target.value || null)}>
            <option value="">Seçilmedi</option>
            {programs.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
      </div>

      {message && <p className={`taNotice ${message.tone === 'ok' ? 'ok' : ''}`} role="status">{message.text}</p>}
      {error && <p className="taNotice" role="alert">Müfredat bilgisi alınamadı. Bağlantını kontrol et.</p>}

      <div className="taActions">
        {actions.map((action) => action.href
          ? <Link key={action.label} className="primary" href={action.href}>{action.label}</Link>
          : <button key={action.label} type="button" disabled title={action.note}>{action.label}</button>)}
      </div>
      {actions.filter((action) => action.note).map((action) => <p key={action.label} className="taMuted">{action.label}: {action.note}</p>)}

      {tree && (
        <section aria-label={`${tree.program.label} ${tree.grade}. sınıf`}>
          <h2 className="visuallyHidden">{tree.program.label} · {tree.grade}. sınıf</h2>
          <p className="taMuted">{tree.program.label} · {tree.grade}. sınıf · <a href={tree.program.document_url} target="_blank" rel="noreferrer">resmî belge</a></p>
          {tree.units.map((unit) => (
            <details key={unit.id} className="taUnit">
              <summary><span className="taCode">{unit.code}</span>{unit.title_tr}{unit.discipline === 'geometry' && <span className="taBadge geo">Geometri</span>}</summary>
              <div>
                {unit.topics.map((topic) => (
                  <div key={topic.id} className="taTopic">
                    <h3><span className="taCode">{topic.code}</span> {topic.title_tr}</h3>
                    <Outcomes items={topic.outcomes} />
                  </div>
                ))}
                {unit.topics.length === 0 && <Outcomes items={unit.outcomes} />}
              </div>
            </details>
          ))}
          <p className="taMuted">{tree.rights_notice}{tree.knowledge_drafts > 0 && ` Bu sınıfa bağlı ${tree.knowledge_drafts} bilimsel bilgi taslağı öğretmen incelemesi bekliyor ve derslerde kullanılmıyor.`}</p>
        </section>
      )}
    </div>
  );
}

function Outcomes({ items }: { items: BrowseView['units'][number]['outcomes'] }) {
  return (
    <ul className="taOutcomes">
      {items.map((item) => (
        <li key={item.id}>
          <span className="taCode">{item.code}</span>
          <span>{item.description_tr ?? <span className="taMuted">Resmî metin gösterilmiyor (PDF s. {item.page})</span>}
            {item.description_tr && item.description_review !== 'approved' && <span className="taBadge">taslak betimleme</span>}</span>
        </li>
      ))}
    </ul>
  );
}
