import Link from 'next/link';

export const metadata = { title: 'Login | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">Login</p>
        <h1>Authentication entry</h1>
        <p>Secure authentication will connect students, teachers, and admins to their portals.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
