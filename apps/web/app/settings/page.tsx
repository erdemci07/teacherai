import Link from 'next/link';

export const metadata = { title: 'Settings | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">Settings</p>
        <h1>Account settings</h1>
        <p>Profile, accessibility, notification, and learning preferences will be managed here.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
