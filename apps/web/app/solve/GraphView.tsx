import type { GraphData } from '../lib/math-board.ts';

// TA-008: grafik tanımsız noktalarda (discontinuities) bölünür; parçalar birleştirilmez. Örnek noktalar yalnız
// gösterimdir, bir özelliğin kanıtı değildir.
export function graphPieces(data: GraphData): [number, number][][] {
  const holes = [...(data.discontinuities ?? [])].sort((a, b) => a - b);
  const pieces: [number, number][][] = [];
  let current: [number, number][] = [];
  let previousX: number | null = null;
  for (const [x, y] of data.sample_points ?? []) {
    const crosses = previousX !== null && holes.some((hole) => previousX! < hole && hole <= x);
    if (!Number.isFinite(y) || crosses) {
      if (current.length > 1) pieces.push(current);
      current = [];
    }
    if (Number.isFinite(y)) current.push([x, y]);
    previousX = x;
  }
  if (current.length > 1) pieces.push(current);
  return pieces;
}

export function GraphView({ data }: { data: GraphData }) {
  const pieces = graphPieces(data);
  if (pieces.length === 0) return <p role="note">Grafik bu soru için çizilemedi.</p>;
  return (
    <svg className="boardGraph" viewBox="0 0 200 200" role="img" aria-label={`${data.expression} fonksiyon grafiği`}>
      <line x1="10" y1="100" x2="190" y2="100" />
      <line x1="100" y1="10" x2="100" y2="190" />
      {pieces.map((piece, index) => (
        <polyline key={index} points={piece.map(([x, y]) => `${100 + x * 25},${100 - y * 18}`).join(' ')} />
      ))}
    </svg>
  );
}
