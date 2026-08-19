import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="pageShell narrow">
      <div className="panel centered">
        <p className="eyebrow">404</p>
        <h1>Page not found</h1>
        <p>The page you requested is not available in TeacherAI yet.</p>
        <Link className="primaryButton" href="/">Return home</Link>
      </div>
    </div>
  );
}
