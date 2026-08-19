import { ChangeEvent, DragEvent, KeyboardEvent, RefObject } from 'react';

interface UploadCardProps {
  inputRef: RefObject<HTMLInputElement | null>;
  disabled: boolean;
  dragging: boolean;
  onDraggingChange: (dragging: boolean) => void;
  onFile: (file: File) => void;
}

export function UploadCard({ inputRef, disabled, dragging, onDraggingChange, onFile }: UploadCardProps) {
  const choose = () => !disabled && inputRef.current?.click();
  const changed = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) onFile(file);
    event.target.value = '';
  };
  const dropped = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    onDraggingChange(false);
    const file = event.dataTransfer.files[0];
    if (file && !disabled) onFile(file);
  };
  const keyed = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose();
    }
  };

  return (
    <div
      className={`uploadCard ${dragging ? 'dragging' : ''}`}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label="Soru görseli seç"
      aria-disabled={disabled}
      onClick={choose}
      onKeyDown={keyed}
      onDragEnter={(event) => { event.preventDefault(); onDraggingChange(true); }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => onDraggingChange(false)}
      onDrop={dropped}
    >
      <input
        ref={inputRef}
        className="visuallyHidden"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        onChange={changed}
        disabled={disabled}
        aria-label="Kameradan çek veya soru görseli seç"
      />
      <span className="uploadGlyph" aria-hidden="true">↑</span>
      <h2>Soru görselini buraya bırak</h2>
      <p>Dosya seçmek veya kamerayı açmak için dokun. Bilgisayarda görseli <strong>Ctrl+V / Cmd+V</strong> ile de yapıştırabilirsin.</p>
      <span className="formatNote">JPG, PNG, WEBP · En fazla 10 MB</span>
    </div>
  );
}
