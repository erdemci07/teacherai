'use client';

import { ChangeEvent, ClipboardEvent, useEffect, useRef, useState } from 'react';
import { analyzeQuestionImage, ImageStatus, VisionAnalysis, VisionApiError } from '../lib/vision-api';
import { generateLesson, GeneratedLesson, LessonApiError } from '../lib/lesson-api';
import { saveLesson } from '../lib/student-api';
import { InteractionPanel } from './InteractionPanel';
import { AnalysisLoading } from './AnalysisLoading';
import { ErrorBanner } from './ErrorBanner';
import { ImagePreview } from './ImagePreview';
import { UploadCard } from './UploadCard';
import { TeacherBoard } from './TeacherBoard';
import { LessonText } from './LessonText';

type SolveState = 'idle' | 'image_selected' | 'uploading' | 'analyzing' | 'planning' | 'rendering' | 'success' | 'error';
const SUPPORTED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
const SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ERRORS: Record<string, string> = {
  image_required: 'Lütfen bir soru görseli seç.',
  unsupported_image_type: 'Bu dosya türünü okuyamıyorum. JPG, JPEG, PNG veya WEBP biçiminde bir görsel deneyebilir misin?',
  image_too_large: 'Bu görsel 10 MB sınırını aşıyor. Daha küçük bir fotoğraf seçebilir misin?',
  invalid_image: 'Bu görseli okuyamadım. Sorunun tamamının net göründüğü başka bir fotoğraf deneyebilir misin?',
  provider_not_configured: 'Öğretmen servisi henüz hazır değil. Biraz sonra tekrar deneyebilirsin.',
  provider_unavailable: 'Şu anda öğretmen servisine ulaşamıyorum. Biraz sonra tekrar deneyebilirsin.',
  lesson_provider_not_configured: 'Öğretmen servisi henüz hazır değil. Biraz sonra tekrar deneyebilirsin.',
  lesson_provider_unavailable: 'Anlatımı şu anda hazırlayamadım. Biraz sonra yeniden deneyebilirsin.',
  verification_contradiction: 'Bu çözüm matematiksel kontrolden geçmedi. Soruyu yeniden inceleyelim.',
  lesson_timeout: 'İnceleme beklediğimden uzun sürdü. Tekrar deneyebilir misin?',
  network_error: 'Şu anda TeacherAI’a ulaşamıyorum. İnternet bağlantını kontrol edip yeniden deneyebilirsin.',
  lesson_error: 'Çözümü şu anda hazırlayamadım. Biraz sonra yeniden deneyebilirsin.',
};
const INVALID_QUESTION_MESSAGES: Record<Exclude<ImageStatus, 'valid_math_question'>, string> = {
  not_math_question: 'Bu görselde çözebileceğim bir matematik sorusu göremedim 🙂 Sorunun bulunduğu kısmı tekrar çekip gönderebilirsin.',
  unreadable: 'Fotoğraf biraz bulanık görünüyor. Soruyu net okuyabilmem için biraz daha yakından ve sabit şekilde tekrar çekebilir misin? 🙂',
  incomplete_question: 'Sorunun bir kısmı kadraj dışında kalmış gibi görünüyor. Sorunun tamamını görebileceğim şekilde tekrar çekebilir misin? 🙂',
};

export function SolveWorkspace() {
  const [state, setState] = useState<SolveState>('idle');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [analysis, setAnalysis] = useState<VisionAnalysis | null>(null);
  const [result, setResult] = useState<GeneratedLesson | null>(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const [showText, setShowText] = useState(false);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const busy = state === 'uploading' || state === 'analyzing' || state === 'planning' || state === 'rendering';
  const invalidAnalysis = analysis && !analysis.is_valid_question ? analysis : null;

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const select = (selected: File) => {
    const mediaType = selected.type.toLowerCase();
    const extension = selected.name.includes('.') ? `.${selected.name.split('.').pop()?.toLowerCase()}` : '';
    const supported = SUPPORTED_TYPES.includes(mediaType) || (!mediaType && SUPPORTED_EXTENSIONS.includes(extension));
    if (!supported) { setError(ERRORS.unsupported_image_type); setState('error'); return; }
    if (selected.size > MAX_FILE_BYTES) { setError(ERRORS.image_too_large); setState('error'); return; }
    if (preview) URL.revokeObjectURL(preview);
    setFile(selected); setPreview(URL.createObjectURL(selected)); setAnalysis(null); setResult(null); setError(''); setState('image_selected');
  };
  const changed = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    if (selected) select(selected);
    event.target.value = '';
  };
  const reset = () => {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null); setPreview(''); setAnalysis(null); setResult(null); setError(''); setState('idle');
  };
  const createLesson = async (value: VisionAnalysis) => {
    setState('planning');
    try {
      const generated = await generateLesson(value);
      setState('rendering'); setResult(generated); void saveLesson(generated).catch(() => undefined); setState('success');
    } catch (caught) {
      const code = caught instanceof LessonApiError ? caught.code : 'lesson_error';
      setError(ERRORS[code] ?? ERRORS.lesson_error); setState('error');
    }
  };
  const solve = async () => {
    if (!file) return;
    setError(''); setAnalysis(null); setResult(null); setState('uploading');
    try {
      const value = await analyzeQuestionImage(file, () => setState('analyzing'));
      setAnalysis(value);
      if (!value.is_valid_question || value.image_status !== 'valid_math_question') {
        const status = value.image_status === 'valid_math_question' ? 'unreadable' : value.image_status;
        setError(INVALID_QUESTION_MESSAGES[status]); setState('error'); return;
      }
      await createLesson(value);
    } catch (caught) {
      const code = caught instanceof VisionApiError ? caught.code : 'network_error';
      setError(ERRORS[code] ?? ERRORS.network_error); setState('error');
    }
  };
  const pasted = (event: ClipboardEvent<HTMLElement>) => {
    const image = Array.from(event.clipboardData.files).find((item) => item.type.startsWith('image/'));
    if (image && !busy) { event.preventDefault(); select(image); }
  };

  return <div className="solvePage" onPaste={pasted}>
    <input ref={cameraRef} className="visuallyHidden" type="file" accept="image/*" capture="environment" onChange={changed} disabled={busy} aria-label="Arka kamerayla soru fotoğrafı çek" />
    <input ref={galleryRef} className="visuallyHidden" type="file" accept="image/*" onChange={changed} disabled={busy} aria-label="Galeriden soru görseli seç" />
    <input ref={fileRef} className="visuallyHidden" type="file" accept="image/jpeg,image/jpg,image/png,image/webp,.jpg,.jpeg,.png,.webp" onChange={changed} disabled={busy} aria-label="Dosyadan soru görseli seç" />
    <header className="solveIntro"><p className="eyebrow">Matematik öğretmenin yanında</p><h1>Sorunu yükle,<br /><span>mantığını birlikte öğrenelim.</span></h1><p>Fotoğrafını çek veya galeriden seç. TeacherAI soruyu inceler, kontrol eder ve adım adım anlatır.</p></header>
    <div className="solveGrid">
      <section className="solveInput" aria-label="Soru görseli">
        {!file ? <UploadCard disabled={busy} dragging={dragging} onDraggingChange={setDragging} onFile={select} onCamera={() => cameraRef.current?.click()} onGallery={() => galleryRef.current?.click()} onFilePicker={() => fileRef.current?.click()} /> : <ImagePreview file={file} previewUrl={preview} disabled={busy} onRemove={reset} onReplace={() => galleryRef.current?.click()} />}
        {error && <ErrorBanner message={error} />}
        {invalidAnalysis && <div className="invalidImageActions"><button type="button" className="primaryButton" onClick={() => cameraRef.current?.click()}>📷 Tekrar Çek</button><button type="button" className="secondaryButton" onClick={() => galleryRef.current?.click()}>Başka Görsel Seç</button></div>}
        {error && analysis?.is_valid_question && !result && <button className="secondaryButton retryButton" onClick={() => createLesson(analysis)}>Yeniden incele</button>}
        <div className="solveActions"><button className="primaryButton analyzeButton" onClick={solve} disabled={!file || busy}>Soruyu Çöz</button><button className="secondaryButton" onClick={reset} disabled={!file || busy}>Temizle</button></div>
        <p className="privacyNote">Görsel işlemden sonra geçici depolamadan silinir.</p>
      </section>
      <aside className="solveOutput" aria-label="TeacherAI anlatımı">{busy && <AnalysisLoading uploading={state === 'uploading'} stage={state} />}{!busy && !result && !error && <div className="resultEmpty"><span>✦</span><h2>Çözümün burada görünecek</h2><p>TeacherAI kullanılan kuralı, çözüm adımlarını ve dikkat etmen gereken noktaları burada anlatacak.</p></div>}{result && <><TeacherBoard result={result} /><InteractionPanel lesson={result.lesson} /><button className="textToggle" onClick={() => setShowText(!showText)} aria-expanded={showText}>{showText ? 'Metin anlatımını gizle' : 'Metin olarak göster'}</button>{showText && <LessonText lesson={result.lesson} />}{process.env.NEXT_PUBLIC_TEACHERAI_DEBUG === 'true' && <details className="technicalDetails"><summary>Teknik detaylar</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>}</>}</aside>
    </div>
  </div>;
}
