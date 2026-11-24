import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { CurriculumResolution, ModeSupport } from '../apps/web/app/lib/education.generated.js';
import { NAV_ITEMS, examFromGoal, isCurrent, resolutionMessage, subjectActions } from '../apps/web/app/lib/learning.js';
import { ExpandableBoard, LearningWorkspace } from '../apps/web/app/solve/LearningWorkspace.js';

const mode = (value: Partial<ModeSupport> & Pick<ModeSupport, 'mode'>): ModeSupport =>
  ({ subject: 'mathematics', available: false, reason: 'planned', ...value });

test('gezinme yalnız çalışan ekranları içerir ve geçerli sayfayı doğru işaretler', () => {
  assert.deepEqual(NAV_ITEMS.map((item) => item.href), ['/', '/konular', '/solve', '/history', '/dashboard']);
  assert.ok(isCurrent('/', '/') && !isCurrent('/konular', '/'));
  assert.ok(isCurrent('/history/', '/history') && !isCurrent('/historyx', '/history'));
});

test('FKB alanında soru çözümü işlevsel gösterilmez; konu anlatımı planlı fazı söyler', () => {
  const physics = subjectActions([
    mode({ subject: 'physics', mode: 'question_solving', reason: 'subject_generation_unavailable', planned_phase: 'TA-009–TA-011' }),
    mode({ subject: 'physics', mode: 'topic_explanation', planned_phase: 'TA-013' }),
  ]);
  assert.equal(physics[0]?.disabled, true);
  assert.equal(physics[0]?.href, undefined);
  assert.match(physics[0]?.note ?? '', /TA-009/);
  assert.match(physics[1]?.note ?? '', /TA-013/);
  const maths = subjectActions([mode({ mode: 'question_solving', available: true, reason: 'available' }), mode({ mode: 'topic_explanation', planned_phase: 'TA-013' })]);
  assert.equal(maths[0]?.href, '/solve');
  assert.equal(maths[1]?.disabled, true);
});

test('çözümleme mesajı belirsizliği ve mezun durumunu açıkça söyler', () => {
  const base: CurriculumResolution = { status: 'ambiguous', subject: 'mathematics', academic_year: '2026-2027',
    academic_year_origin: 'declared', learner_status: 'graduate', exam: 'AYT', reasons: ['graduate_exam_scope', 'exam_scope_unverified'] };
  const message = resolutionMessage(base);
  assert.equal(message.tone, 'warn');
  assert.match(message.text, /12\. sınıf öğrencisi sayılmaz/);
  assert.match(message.text, /doğrulanmadı/);
  assert.equal(resolutionMessage({ ...base, status: 'resolved', program_ids: ['meb-2018.matematik.1-8'], reasons: ['by_exclusion'] }).tone, 'ok');
  assert.match(resolutionMessage({ ...base, status: 'unresolved', reasons: ['grade_unknown'] }).text, /tahmin edilmez/);
});

test('sınav hedefi yalnız tek ve açık sınav adıyla eşlenir', () => {
  assert.equal(examFromGoal('LGS'), 'LGS');
  assert.equal(examFromGoal('ayt matematik'), 'AYT');
  assert.equal(examFromGoal('YKS'), null);
  assert.equal(examFromGoal('TYT ve AYT'), null);
  assert.equal(examFromGoal(null), null);
});

test('tahta aynı içerikle büyür; büyütme düğmesi erişilebilir ve yeni istek yapmaz', () => {
  const closed = renderToStaticMarkup(createElement(ExpandableBoard, { children: createElement('p', null, 'x = 4') }));
  assert.match(closed, /aria-expanded="false"/);
  assert.match(closed, /Tahtayı büyüt/);
  assert.doesNotMatch(closed, /role="dialog"/);
  const open = renderToStaticMarkup(createElement(ExpandableBoard, { initiallyExpanded: true, children: createElement('p', null, 'x = 4') }));
  assert.match(open, /data-expanded="true"/);
  assert.match(open, /role="dialog"/);
  assert.match(open, /x = 4/);
  const workspace = renderToStaticMarkup(createElement(LearningWorkspace, { board: createElement('p', null, 'tahta'), children: createElement('p', null, 'yan') }));
  assert.match(workspace, /data-layout="split"/);
  const source = readFileSync('apps/web/app/solve/LearningWorkspace.tsx', 'utf8');
  assert.doesNotMatch(source, /fetch\(|generate|requestHeaders/);
});

test('tasarım sistemi güvenli alan, dinamik yükseklik ve dokunma hedeflerini tanımlar', () => {
  const css = readFileSync('apps/web/app/design-system.css', 'utf8');
  for (const token of ['env(safe-area-inset-bottom', '100dvh', '--ta-touch: 44px', 'prefers-reduced-motion', 'orientation: landscape'])
    assert.ok(css.includes(token), token);
  assert.doesNotMatch(css, /:hover/);
  assert.ok(css.includes(':root[data-theme="dark"]'));
  const layout = readFileSync('apps/web/app/layout.tsx', 'utf8');
  assert.match(layout, /viewportFit: 'cover'/);
  assert.doesNotMatch(layout, /userScalable: false|maximumScale: 1/);
});
