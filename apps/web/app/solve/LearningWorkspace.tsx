'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';

// TA-006: aynı ders durumunu telefonda tek sütun, yatay tablet/masaüstünde tahta + etkileşim yan yana gösterir.
// Tahtayı büyütmek yalnız sunum durumudur: yeni ders üretmez, istek veya sağlayıcı çağrısı yapmaz.
export function LearningWorkspace({ board, children }: { board: ReactNode; children: ReactNode }) {
  return (
    <div className="taWorkspace" data-layout="split">
      <ExpandableBoard>{board}</ExpandableBoard>
      <div className="taWorkspaceSide">{children}</div>
    </div>
  );
}

export function ExpandableBoard({ children, initiallyExpanded = false }: { children: ReactNode; initiallyExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setExpanded(false); };
    window.addEventListener('keydown', onKey);
    toggleRef.current?.focus();
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded]);

  return (
    <section className="taBoardFrame" data-expanded={expanded ? 'true' : 'false'} aria-label="Çözüm tahtası"
      {...(expanded ? { role: 'dialog', 'aria-modal': true } : {})}>
      <div className="taBoardBar">
        <button ref={toggleRef} type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Tahtayı küçült' : 'Tahtayı büyüt'}
        </button>
      </div>
      {children}
    </section>
  );
}
