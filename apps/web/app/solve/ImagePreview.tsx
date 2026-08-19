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
  return (
    <div className="imagePreview">
      {/* A blob URL is required here because the image has not left the browser yet. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={previewUrl} alt="Yüklenen matematik sorusunun önizlemesi" />
      <div className="fileMeta">
        <div><strong>{file.name}</strong><span>{formatBytes(file.size)}</span></div>
        <div className="previewActions">
          <button type="button" className="textButton" onClick={onReplace} disabled={disabled}>Değiştir</button>
          <button type="button" className="textButton dangerText" onClick={onRemove} disabled={disabled}>Kaldır</button>
        </div>
      </div>
    </div>
  );
}
