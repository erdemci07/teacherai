import Link from 'next/link';
import { Logo } from './Logo';

const navigationItems = [
  { href: '/solve', label: 'Solve' },
  { href: '/teacher', label: 'Teacher' },
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/about', label: 'About' },
] as const;

export function Navigation() {
  return (
    <header className="siteHeader">
      <nav className="navShell" aria-label="Primary navigation">
        <Link href="/" className="logoLink">
          <Logo />
        </Link>
        <div className="navLinks">
          {navigationItems.map((item) => (
            <Link href={item.href} key={item.href}>
              {item.label}
            </Link>
          ))}
        </div>
        <div className="navActions">
          <Link href="/login" className="ghostButton">Log in</Link>
          <Link href="/solve" className="primaryButton">Upload question</Link>
        </div>
      </nav>
    </header>
  );
}
