'use client';

import { ClipboardEvent, useEffect, useRef, useState } from 'react';
import { analyzeQuestionImage, VisionAnalysis, VisionApiError } from '../lib/vision-api';
import { AnalysisLoading } from './AnalysisLoading';
import { AnalysisResult } from './AnalysisResult';
import { ErrorBanner } from './ErrorBanner';
import { ImagePreview } from './ImagePreview';
import { UploadCard } from './UploadCard';

type SolveState = 'idle' | 'image_selected' | 'uploading' | 'analyzing' | 'success' | 'error';
const SUPPORTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ERROR_MESSAGES: Record<string, string> = {
  image_required: 'Lütfen bir soru görseli seçin.',
  unsupported_image_type: 'Bu dosya türü desteklenmiyor. JPG, PNG veya WEBP kullanın.',
  image_too_large: 'Görsel 10 MB sınırını aşıyor. Daha küçük bir görsel seçin.',
  invalid_image: 'Görsel okunamadı. Dosyanın bozuk olmadığını kontrol edin.',
  provider_not_configured: 'Analiz servisi şu anda hazır değil. Lütfen daha sonra tekrar deneyin.',
  provider_unavailable: 'Analiz servisine ulaşılamıyor. Birkaç dakika sonra tekrar deneyin.',
  provider_timeout: 'Analiz beklenenden uzun sürdü. Lütfen tekrar deneyin.',
  invalid_provider_response: 'Soru güvenilir biçimde okunamadı. Daha net bir fotoğrafla tekrar deneyin.',
  request_timeout: 'İstek zaman aşımına uğradı. İnternet bağlantınızı kontrol edip tekrar deneyin.',
  network_error: 'TeacherAI sunucusuna ulaşılamıyor. İnternet bağlantınızı kontrol edin.',
  unexpected_response: 'Beklenmeyen bir sorun oluştu. Lütfen tekrar deneyin.',
};

export function SolveWorkspace() {
  const [state, setState] = useState<SolveState>('idle');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [result, setResult] = useState<VisionAnalysis | null>(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = state === 'uploading' || state === 'analyzing';

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  const selectFile = (selected: File) => {
    if (!SUPPORTED_TYPES.includes(selected.type)) {
      setError(ERROR_MESSAGES.unsupported_image_type); setState('error'); return;
    }
    if (selected.size > MAX_FILE_BYTES) {
      setError(ERROR_MESSAGES.image_too_large); setState('error'); return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(selected); setPreviewUrl(URL.createObjectURL(selected)); setResult(null); setError(''); setState('image_selected');
  };

  const reset = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null); setPreviewUrl(''); setResult(null); setError(''); setState('idle');
  };

  const analyze = async () => {
    if (!file) { setError(ERROR_MESSAGES.image_required); setState('error'); return; }
    setError(''); setResult(null); setState('uploading');
    try {
      const analysis = await analyzeQuestionImage(file, () => setState('analyzing'));
      setResult(analysis); setState('success');
    } catch (caught) {
      const code = caught instanceof VisionApiError ? caught.code : 'unexpected_response';
      setError(ERROR_MESSAGES[code] ?? ERROR_MESSAGES.unexpected_response); setState('error');
    }
  };

  const pasted = (event: ClipboardEvent<HTMLElement>) => {
    const image = Array.from(event.clipboardData.files).find((item) => item.type.startsWith('image/'));
    if (image && !busy) { event.preventDefault(); selectFile(image); }
  };

  return (
    <div className="solvePage" onPaste={pasted}>
      <header className="solveIntro">
        <p className="eyebrow">TeacherAI Vision</p>
        <h1>Sorunu yükle,<br /><span>önce doğru anlayalım.</span></h1>
        <p>Matematik sorununun fotoğrafını çek veya yükle. TeacherAI metni, formülleri ve görsel bağlamı birlikte inceler.</p>
      </header>
      <div className="solveGrid">
        <section className="solveInput" aria-label="Soru görseli yükleme alanı">
          {!file ? <UploadCard inputRef={inputRef} disabled={busy} dragging={dragging} onDraggingChange={setDragging} onFile={selectFile} /> : <ImagePreview file={file} previewUrl={previewUrl} disabled={busy} onRemove={reset} onReplace={() => inputRef.current?.click()} />}
          {file && <input ref={inputRef} className="visuallyHidden" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" aria-label="Soru görselini değiştir" onChange={(event) => { const next = event.target.files?.[0]; if (next) selectFile(next); event.target.value = ''; }} />}
          {error && <ErrorBanner message={error} />}
          <div className="solveActions">
            <button type="button" className="primaryButton analyzeButton" onClick={analyze} disabled={!file || busy}>Soruyu İncele</button>
            <button type="button" className="secondaryButton" onClick={reset} disabled={!file || busy}>Temizle</button>
          </div>
          <p className="privacyNote">Görselin yalnızca analiz sırasında işlenir ve işlemden sonra geçici depolamadan silinir.</p>
        </section>
        <aside className="solveOutput" aria-label="Analiz sonucu">
          {(state === 'idle' || state === 'image_selected' || state === 'error') && !result && <div className="resultEmpty"><span aria-hidden="true">✦</span><h2>Analiz burada görünecek</h2><p>Soru türü, konu, zorluk, formüller ve görsel öğeler yapılandırılmış şekilde sunulur.</p></div>}
          {(state === 'uploading' || state === 'analyzing') && <AnalysisLoading uploading={state === 'uploading'} />}
          {result && <AnalysisResult result={result} />}
        </aside>
      </div>
    </div>
  );
}
