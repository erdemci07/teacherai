import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { choiceMismatchNotice, questionState } from '../apps/web/app/lib/clarification.js';
import type { IntegrityReport, SourceUncertainty } from '../apps/web/app/lib/education.generated.js';
import { ClarificationPanel } from '../apps/web/app/solve/ClarificationPanel.js';

function report(decision: IntegrityReport['decision'], recovery: IntegrityReport['recovery'], uncertainties: SourceUncertainty[] = []): IntegrityReport {
  return {
    schema_version: '1.0.0', revision: 1, revision_origin: 'vision', decision, recovery, subject: 'mathematics',
    subject_origin: 'canonical_label', intent: { kind: 'find_variable', choice_dependent: false, answer_strategy: 'open' },
    uncertainties, rechecks_used: 1, recheck_limit: 1,
  };
}

const radical: SourceUncertainty = {
  id: 'u1', category: 'radical_scope', element: 'expression:0', recognized: '\\sqrt{5}+9', impact: 'material',
  resolution: 'unresolved', origin: 'vision', alternatives: [{ id: 'u1_r_1', text: '\\sqrt{5+9}', latex: '\\sqrt{5+9}', origin: 'vision_recheck' }],
};

test('hazır ve önemsiz belirsizlikli sorular öğrenciye soru sormadan ilerler', () => {
  assert.equal(questionState(undefined).kind, 'proceed');
  assert.equal(questionState(report('ready', 'none')).kind, 'proceed');
  assert.equal(questionState(report('ready_with_noncritical_uncertainty', 'none')).kind, 'proceed');
});

test('kritik belirsizlik için hedefli soru ve ilk okuma dahil seçenekler gösterilir', () => {
  const state = questionState(report('clarification_required', 'choose_alternative', [radical]));
  assert.equal(state.kind, 'clarify');
  assert.ok(state.kind === 'clarify' && state.prompt.startsWith('Kök işaretinin nerede bittiğini'));
  assert.deepEqual(state.kind === 'clarify' && state.options.map(option => option.id), ['recognized', 'u1_r_1']);
  const html = renderToStaticMarkup(createElement(ClarificationPanel, { state: state as Exclude<typeof state, { kind: 'proceed' }>, pending: false, onSelect: () => {}, onRetake: () => {}, onReplace: () => {} }));
  assert.match(html, /<legend>Kök işaretinin/);
  assert.match(html, /class="katex/);
  assert.match(html, /Hiçbiri doğru değil/);
  assert.doesNotMatch(html, /AST|OCR|integrity|uncertainty/i);
});

test('seçeneği olmayan veya kaynak seçimi gereken durum yeniden çekim ister', () => {
  assert.equal(questionState(report('retake_required', 'retake')).kind, 'retake');
  const crop = questionState(report('clarification_required', 'crop'));
  assert.ok(crop.kind === 'crop' && /birden fazla soru/.test(crop.message));
  assert.equal(questionState(report('unsupported_subject', 'none')).kind, 'unsupported');
});

test('seçenek metni güvenli biçimde gösterilir ve uyuşmazlık açıkça bildirilir', () => {
  const unsafe = { ...radical, recognized: '<img src=x onerror=alert(1)>', alternatives: [{ id: 'a', text: '<script>x</script>', origin: 'vision' as const }] };
  const state = questionState(report('clarification_required', 'choose_alternative', [unsafe]));
  const html = renderToStaticMarkup(createElement(ClarificationPanel, { state: state as Exclude<typeof state, { kind: 'proceed' }>, pending: true, onSelect: () => {}, onRetake: () => {}, onReplace: () => {} }));
  assert.doesNotMatch(html, /<script>|<img/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /<fieldset disabled="">/);
  assert.match(choiceMismatchNotice('no_match') ?? '', /seçeneklerin hiçbiriyle uyuşmadı/);
  assert.equal(choiceMismatchNotice('matched'), null);
});
