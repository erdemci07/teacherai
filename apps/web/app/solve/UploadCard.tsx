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

  return (
    <div className={`uploadCard ${dragging ? 'dragging' : ''}`} role="button" tabIndex={disabled ? -1 : 0} aria-label="Soru fotoğrafını sürükle veya dosya seç" aria-disabled={disabled} onClick={() => !disabled && onFilePicker()} onKeyDown={keyed} onDragEnter={(event) => { event.preventDefault(); onDraggingChange(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => onDraggingChange(false)} onDrop={dropped}>
      <div className="uploadHero">
        <img className="uploadMascot" src="/teacherai-mascot.png" alt="" />
        <div>
          <span className="uploadPill">TeacherAI hazır</span>
          <h2>Sorunu göster, birlikte çözelim.</h2>
          <p>Kamerayla çek veya galeriden seç. Çözümü adım adım hazırlayacağım.</p>
        </div>
      </div>
      <div className="uploadChoices uploadActionStack">
        <button type="button" className="cameraChoice uploadActionPrimary" onClick={(event) => { event.stopPropagation(); onCamera(); }} disabled={disabled}>
          <span aria-hidden="true">⌁</span>
          <strong>Kamerayla çek</strong>
          <small>Sorunun fotoğrafını çek</small>
        </button>
        <button type="button" className="uploadActionSecondary" onClick={(event) => { event.stopPropagation(); onGallery(); }} disabled={disabled}>
          <span aria-hidden="true">□</span>
          <strong>Galeriden seç</strong>
          <small>Fotoğraf yükle</small>
        </button>
        <button type="button" className="fileChoice uploadFileChoice" onClick={(event) => { event.stopPropagation(); onFilePicker(); }} disabled={disabled}>
          <span aria-hidden="true">↥</span>
          <strong>Dosyadan yükle</strong>
        </button>
      </div>
      <div className="uploadNotes">
        <p className="desktopUploadText">Masaüstünde fotoğrafı buraya sürükleyebilir veya görseli <strong>Ctrl+V / Cmd+V</strong> ile yapıştırabilirsin.</p>
        <p className="uploadGuidance">Sorunun tamamı, seçenekler ve varsa şekil net görünsün.</p>
        <span className="formatNote">JPG, PNG, WEBP, HEIC, HEIF · En fazla 10 MB</span>
      </div>
    </div>
  );
}
