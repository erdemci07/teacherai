'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import type { CurriculumResolution } from '../lib/education.generated';
import {
  browseProgram, getCatalog, resolveCurriculum, type BrowseView, type CatalogView, type Exam, type SchoolTrack,
} from '../lib/curriculum-api';
import { CURRENT_ACADEMIC_YEARS, SUBJECT_LABELS, examGoals, knowledgeNote, resolutionMessage, subjectActions } from '../lib/learning';
import { GRADE_OPTIONS, getProfile } from '../lib/student-api';
import { saveTopicContext } from '../lib/topic-context';

type Status = 'student' | 'graduate';
const EXAM_OPTIONS: { value: string; label: string; exams: Exam[] }[] = [
  { value: '', label: 'Yok', exams: [] }, { value: 'LGS', label: 'LGS', exams: ['LGS'] },
  { value: 'TYT', label: 'TYT', exams: ['TYT'] }, { value: 'AYT', label: 'AYT', exams: ['AYT'] },
  { value: 'TYT+AYT', label: 'TYT ve AYT (YKS)', exams: ['TYT', 'AYT'] },
];

// TA-006/TA-007: gerçek müfredat kaydında gözatma. Sınıf, öğrenci/mezun durumu, okul türü ve sınav hedefi yalnız
// öğrencinin seçimidir; başlangıç değeri profildendir. Seçim değiştirmek ders üretmez ve sağlayıcı çağırmaz.
// Sınıf bilinmiyorsa program kendiliğinden seçilmez; açık program seçimi beyana göre belirlenen programdan
// farklıysa bu açıkça söylenir. Eski (geç gelen) yanıtlar güncel seçimin üzerine yazılmaz.
export function TopicBrowser() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [catalog, setCatalog] = useState<CatalogView | null>(null);
  const [subject, setSubject] = useState('mathematics');
  const [grade, setGrade] = useState<number | null>(null);
  const [year, setYear] = useState<string>(CURRENT_ACADEMIC_YEARS[0]);
  const [status, setStatus] = useState<Status>('student');
  const [examKey, setExamKey] = useState('');
  const [track, setTrack] = useState<SchoolTrack | ''>('');
  const [chosenProgram, setChosenProgram] = useState<string | null>(null);
  const [resolved, setResolved] = useState<{ key: string; value: CurriculumResolution } | null>(null);
  const [loaded, setLoaded] = useState<{ key: string; view: BrowseView } | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace('/login');
    if (!user) return;
    let current = true;
    getCatalog().then((value) => { if (current) setCatalog(value); }).catch(() => { if (current) setError(true); });
    getProfile().then((profile) => {
      if (!current) return;
      if (profile?.grade) setGrade(profile.grade);
      if (profile?.learner_status) setStatus(profile.learner_status);
      const goals = examGoals(profile?.exam_goal);
      setExamKey(EXAM_OPTIONS.find((option) => option.exams.join('+') === goals.join('+'))?.value ?? '');
    }).catch(() => undefined);
    return () => { current = false; };
  }, [user, loading, router]);

  const effectiveGrade = status === 'graduate' ? null : grade;
  const resolveKey = JSON.stringify([subject, effectiveGrade, year, status, examKey, track]);
  useEffect(() => {
    if (!user) return;
    let current = true;  // geç gelen eski yanıt yok sayılır
    const exams = EXAM_OPTIONS.find((option) => option.value === examKey)?.exams ?? [];
    resolveCurriculum({ subject, grade: effectiveGrade, academicYear: year, learnerStatus: status, exams, track: track || null })
      .then((value) => { if (current) setResolved({ key: resolveKey, value }); })
      .catch(() => { if (current) setError(true); });
    return () => { current = false; };
  }, [user, subject, effectiveGrade, year, status, examKey, track, resolveKey]);
  const resolution = resolved && resolved.key === resolveKey ? resolved.value : null;

  const programs = useMemo(() => (catalog?.programs ?? []).filter((item) => item.subject === subject), [catalog, subject]);
  const resolvedProgram = resolution?.status === 'resolved' ? resolution.program_ids?.[0] ?? null : null;
  const programId = chosenProgram ?? resolvedProgram;
  const program = programs.find((item) => item.id === programId) ?? null;
  // Sınıf bilinmeden ağaç gösterilmez; programın kapsamadığı sınıfa rastgele başka sınıf konmaz.
  const browseGrade = program && effectiveGrade && program.covered_grades.includes(effectiveGrade) ? effectiveGrade : null;
  const mismatch = chosenProgram && resolution?.status === 'resolved' && resolvedProgram !== chosenProgram;

  const treeKey = program && browseGrade ? `${program.id}:${browseGrade}` : null;
  useEffect(() => {
    if (!program || !browseGrade || !treeKey) return;
    let current = true;
    browseProgram(program.id, browseGrade).then((view) => { if (current) setLoaded({ key: treeKey, view }); })
      .catch(() => { if (current) setError(true); });
    return () => { current = false; };
  }, [program, browseGrade, treeKey]);
  const tree = loaded && loaded.key === treeKey ? loaded.view : null;

  const subjectInfo = catalog?.subjects.find((item) => item.subject === subject);
  const actions = subjectActions(subjectInfo?.modes ?? []);
  const solving = actions.find((action) => action.href);
  const message = resolution ? resolutionMessage(resolution) : null;
  const showTrack = status === 'graduate' || (grade !== null && grade >= 9);

  function changeSubject(value: string) { setSubject(value); setChosenProgram(null); }

  return (
    <div className="taPage taSurface">
      <p className="eyebrow">Konular</p>
      <h1>Programındaki konular</h1>
      <p className="taLead">Resmî öğretim programlarından ünite, konu ve kazanım kodları. Sınıfını sen seçersin; soru fotoğrafından sınıf tahmin edilmez.</p>

      <div className="taTabs" role="group" aria-label="Ders">
        {(catalog?.subjects ?? []).map((item) => (
          <button key={item.subject} type="button" aria-pressed={item.subject === subject} onClick={() => changeSubject(item.subject)}>
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
        {showTrack && (
          <label>Okul türü
            <select value={track} onChange={(event) => setTrack(event.target.value as SchoolTrack | '')}>
              <option value="">Seçilmedi (genel program)</option>
              <option value="general">Genel lise</option>
              <option value="science_high_school">Fen lisesi</option>
            </select>
          </label>
        )}
        <label>Öğretim yılı
          <select value={year} onChange={(event) => setYear(event.target.value)}>
            {CURRENT_ACADEMIC_YEARS.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label>Sınav hedefi
          <select value={examKey} onChange={(event) => setExamKey(event.target.value)}>
            {EXAM_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <label>Program
          <select value={chosenProgram ?? ''} onChange={(event) => setChosenProgram(event.target.value || null)}>
            <option value="">{resolvedProgram ? 'Beyanına göre belirlenen' : 'Seçilmedi'}</option>
            {programs.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
      </div>

      {message && <p className={`taNotice ${message.tone === 'ok' ? 'ok' : ''}`} role="status">{message.text}</p>}
      {mismatch && <p className="taNotice" role="status" data-program-mismatch="true">
        Seçtiğin program, beyanına göre bu yıl uygulanan programdan farklı. Konular seçtiğin programdan gösteriliyor.</p>}
      {program && !browseGrade && <p className="taMuted" data-needs-grade="true">
        {effectiveGrade ? 'Bu program seçtiğin sınıfı kapsamıyor.' : 'Konuları görmek için sınıfını seç.'}</p>}
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
                    {solving?.href && <Link className="taTopicAction" href={solving.href} onClick={() => saveTopicContext({
                      programId: tree.program.id, programLabel: tree.program.label, grade: tree.grade,
                      topicId: topic.id, code: topic.code, title: topic.title_tr,
                    })}>Bu konudan soru çöz</Link>}
                  </div>
                ))}
                {unit.topics.length === 0 && <Outcomes items={unit.outcomes} />}
              </div>
            </details>
          ))}
          <p className="taMuted">{tree.rights_notice}{knowledgeNote(tree)}</p>
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
