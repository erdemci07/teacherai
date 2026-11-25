import type { GraphData } from '../lib/math-board.ts';

// TA-008: grafik tanımsız noktalarda (discontinuities) bölünür; parçalar birleştirilmez. Örnek noktalar yalnız
// gösterimdir, bir özelliğin kanıtı değildir.
// TA-008B: sunucunun doğruladığı parça sınırlarında da bölünür; delik açık daire, asimptot kesikli çizgi, tanım
// kümesinin pencere içindeki uç noktaları kapalı (dolu) veya açık daireyle gösterilir. Çizim dışı (çok büyük) değer
// parçayı böler; asimptot yakınında dikey birleştirme çizgisi oluşmaz.
const WINDOW = 10;
const Y_LIMIT = 50;

export function graphPieces(data: GraphData): [number, number][][] {
  const cuts = [...(data.discontinuities ?? []), ...(data.segments ?? []).flatMap((segment) => [segment.start, segment.end])]
    .sort((a, b) => a - b);
  const pieces: [number, number][][] = [];
  let current: [number, number][] = [];
  let previousX: number | null = null;
  for (const [x, y] of data.sample_points ?? []) {
    const visible = Number.isFinite(y) && Math.abs(y) <= Y_LIMIT;
    const crosses = previousX !== null && cuts.some((cut) => previousX! < cut && cut <= x);
    if (!visible || crosses) {
      if (current.length > 1) pieces.push(current);
      current = [];
    }
    if (visible) current.push([x, y]);
    previousX = x;
  }
  if (current.length > 1) pieces.push(current);
  return pieces;
}

export interface EndpointMark { x: number; y: number; closed: boolean }

/** Pencere içindeki parça uçları: kapalı uç dolu, açık uç (tanımsız) boş daire. Pencere kenarı uç sayılmaz. */
export function endpointMarks(data: GraphData): EndpointMark[] {
  const points = data.sample_points ?? [];
  const asymptotes = new Set(data.asymptotes ?? []);
  const holes = new Set((data.holes ?? []).map(([x]) => x));
  const marks: EndpointMark[] = [];
  for (const segment of data.segments ?? []) {
    for (const [x, closed] of [[segment.start, segment.start_closed], [segment.end, segment.end_closed]] as [number, boolean][]) {
      if (Math.abs(x) >= WINDOW || asymptotes.has(x) || holes.has(x)) continue;
      const nearest = points.reduce<[number, number] | null>((best, point) =>
        best === null || Math.abs(point[0] - x) < Math.abs(best[0] - x) ? point : best, null);
      if (nearest && Math.abs(nearest[0] - x) < 1e-6) marks.push({ x, y: nearest[1], closed });
      else if (nearest && !closed) marks.push({ x, y: nearest[1], closed });
    }
  }
  return marks;
}

const sx = (x: number) => 100 + x * 25;
const sy = (y: number) => 100 - y * 18;

export function GraphView({ data }: { data: GraphData }) {
  const pieces = graphPieces(data);
  if (pieces.length === 0) return <p role="note">Grafik bu soru için çizilemedi.</p>;
  const holes = data.holes ?? [];
  const asymptotes = data.asymptotes ?? [];
  const marks = endpointMarks(data);
  const described = [
    holes.length ? `delik: ${holes.map(([x]) => `x = ${x}`).join(', ')}` : '',
    asymptotes.length ? `düşey asimptot: ${asymptotes.map((x) => `x = ${x}`).join(', ')}` : '',
  ].filter(Boolean).join('; ');
  return (
    <svg className="boardGraph" viewBox="0 0 200 200" role="img"
      aria-label={`${data.expression} fonksiyon grafiği${described ? ` (${described})` : ''}`}>
      <line x1="10" y1="100" x2="190" y2="100" />
      <line x1="100" y1="10" x2="100" y2="190" />
      {asymptotes.map((x) => (
        <line key={`a${x}`} className="asymptote" x1={sx(x)} y1="10" x2={sx(x)} y2="190" strokeDasharray="4 3" />
      ))}
      {pieces.map((piece, index) => (
        <polyline key={index} points={piece.map(([x, y]) => `${sx(x)},${sy(y)}`).join(' ')} />
      ))}
      {holes.map(([x, y]) => (
        <circle key={`h${x}`} className="hole" cx={sx(x)} cy={sy(y)} r="2.5" fill="white" />
      ))}
      {marks.map((mark) => (
        <circle key={`e${mark.x}`} className={mark.closed ? 'closed' : 'open'} cx={sx(mark.x)} cy={sy(mark.y)} r="2.5"
          fill={mark.closed ? 'currentColor' : 'white'} />
      ))}
    </svg>
  );
}
