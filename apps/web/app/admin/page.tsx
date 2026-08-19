import Link from 'next/link';

export const metadata = { title: 'Admin Portal | TeacherAI' };

export default function Page() {
  return (
    <div className="pageShell narrow">
      <div className="panel">
        <p className="eyebrow">Admin Portal</p>
        <h1>Admin workspace</h1>
        <p>Tenant, provider, model, feature, and policy administration will live here.</p>
        <div className="placeholderActions">
          <Link className="primaryButton" href="/">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
