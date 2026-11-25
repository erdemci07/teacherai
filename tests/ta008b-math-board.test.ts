import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { endpointMarks, graphPieces, GraphView } from '../apps/web/app/solve/GraphView.js';
import type { GraphData } from '../apps/web/app/lib/math-board.ts';

const base = { roots: [], y_intercept: null, critical_points: [] };

test('TA-008B: kaldırılabilir süreksizlik açık daire, grafik delikte birleşmez', () => {
  const data: GraphData = { ...base, expression: '(x^2-1)/(x-1)',
    sample_points: [[-1, 0], [0, 1], [0.5, 1.5], [1.5, 2.5], [2, 3]],
    segments: [{ start: -10, end: 1, start_closed: true, end_closed: false }, { start: 1, end: 10, start_closed: false, end_closed: true }],
    holes: [[1, 2]], asymptotes: [], discontinuities: [1] };
  assert.equal(graphPieces(data).length, 2);
  const html = renderToStaticMarkup(createElement(GraphView, { data }));
  assert.match(html, /class="hole"/);
  assert.doesNotMatch(html, /class="asymptote"/);
  assert.match(html, /delik: x = 1/);
});

test('TA-008B: asimptot kesikli çizgi; çok büyük değer dikey birleştirme çizgisi oluşturmaz', () => {
  const data: GraphData = { ...base, expression: '1/x',
    sample_points: [[-1, -1], [-0.001, -1000], [0.001, 1000], [1, 1], [2, 0.5]],
    segments: [{ start: -10, end: 0, start_closed: true, end_closed: false }, { start: 0, end: 10, start_closed: false, end_closed: true }],
    holes: [], asymptotes: [0], discontinuities: [0] };
  const pieces = graphPieces(data);
  assert.ok(pieces.every((piece) => piece.every(([, y]) => Math.abs(y) <= 50)));
  const html = renderToStaticMarkup(createElement(GraphView, { data }));
  assert.match(html, /class="asymptote"/);
  assert.match(html, /düşey asimptot: x = 0/);
  assert.equal(endpointMarks(data).length, 0); // asimptot ucu nokta olarak işaretlenmez
});

test('TA-008B: √x tanım kümesi ucu kapalı (dolu) gösterilir; pencere kenarı uç sayılmaz', () => {
  const data: GraphData = { ...base, expression: 'sqrt(x)',
    sample_points: [[0, 0], [1, 1], [4, 2], [9, 3], [10, 3.162]],
    segments: [{ start: 0, end: 10, start_closed: true, end_closed: true }], holes: [], asymptotes: [] };
  const marks = endpointMarks(data);
  assert.deepEqual(marks, [{ x: 0, y: 0, closed: true }]);
  assert.match(renderToStaticMarkup(createElement(GraphView, { data })), /class="closed"/);
});
