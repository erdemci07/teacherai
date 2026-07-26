import Link from 'next/link';

export const metadata = { title: 'Teacher Portal | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">Teacher Portal</p>
        <h1>Teacher workspace</h1>
        <p>Review queues, explanations, corrections, teaching styles, and datasets will live here.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
