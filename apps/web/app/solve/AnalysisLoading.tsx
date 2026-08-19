interface AnalysisLoadingProps {
  uploading: boolean;
}

export function AnalysisLoading({ uploading }: AnalysisLoadingProps) {
  return (
    <div className="analysisLoading" role="status" aria-live="polite">
      <span className="loadingSpinner" aria-hidden="true" />
      <div>
        <strong>{uploading ? 'Görsel güvenle yükleniyor...' : 'Soruyu inceliyorum...'}</strong>
        <p>{uploading ? 'Dosyanızı analiz için hazırlıyorum.' : 'Matematiksel ifadeler, şekiller ve soru türü belirleniyor.'}</p>
      </div>
    </div>
  );
}
