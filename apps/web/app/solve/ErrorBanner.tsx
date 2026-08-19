interface ErrorBannerProps {
  message: string;
}

export function ErrorBanner({ message }: ErrorBannerProps) {
  return (
    <div className="solveError" role="alert" aria-live="assertive">
      <strong>İşlem tamamlanamadı</strong>
      <span>{message}</span>
    </div>
  );
}
