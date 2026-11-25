import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { graphPieces, GraphView } from '../apps/web/app/solve/GraphView.js';
import { GeometryFacts, intervalText, NumberLine, numericValue } from '../apps/web/app/solve/MathBoardPrimitives.js';

test('TA-008: aralık gösterimi açık/kapalı uçları ve sonsuzluğu doğru yazar', () => {
  assert.equal(intervalText({ lower: null, upper: '-2', lower_closed: false, upper_closed: false }), '(−∞, -2)');
  assert.equal(intervalText({ lower: '-2', upper: '1', lower_closed: false, upper_closed: true }), '(-2, 1]');
  assert.equal(intervalText({ lower: '3', upper: '3', lower_closed: true, upper_closed: true }), '{3}');
  assert.equal(numericValue('3/2'), 1.5);
  assert.equal(numericValue('sqrt(2)'), null); // sayısal olmayan değer çizime konum olarak girmez
});

test('TA-008: grafik tanımsız noktada bölünür, parçalar birleştirilmez', () => {
  const data = { expression: '1/(x-1)', roots: [], y_intercept: -1, critical_points: [],
    sample_points: [[-1, -0.5], [0, -1], [0.5, -2], [1.5, 2], [2, 1]] as [number, number][], discontinuities: [1] };
  const pieces = graphPieces(data);
  assert.equal(pieces.length, 2);
  assert.deepEqual(pieces[1]?.[0], [1.5, 2]);
  const html = renderToStaticMarkup(createElement(GraphView, { data }));
  assert.equal((html.match(/<polyline/g) ?? []).length, 2);
});

test('TA-008: sayı doğrusu ve şema uyarısı erişilebilir metin taşır', () => {
  const line = renderToStaticMarkup(createElement(NumberLine, { variable: 'x', exclusions: ['-2'],
    intervals: [{ lower: '-2', upper: '1', lower_closed: false, upper_closed: true }] }));
  assert.match(line, /aria-label="Sayı doğrusu: x ∈ \(-2, 1\]"/);
  assert.match(line, /class="open"/);
  assert.match(line, /class="closed"/);
  assert.match(line, /tanımsız: -2/);
  const facts = renderToStaticMarkup(createElement(GeometryFacts, { note: 'Şekil ölçekli değildir.', schematic: true,
    facts: ['A B C (dik açı; yalnız görünüş — kullanılmadı)'] }));
  assert.match(facts, /ölçekli değil/);
  assert.doesNotMatch(facts, /<script|<svg/);
});
