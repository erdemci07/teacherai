"use client";

import React from "react";
import Link from "next/link";
import { useAuth } from "../auth/AuthProvider";
import { Logo } from "./Logo";

const items = [
  { href: "/solve", label: "Soru Çöz" },
  { href: "/history", label: "Geçmiş" },
  { href: "/dashboard", label: "Panelim" },
  { href: "/about", label: "Hakkımızda" },
] as const;

export function Navigation(): JSX.Element {
  const { user, loading, logout } = useAuth();

  return (
    <header className="siteHeader">
      <nav className="navShell" aria-label="Ana menü">
        <Link href="/" className="logoLink">
          <Logo />
        </Link>

        <div className="navLinks">
          {items.map((x) => (
            <Link href={x.href} key={x.href}>
              {x.label}
            </Link>
          ))}
        </div>

        <div className="navActions">
          {!loading && user ? (
            <button className="ghostButton navLogout" onClick={logout}>
              Çıkış yap
            </button>
          ) : (
            <Link href="/login" className="ghostButton">
              Giriş yap
            </Link>
          )}

          <Link href="/solve" className="primaryButton">
            Soru yükle
          </Link>
        </div>
      </nav>
    </header>
  );
}
