'use client';

export default function Error({ reset }: { reset: () => void }) {
  return (
    <div className="pageShell narrow">
      <div className="panel centered">
        <p className="eyebrow">Something went wrong</p>
        <h1>TeacherAI could not load this page.</h1>
        <p>Please try again. If the issue continues, the platform team will investigate through application telemetry.</p>
        <button className="primaryButton" onClick={reset}>Try again</button>
      </div>
    </div>
  );
}
