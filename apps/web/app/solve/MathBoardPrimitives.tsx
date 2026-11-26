import type { IntervalView } from '../lib/math-board.ts';

// TA-008: tahtanın matematik öğeleri. SVG yalnız bu bileşende, doğrulanmış sayısal değerlerden üretilir;
// sağlayıcıdan gelen SVG/HTML/betik hiçbir zaman çizilmez.

export function intervalText(item: IntervalView): string {
  const lower = item.lower ?? '−∞';
  const upper = item.upper ?? '+∞';
  if (item.lower !== null && item.lower === item.upper) return `{${item.lower}}`;
  return `${item.lower_closed ? '[' : '('}${lower}, ${upper}${item.upper_closed ? ']' : ')'}`;
}

export function numericValue(text: string | null): number | null {
  if (text === null) return null;
  const fraction = /^(-?\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?)$/.exec(text.trim());
  if (fraction) return Number(fraction[1]) / Number(fraction[2]);
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

export function NumberLine({ variable, intervals, exclusions }: { variable: string; intervals: IntervalView[]; exclusions: string[] }) {
  const values = intervals.flatMap((item) => [numericValue(item.lower), numericValue(item.upper)]).filter((v): v is number => v !== null);
  const low = Math.min(...values, 0) - 2;
  const high = Math.max(...values, 0) + 2;
  const scale = (value: number) => 10 + ((value - low) / (high - low || 1)) * 180;
  const label = `${variable} ∈ ${intervals.map(intervalText).join(' ∪ ')}`;
  return (
    <figure className="boardNumberLine">
      <svg viewBox="0 0 200 40" role="img" aria-label={`Sayı doğrusu: ${label}`}>
        <line x1="4" y1="20" x2="196" y2="20" className="axis" />
        {intervals.map((item, index) => {
          const a = numericValue(item.lower);
          const b = numericValue(item.upper);
          const x1 = a === null ? 4 : scale(a);
          const x2 = b === null ? 196 : scale(b);
          return (
            <g key={index}>
              <line x1={x1} y1="20" x2={x2} y2="20" className="range" />
              {a !== null && <circle cx={x1} cy="20" r="3.5" className={item.lower_closed ? 'closed' : 'open'} />}
              {b !== null && b !== a && <circle cx={x2} cy="20" r="3.5" className={item.upper_closed ? 'closed' : 'open'} />}
              {a !== null && <text x={x1} y="36" textAnchor="middle">{item.lower}</text>}
              {b !== null && b !== a && <text x={x2} y="36" textAnchor="middle">{item.upper}</text>}
            </g>
          );
        })}
      </svg>
      <figcaption>{label}{exclusions.length > 0 && ` (tanımsız: ${exclusions.join(', ')})`}</figcaption>
    </figure>
  );
}

export function GeometryFacts({ note, facts, schematic }: { note: string | null; facts: string[]; schematic: boolean }) {
  return (
    <section className="boardItem board-geometry_facts" aria-label="Geometri olguları">
      <small>Şekildeki bilgiler{schematic && <span className="taBadge">ölçekli değil</span>}</small>
      {note && <p>{note}</p>}
      <ul>{facts.map((fact, index) => <li key={index}>{fact}</li>)}</ul>
    </section>
  );
}

// TA-009 §16: fizik tahtası yalnız sunucunun kurduğu veya açıkça etiketlediği öğeleri listeler; çizim üretilmez.
export function PhysicsFacts({ note, facts }: { note: string | null; facts: string[] }) {
  return (
    <section className="boardItem board-physics_facts" aria-label="Fizik doğrulaması">
      <small>Fiziksel model<span className="taBadge">ölçekli değildir</span></small>
      {note && <p>{note}</p>}
      <ul>{facts.map((fact, index) => <li key={index}>{fact}</li>)}</ul>
    </section>
  );
}
