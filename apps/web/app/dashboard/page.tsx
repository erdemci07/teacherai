import Link from 'next/link';

export const metadata = { title: 'Dashboard | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">Dashboard</p>
        <h1>Student dashboard</h1>
        <p>Learning progress, active lessons, and recommendations will be organized here.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
