import Link from 'next/link';

export const metadata = { title: 'History | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">History</p>
        <h1>Learning history</h1>
        <p>Submitted questions, generated lessons, and practice history will appear here.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
