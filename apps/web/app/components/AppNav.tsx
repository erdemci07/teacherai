'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { NAV_ITEMS, isCurrent } from '../lib/learning';

const STORAGE_KEY = 'teacherai.nav.collapsed';

// TA-006: telefonda alt gezinme, masaüstünde daraltılabilir kenar çubuğu. Fare/hover varsayılmaz; bütün hedefler
// en az 44 px'tir. Yalnız oturum açık öğrenciye gösterilir; çalışmayan özellik menüde yer almaz.
export function AppNav() {
  const { user, loading } = useAuth();
  const pathname = usePathname() ?? '/';
  // Bileşen yalnız istemcide, oturum yüklendikten sonra çizilir; bu yüzden ilk değer depodan okunabilir.
  const [collapsed, setCollapsed] = useState(() => {
    try { return typeof window !== 'undefined' && window.localStorage.getItem(STORAGE_KEY) === 'true'; } catch { return false; }
  });

  if (loading || !user) return null;

  function toggle() {
    const next = !collapsed;
    setCollapsed(next);
    try { window.localStorage.setItem(STORAGE_KEY, String(next)); } catch { /* yoksay */ }
  }

  return (
    <>
      <nav className="taRail taSurface" aria-label="Öğrenme menüsü" data-collapsed={collapsed ? 'true' : 'false'}>
        {NAV_ITEMS.map((item) => (
          <Link key={item.href} href={item.href} aria-current={isCurrent(pathname, item.href) ? 'page' : undefined}>
            <span aria-hidden="true">{item.icon}</span>
            <span className="taRailLabel">{item.label}</span>
          </Link>
        ))}
        <button type="button" className="taRailToggle" onClick={toggle} aria-expanded={!collapsed}>
          <span aria-hidden="true">{collapsed ? '»' : '«'}</span>
          <span className="taRailLabel">{collapsed ? 'Menüyü genişlet' : 'Menüyü daralt'}</span>
        </button>
      </nav>
      <nav className="taBottomNav taSurface" aria-label="Öğrenme menüsü (mobil)">
        {NAV_ITEMS.map((item) => (
          <Link key={item.href} href={item.href} aria-current={isCurrent(pathname, item.href) ? 'page' : undefined}>
            <span aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}
