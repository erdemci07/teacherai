import Link from 'next/link';

export const metadata = { title: 'About | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">About</p>
        <h1>About TeacherAI</h1>
        <p>TeacherAI is being built as a long-term AI education platform for teacher-quality instruction.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
