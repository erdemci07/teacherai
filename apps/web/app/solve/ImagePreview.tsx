interface ImagePreviewProps {
  file: File;
  previewUrl: string;
  disabled: boolean;
  onRemove: () => void;
  onReplace: () => void;
}

function formatBytes(bytes: number) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ImagePreview({ file, previewUrl, disabled, onRemove, onReplace }: ImagePreviewProps) {
  const previewable = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'].includes(file.type.toLowerCase());
  return (
    <div className="imagePreview">
      {previewable ? (
        <>
          {/* A blob URL is required here because the image has not left the browser yet. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={previewUrl} alt="Yüklenen matematik sorusunun önizlemesi" />
        </>
      ) : (
        <div className="genericImagePreview" role="img" aria-label="Seçilen görsel dosyası">
          <strong>Görsel seçildi</strong>
          <span>Önizleme bu tarayıcıda desteklenmeyebilir.</span>
        </div>
      )}
      <div className="fileMeta">
        <div><strong>{file.name}</strong><span>{formatBytes(file.size)}</span></div>
        <div className="previewActions">
          <button type="button" className="textButton" onClick={onReplace} disabled={disabled}>Değiştir</button>
          <button type="button" className="textButton dangerText" onClick={onRemove} disabled={disabled}>Sil</button>
        </div>
      </div>
    </div>
  );
}
