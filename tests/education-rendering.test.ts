import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { EducationBoard } from '../apps/web/app/history/EducationBoard.js';
import type { LessonView } from '../apps/web/app/lib/education.generated.js';

const views: LessonView[] = JSON.parse(readFileSync('apps/api/tests/fixtures/education/synthetic.json', 'utf8'));
const render = (view: LessonView) => renderToStaticMarkup(createElement(EducationBoard, {view}));

test('on sentetik ders aynı bileşende açıklamasını ve özetini gösterir', () => {
  assert.equal(views.length, 10);
  for (const view of views) {
    const html = render(view);
    assert.ok(html.includes(view.lesson.content.takeaway));
    assert.ok(html.includes('Müfredat ve öğretim yöntemi değerlendirilmedi.'));
  }
  const find = (id: string) => render(views.find(v => v.lesson.lesson_id === id)!);
  assert.match(find('denklem'), /class="katex/);
  assert.match(find('surat'), /12 m\/s/);
  assert.match(find('tepkime'), /2H₂ \+ O₂ → 2H₂O/);
  assert.match(find('madde'), /<th scope="col">Hacim<\/th>/);
  assert.doesNotMatch(find('secilim'), /katex|<strong>Cevap/);
  assert.match(find('gozlem'), /<p>Gözlem<\/p>/);
  assert.match(find('secilim'), /bilimsel içerik henüz otomatik doğrulanmıyor/);
  assert.doesNotMatch(find('denklem'), /henüz otomatik doğrulanmıyor/);
});

test('çoktan seçmeli cevapta yalnızca seçilen şık gösterilir', () => {
  const view = structuredClone(views[0]!);
  view.lesson.content.answer = {kind: 'choice', choices: ['A) 3', 'B) 4'], selected: 1};
  const html = render(view);
  assert.match(html, /B\) 4/);
  assert.doesNotMatch(html, /A\) 3/);
});

test('desteklenmeyen görsel açıklanır ve kaynak metin güvenli biçimde gösterilir', () => {
  const view = structuredClone(views[0]!);
  view.lesson.content.blocks = [{id: 'visual', kind: 'visual', visual_type: 'unsupported', description: '<script>örnek</script>'}];
  view.panels = [{blocks:['visual']}];
  const html = render(view);
  assert.match(html, /Bu görsel türü henüz gösterilemiyor/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});
