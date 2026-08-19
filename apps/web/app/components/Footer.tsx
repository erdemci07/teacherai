import Link from 'next/link';
import { Logo } from './Logo';

export function Footer() {
  return (
    <footer className="footer">
      <div className="footerGrid">
        <div>
          <Logo />
          <p>TeacherAI is built to teach mathematics like an experienced teacher, with structured lessons, reviewable outputs, and scalable learning systems.</p>
        </div>
        <div>
          <h3>Platform</h3>
          <Link href="/solve">Solve</Link>
          <Link href="/history">History</Link>
          <Link href="/dashboard">Dashboard</Link>
        </div>
        <div>
          <h3>Portals</h3>
          <Link href="/teacher">Teacher Portal</Link>
          <Link href="/admin">Admin Portal</Link>
          <Link href="/settings">Settings</Link>
        </div>
        <div>
          <h3>Company</h3>
          <Link href="/about">About</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/login">Login</Link>
        </div>
      </div>
      <div className="footerBottom">© 2026 TeacherAI. Built for long-term learning.</div>
    </footer>
  );
}
