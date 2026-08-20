import { DragEvent, KeyboardEvent } from 'react';

interface UploadCardProps {
  disabled: boolean;
  dragging: boolean;
  onDraggingChange: (dragging: boolean) => void;
  onFile: (file: File) => void;
  onCamera: () => void;
  onGallery: () => void;
  onFilePicker: () => void;
}

export function UploadCard({ disabled, dragging, onDraggingChange, onFile, onCamera, onGallery, onFilePicker }: UploadCardProps) {
  const dropped = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    onDraggingChange(false);
    const file = event.dataTransfer.files[0];
    if (file && !disabled) onFile(file);
  };
  const keyed = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (!disabled) onFilePicker();
    }
  };

  return <div className={`uploadCard ${dragging ? 'dragging' : ''}`} role="button" tabIndex={disabled ? -1 : 0} aria-label="Soru fotoğrafını sürükle veya dosya seç" aria-disabled={disabled} onClick={() => !disabled && onFilePicker()} onKeyDown={keyed} onDragEnter={(event) => { event.preventDefault(); onDraggingChange(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => onDraggingChange(false)} onDrop={dropped}>
    <span className="uploadGlyph" aria-hidden="true">＋</span><h2>Soru fotoğrafını ekle</h2>
    <p className="desktopUploadText">Fotoğrafı buraya sürükle veya aşağıdan bir yöntem seç. Görseli <strong>Ctrl+V / Cmd+V</strong> ile de yapıştırabilirsin.</p>
    <div className="uploadChoices">
      <button type="button" className="cameraChoice" onClick={(event) => { event.stopPropagation(); onCamera(); }} disabled={disabled}><span aria-hidden="true">📷</span>Kamerayla Çek</button>
      <button type="button" onClick={(event) => { event.stopPropagation(); onGallery(); }} disabled={disabled}><span aria-hidden="true">🖼️</span>Galeriden Seç</button>
      <button type="button" className="fileChoice" onClick={(event) => { event.stopPropagation(); onFilePicker(); }} disabled={disabled}><span aria-hidden="true">↥</span>Dosya Yükle</button>
    </div>
    <p className="uploadGuidance">En iyi sonuç için sorunun tamamı ve varsa şekil veya grafik net görünsün.</p><span className="formatNote">JPG, PNG, WEBP · En fazla 10 MB</span>
  </div>;
}
