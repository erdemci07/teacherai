import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { EducationBoard, stepOutcome } from '../apps/web/app/history/EducationBoard.js';
import type { BlockCheck, LessonView } from '../apps/web/app/lib/education.generated.js';

// Sunucunun gerçek v2 projeksiyonundan üretilir: python -m scripts.science_matrix --write-fixture
const views: LessonView[] = JSON.parse(readFileSync('apps/api/tests/fixtures/education/reasoning_v2.json', 'utf8'));
const render = (view: LessonView) => renderToStaticMarkup(createElement(EducationBoard, {view}));
const find = (id: string) => views.find(view => view.lesson.lesson_id === id)!;

test('2.2.0 adımları sunucu kontrolüne göre etiketlenir; kontrolsüz adım geçmiş gösterilmez', () => {
  const html = render(find('hedef_dogrulandi'));
  assert.equal(find('hedef_dogrulandi').lesson.schema.version, '2.2.0');
  assert.match(html, /data-step-check="passed"[^>]*>Bu adım matematik motoruyla kontrol edildi/);
  assert.match(html, /data-step-check="not_checked"[^>]*>Bu adım otomatik kontrol edilmedi/);
  assert.match(html, /data-target-check="passed"[^>]*>Sorunun istediği sonuç bağımsız olarak hesaplandı/);
});

test('desteklenmeyen hedef ve adım başarılı gibi gösterilmez', () => {
  const html = render(find('hedef_desteklenmiyor'));
  assert.doesNotMatch(html, /data-step-check="passed"/);
  assert.doesNotMatch(html, /data-target-check="passed"/);
  assert.match(html, /Sorunun istediği sonuç otomatik doğrulanamadı/);
  assert.match(html, /Bu hesap için otomatik doğrulama yok/);
});

test('adım durumunda çelişki önceliklidir ve kısmi kontrol tam sayılmaz', () => {
  const check = (target: string, outcome: BlockCheck['outcome']): BlockCheck =>
    ({id: `c_${target}_${outcome}`, scope: 'block', target, dimension: 'transformation', verifier: 'mathai', outcome, reason: 'r'});
  assert.equal(stepOutcome([check('s', 'passed'), check('s_0', 'failed')], ['s', 's_0']), 'failed');
  assert.equal(stepOutcome([check('s', 'passed'), check('s_0', 'partially_checked')], ['s', 's_0']), 'partially_checked');
  assert.equal(stepOutcome([check('s', 'unsupported')], ['s']), 'unsupported');
  assert.equal(stepOutcome([check('other', 'passed')], ['s']), 'not_checked');
  assert.equal(stepOutcome([{...check('s', 'passed'), scope: 'lesson', target: null}], ['s']), 'not_checked');
});

test('anlatım ve adım metni betik olarak yorumlanmaz', () => {
  const view = structuredClone(find('hedef_dogrulandi'));
  const step = view.lesson.content.blocks.find(block => block.kind === 'derivation_step')!;
  if (step.kind === 'derivation_step') step.explanation = '<img src=x onerror=alert(1)>';
  const html = render(view);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(html, /<img src=x/);
});

test('TA-005 yöntem ve müfredat rozetleri yalnızca sunucu kaydı sonucunu gösterir', () => {
  const plain = render(find('hedef_dogrulandi'));
  assert.match(plain, /Müfredat ve öğretim yöntemi değerlendirilmedi/);
  assert.doesNotMatch(plain, /data-policy-check/);
  const view = structuredClone(find('hedef_dogrulandi'));
  const step = view.lesson.content.blocks.find(block => block.kind === 'derivation_step')!;
  view.lesson.verification.method = 'failed';
  view.lesson.verification.curriculum = 'passed';
  view.lesson.verification.block_checks = [...(view.lesson.verification.block_checks ?? []), {id: 'registry:method', scope: 'block', target: step.id, mapping: 'mapped',
    dimension: 'method', verifier: 'registry', outcome: 'failed', reason: 'forbidden_operation', evidence: []}];
  const html = render(view);
  assert.match(html, /data-policy-check="method" data-state="failed"[^>]*>Yöntem: bu sınıf düzeyine uygun yöntem doğrulanamadı/);
  assert.match(html, /data-policy-check="curriculum" data-state="passed"[^>]*>Müfredat: konu kaynaklı bir kazanıma eşlendi/);
  assert.doesNotMatch(html, /Bu adımda bir çelişki bulundu/);  // yöntem uygunsuzluğu hesap çelişkisi değildir
});
