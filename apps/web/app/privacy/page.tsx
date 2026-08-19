import Link from 'next/link';

export const metadata = { title: 'Privacy | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">Privacy</p>
        <h1>Privacy and trust</h1>
        <p>Privacy, consent, and data controls will protect students, teachers, and schools.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
