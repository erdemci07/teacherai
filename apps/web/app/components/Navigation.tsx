'use client';

import Link from 'next/link';
import { useAuth } from '../auth/AuthProvider';
import { Logo } from './Logo';

export function Navigation() {
  const { user, loading, logout } = useAuth();

  return (
    <header className="siteHeader">
      <nav className="navShell appHeaderShell" aria-label="Ana menü">
        <Link href="/" className="logoLink appHeaderBrand">
          <Logo />
        </Link>
        <div className="appHeaderActions">
          {!loading && user ? (
            <button className="ghostButton navLogout" onClick={logout}>Çıkış</button>
          ) : (
            <Link href="/login" className="ghostButton">Giriş</Link>
          )}
          <Link href="/solve" className="primaryButton navSolve">Soru Çöz</Link>
        </div>
      </nav>
    </header>
  );
}
