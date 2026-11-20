'use client';

import { ChangeEvent, ClipboardEvent, useEffect, useRef, useState } from 'react';
import { analyzeQuestionImage, clarifyQuestion, ImageStatus, VisionAnalysis, VisionApiError } from '../lib/vision-api';
import { choiceMismatchNotice, questionState, type QuestionState } from '../lib/clarification';
import { ClarificationPanel } from './ClarificationPanel';
import { generateLesson, GeneratedLesson, LessonApiError } from '../lib/lesson-api';
import Link from 'next/link';
import { useAuth } from '../auth/AuthProvider';
import { InteractionPanel } from './InteractionPanel';
import { AnalysisLoading } from './AnalysisLoading';
import { ErrorBanner } from './ErrorBanner';
import { ImagePreview } from './ImagePreview';
import { UploadCard } from './UploadCard';
import { TeacherBoard } from './TeacherBoard';
import { LessonText } from './LessonText';
import { SolutionFeedback } from './SolutionFeedback';
import { ShareSolution } from './ShareSolution';
import { BrandMark } from '../components/BrandMark';
import { ERROR_MESSAGES } from '../lib/error-messages';
import { IdempotencyKeys, outcomeOf } from '../lib/idempotency';

type SolveState = 'idle' | 'image_selected' | 'uploading' | 'analyzing' | 'clarifying' | 'planning' | 'rendering' | 'success' | 'error';
const SUPPORTED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];
const SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'];
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ERRORS = ERROR_MESSAGES;
const INVALID_QUESTION_MESSAGES: Record<Exclude<ImageStatus, 'valid_math_question'>, string> = {
  not_math_question: 'Bu görselde çözebileceğim bir matematik sorusu göremedim 🙂 Sorunun bulunduğu kısmı tekrar çekip gönderebilirsin.',
  unreadable: 'Fotoğraf biraz bulanık görünüyor. Soruyu net okuyabilmem için biraz daha yakından ve sabit şekilde tekrar çekebilir misin? 🙂',
  incomplete_question: 'Sorunun bir kısmı kadraj dışında kalmış gibi görünüyor. Sorunun tamamını görebileceğim şekilde tekrar çekebilir misin? 🙂',
};
const fileKey = (value: File) => `${value.name}:${value.size}:${value.lastModified}`;

export function SolveWorkspace() {
  const [state, setState] = useState<SolveState>('idle');
  const {user, loading} = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [previewAvailable, setPreviewAvailable] = useState(false);
  const [analysis, setAnalysis] = useState<VisionAnalysis | null>(null);
  const [result, setResult] = useState<GeneratedLesson | null>(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const [showText, setShowText] = useState(false);
  const [selectedFileKey, setSelectedFileKey] = useState('');
  const [solvedFileKey, setSolvedFileKey] = useState('');
  const [lessonScrollSignal, setLessonScrollSignal] = useState(0);
  const [questionView, setQuestionView] = useState<QuestionState | null>(null);
  const [clarifying, setClarifying] = useState(false);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const lessonStartRef = useRef<HTMLDivElement>(null);
  const selectedFileKeyRef = useRef('');
  const idempotency = useRef(new IdempotencyKeys());
  const busy = state === 'uploading' || state === 'analyzing' || state === 'planning' || state === 'rendering';
  const invalidAnalysis = analysis && !analysis.is_valid_question ? analysis : null;
  const solvedCurrentImage = Boolean(file && selectedFileKey && selectedFileKey === solvedFileKey);
  const stateLabel = result ? 'Çözüldü' : busy ? 'Hazırlanıyor' : state === 'clarifying' ? 'Netleştiriliyor' : file ? 'Soru seçildi' : 'Yeni soru';
  const mismatch = result ? choiceMismatchNotice(result.verification.choice_match?.status) : null;

  const revokeBlobPreview = (url: string) => {
    if (url.startsWith('blob:')) URL.revokeObjectURL(url);
  };

  useEffect(() => () => { if (preview) revokeBlobPreview(preview); }, [preview]);

  useEffect(() => {
    if (!lessonScrollSignal) return;
    lessonStartRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [lessonScrollSignal]);

  const select = (selected: File) => {
    const mediaType = selected.type.toLowerCase();
    const extension = selected.name.includes('.') ? `.${selected.name.split('.').pop()?.toLowerCase()}` : '';
    const supported = SUPPORTED_TYPES.includes(mediaType) || (!mediaType && SUPPORTED_EXTENSIONS.includes(extension));
    if (!supported) { setError(ERRORS.unsupported_image_type); setState('error'); return; }
    if (selected.size > MAX_FILE_BYTES) { setError(ERRORS.image_too_large); setState('error'); return; }
    if (preview) revokeBlobPreview(preview);
    const key = fileKey(selected);
    selectedFileKeyRef.current = key;
    setSelectedFileKey(key);
    setSolvedFileKey('');
    setFile(selected); setPreview(URL.createObjectURL(selected)); setPreviewAvailable(true); setAnalysis(null); setResult(null); setQuestionView(null); setError(''); setState('image_selected');
  };
  const changed = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    if (selected) select(selected);
    event.target.value = '';
  };
  const reset = () => {
    if (preview) revokeBlobPreview(preview);
    selectedFileKeyRef.current = '';
    setSelectedFileKey('');
    setSolvedFileKey('');
    setFile(null); setPreview(''); setPreviewAvailable(false); setAnalysis(null); setResult(null); setQuestionView(null); setError(''); setState('idle');
  };
  const createLesson = async (value: VisionAnalysis, solveFileKey = selectedFileKeyRef.current) => {
    setState('planning');
    try {
      const action = `generate:${value.request_id}`;
      const generated = await generateLesson(value, idempotency.current.keyFor(action));
      idempotency.current.settle(action, 'answered');
      // Görsel bu arada değiştirildiyse eski sorunun dersi yeni ekranın üzerine yazılmaz.
      if (solveFileKey && selectedFileKeyRef.current !== solveFileKey) return false;
      if (generated.verification.status === 'failed') throw new LessonApiError('math_verification_failed');
      setState('rendering'); setResult(generated); setState('success');
      if (solveFileKey && selectedFileKeyRef.current === solveFileKey) setSolvedFileKey(solveFileKey);
      setLessonScrollSignal((current) => current + 1);
      return true;
    } catch (caught) {
      const code = caught instanceof LessonApiError ? caught.code : 'lesson_error';
      idempotency.current.settle(`generate:${value.request_id}`, outcomeOf(code));
      if (solveFileKey && selectedFileKeyRef.current !== solveFileKey) return false;
      setError(ERRORS[code] ?? ERRORS.lesson_error); setState('error');
      return false;
    }
  };
  const solve = async () => {
    if (!file) return;
    const solveFileKey = selectedFileKeyRef.current;
    setError(''); setAnalysis(null); setResult(null); setQuestionView(null); setState('uploading');
    try {
      const value = await analyzeQuestionImage(file, () => setState('analyzing'), undefined, idempotency.current.keyFor(`analyze:${solveFileKey}`));
      idempotency.current.settle(`analyze:${solveFileKey}`, 'answered');
      // Eski görselin geç gelen yanıtı, öğrenci görseli değiştirdiyse yok sayılır.
      if (selectedFileKeyRef.current !== solveFileKey) return;
      setAnalysis(value);
      if (!previewAvailable && value.normalized_preview_url) { setPreview(value.normalized_preview_url); setPreviewAvailable(true); }
      if (!value.is_valid_question || value.image_status !== 'valid_math_question') {
        const status = value.image_status === 'valid_math_question' ? 'unreadable' : value.image_status;
        setError(INVALID_QUESTION_MESSAGES[status]); setState('error'); return;
      }
      // Olağan soru doğrudan çözülür; yalnızca sonuca bağlı ve çözülemeyen bir belirsizlikte sorulur.
      const view = questionState(value.integrity);
      if (view.kind !== 'proceed') { setQuestionView(view); setState('clarifying'); return; }
      await createLesson(value, solveFileKey);
    } catch (caught) {
      const code = caught instanceof VisionApiError ? caught.code : 'network_error';
      idempotency.current.settle(`analyze:${solveFileKey}`, outcomeOf(code));
      if (selectedFileKeyRef.current !== solveFileKey) return;
      setError(ERRORS[code] ?? ERRORS.network_error); setState('error');
    }
  };
  const answerClarification = async (uncertaintyId: string, selection: string) => {
    if (!analysis || clarifying) return;
    const solveFileKey = selectedFileKeyRef.current;
    setClarifying(true); setError('');
    try {
      const updated = await clarifyQuestion(analysis.request_id, { expected_revision: analysis.revision ?? 1, uncertainty_id: uncertaintyId, selection });
      if (selectedFileKeyRef.current !== solveFileKey) return;
      setAnalysis(updated);
      const view = questionState(updated.integrity);
      if (view.kind === 'proceed') { setQuestionView(null); await createLesson(updated, solveFileKey); }
      else setQuestionView(view);
    } catch (caught) {
      const code = caught instanceof VisionApiError ? caught.code : 'network_error';
      if (selectedFileKeyRef.current === solveFileKey) setError(ERRORS[code] ?? ERRORS.network_error);
    } finally {
      setClarifying(false);
    }
  };
  const pasted = (event: ClipboardEvent<HTMLElement>) => {
    const image = Array.from(event.clipboardData.files).find((item) => item.type.startsWith('image/'));
    if (image && !busy) { event.preventDefault(); select(image); }
  };

  const handlePreviewError = () => {
    if (!file || !preview.startsWith('blob:')) return;
    setPreviewAvailable(false);
  };

  if (loading) return <p role="status">Oturum kontrol ediliyor…</p>;
  if (!user) return <main><p>Soru çözmek için oturum aç.</p><Link href="/login">Oturum aç</Link></main>;
  return <div className={`solvePage solveState-${state}`} onPaste={pasted}>
    <input ref={cameraRef} className="visuallyHidden" type="file" accept="image/*" capture="environment" onChange={changed} disabled={busy} aria-label="Arka kamerayla soru fotoğrafı çek" />
    <input ref={galleryRef} className="visuallyHidden" type="file" accept="image/*" onChange={changed} disabled={busy} aria-label="Galeriden soru görseli seç" />
    <input ref={fileRef} className="visuallyHidden" type="file" accept="image/jpeg,image/jpg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif" onChange={changed} disabled={busy} aria-label="Dosyadan soru görseli seç" />
    <header className="solveAppTop" aria-label="Çözüm ekranı">
      <div className="solveAppIdentity">
        <BrandMark size="sm" />
        <div>
          <span>TeacherAI</span>
          <strong>{stateLabel}</strong>
        </div>
      </div>
      <button type="button" className="ghostButton solveResetTop" onClick={reset} disabled={!file || busy}>Temizle</button>
    </header>
    <header className="solveIntro">
      <div className="mascotLockup" aria-label="TeacherAI, senin yapay zekâ öğretmenin">
        <BrandMark size="lg" />
        <strong>TeacherAI</strong>
        <span>Senin yapay zekâ öğretmenin</span>
      </div>
      <p className="eyebrow">Matematik öğretmenin yanında</p>
      <h1>Matematik sorunu göster</h1>
      <p>Birlikte adım adım çözelim.</p>
      <div className="solveProgressPills" aria-label="Çözüm akışı">
        <span className={file ? 'done' : ''}>Görsel</span>
        <span className={analysis ? 'done' : busy ? 'active' : ''}>Analiz</span>
        <span className={result ? 'done' : state === 'planning' || state === 'rendering' ? 'active' : ''}>Çözüm</span>
      </div>
    </header>
    <div className="solveGrid">
      <section className="solveInput" aria-label="Soru görseli">
        {!file ? <UploadCard disabled={busy} dragging={dragging} onDraggingChange={setDragging} onFile={select} onCamera={() => cameraRef.current?.click()} onGallery={() => galleryRef.current?.click()} onFilePicker={() => fileRef.current?.click()} /> : <ImagePreview file={file} previewUrl={preview} previewAvailable={previewAvailable} disabled={busy} onRemove={reset} onReplace={() => galleryRef.current?.click()} onPreviewError={handlePreviewError} />}
        {error && <ErrorBanner message={error} />}
        {state === 'clarifying' && questionView && questionView.kind !== 'proceed' && <ClarificationPanel state={questionView} pending={clarifying} onSelect={answerClarification} onRetake={() => cameraRef.current?.click()} onReplace={() => galleryRef.current?.click()} />}
        {invalidAnalysis && <div className="invalidImageActions"><button type="button" className="primaryButton" onClick={() => cameraRef.current?.click()}>📷 Tekrar Çek</button><button type="button" className="secondaryButton" onClick={() => galleryRef.current?.click()}>Başka Görsel Seç</button></div>}
        {error && analysis?.is_valid_question && !result && <button className="secondaryButton retryButton" onClick={() => createLesson(analysis)}>Yeniden incele</button>}
        <div className="solveActions"><button className="primaryButton analyzeButton" onClick={solve} disabled={!file || busy}>{solvedCurrentImage ? 'Yeniden Çöz' : 'Soruyu Çöz'}</button><button className="secondaryButton" onClick={reset} disabled={!file || busy}>Temizle</button></div>
        <p className="privacyNote">Görsel işlemden sonra geçici depolamadan silinir.</p>
      </section>
      <aside className="solveOutput" aria-label="TeacherAI anlatımı">
        {busy && <AnalysisLoading key={state} uploading={state === 'uploading'} stage={state} />}
        {!busy && !result && !error && state !== 'clarifying' && (
          <div className="resultEmpty solutionPlaceholder">
            <BrandMark size="lg" />
            <span>Çözüm alanı</span>
            <h2>Çözümün burada görünecek</h2>
            <p>TeacherAI sorunu çözdüğünde kullanılan kuralı, çözüm adımlarını ve dikkat etmen gereken noktaları burada anlatacak.</p>
          </div>
        )}
        {result && (
          <div className="solutionMobileScreen">
            <section className="solutionOverview">
              <div>
                <span>{result.lesson.source_analysis.topic}</span>
                {result.lesson.source_analysis.subtopic && <span>{result.lesson.source_analysis.subtopic}</span>}
              </div>
              <h2>Çözüm</h2>
              <p>Matematiksel kontrolün sonucunu ve çözüm adımlarını aşağıda inceleyebilirsin.</p>
            </section>
            <div ref={lessonStartRef} className="lessonScrollTarget" aria-hidden="true" />
            <TeacherBoard result={result} />
            {mismatch && <p className="choiceMismatch" role="note">{mismatch}</p>}
            <section key={result.lesson.lesson_plan_id} className="afterSolutionActions" aria-label="Çözüm sonrası işlemler">
              <InteractionPanel lesson={result.lesson} />
              <ShareSolution result={result} />
              <button className="textToggle" onClick={() => setShowText(!showText)} aria-expanded={showText}>{showText ? 'Metin anlatımını gizle' : 'Metin olarak göster'}</button>
              {showText && <LessonText lesson={result.lesson} />}
              <SolutionFeedback result={result} />
            </section>
            {process.env.NEXT_PUBLIC_TEACHERAI_DEBUG === 'true' && <details className="technicalDetails"><summary>Teknik detaylar</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>}
          </div>
        )}
      </aside>
    </div>
  </div>;
}
