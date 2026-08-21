interface ImagePreviewProps {
  file: File;
  previewUrl: string;
  previewAvailable: boolean;
  previewPreparing: boolean;
  disabled: boolean;
  onRemove: () => void;
  onReplace: () => void;
  onPreviewError: () => void;
}

function formatBytes(bytes: number) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ImagePreview({ file, previewUrl, previewAvailable, previewPreparing, disabled, onRemove, onReplace, onPreviewError }: ImagePreviewProps) {
  return (
    <div className="imagePreview">
      {previewAvailable && previewUrl ? (
        <>
          {/* A blob URL is required here because the image has not left the browser yet. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={previewUrl} alt="Yüklenen matematik sorusunun önizlemesi" onError={onPreviewError} />
        </>
      ) : (
        <div className="genericImagePreview" role="img" aria-label="Seçilen görsel dosyası">
          <strong>{previewPreparing ? 'Görsel hazırlanıyor...' : 'Görsel seçildi'}</strong>
          <span>{previewPreparing ? 'Önizleme birazdan görünecek.' : 'Önizleme bu tarayıcıda desteklenmeyebilir.'}</span>
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
