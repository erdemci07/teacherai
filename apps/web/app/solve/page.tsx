import Link from 'next/link';

export const metadata = { title: 'Solve | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">Solve</p>
        <h1>Upload Area Placeholder</h1>
        <p>Student question upload and lesson generation will be introduced after the core engines are implemented.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
