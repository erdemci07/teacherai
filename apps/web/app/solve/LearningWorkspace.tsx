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

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// TA-007: büyütülmüş tahta modal davranır: arka plan `inert` olur (ekran okuyucu ve klavye erişemez), Tab odağı
// tahta içinde döner, Escape kapatır ve odak büyütme düğmesine geri döner.
export function inertOutside(element: HTMLElement): () => void {
  const changed: HTMLElement[] = [];
  let node: HTMLElement | null = element;
  while (node && node.parentElement) {
    for (const sibling of Array.from(node.parentElement.children)) {
      if (sibling !== node && sibling instanceof HTMLElement && !sibling.inert) {
        sibling.inert = true;
        changed.push(sibling);
      }
    }
    node = node.parentElement;
  }
  return () => { for (const item of changed) item.inert = false; };
}

export function nextFocus(items: readonly HTMLElement[], active: Element | null, backwards: boolean): HTMLElement | null {
  if (items.length === 0) return null;
  const first = items[0]!;
  const last = items[items.length - 1]!;
  if (backwards && (active === first || !items.includes(active as HTMLElement))) return last;
  if (!backwards && (active === last || !items.includes(active as HTMLElement))) return first;
  return null;
}

export function ExpandableBoard({ children, initiallyExpanded = false }: { children: ReactNode; initiallyExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const frameRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const frame = frameRef.current;
    const toggle = toggleRef.current;
    if (!expanded || !frame) return;
    const restore = inertOutside(frame);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setExpanded(false); return; }
      if (event.key !== 'Tab') return;
      const items = Array.from(frame.querySelectorAll<HTMLElement>(FOCUSABLE));
      const target = nextFocus(items, document.activeElement, event.shiftKey);
      if (target) { event.preventDefault(); target.focus(); }
    };
    window.addEventListener('keydown', onKey);
    toggle?.focus();
    return () => {
      window.removeEventListener('keydown', onKey);
      restore();
      toggle?.focus();
    };
  }, [expanded]);

  return (
    <section ref={frameRef} className="taBoardFrame" data-expanded={expanded ? 'true' : 'false'} aria-label="Çözüm tahtası"
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
