import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { EducationalProvenance } from '../apps/web/app/lib/education.generated.js';
import { ProvenanceDetails } from '../apps/web/app/history/EducationBoard.js';
import { examFromGoal, examGoals, knowledgeNote } from '../apps/web/app/lib/learning.js';
import { isTopicContext, parseTopicContext, readTopicContext, saveTopicContext } from '../apps/web/app/lib/topic-context.js';
import { ExpandableBoard, nextFocus } from '../apps/web/app/solve/LearningWorkspace.js';

test('TA-007: Türkçe ekli sınav hedefleri ve çoklu hedef kaybolmaz', () => {
  assert.deepEqual(examGoals("LGS'ye hazırlanıyorum"), ['LGS']);
  assert.deepEqual(examGoals('TYT ve AYT'), ['TYT', 'AYT']);
  assert.deepEqual(examGoals("YKS'ye çalışıyorum"), ['TYT', 'AYT']);
  assert.deepEqual(examGoals('Sınava hazırlanıyorum'), []);
  assert.equal(examFromGoal("LGS'ye"), 'LGS');
  assert.equal(examFromGoal('YKS'), null);
});

test('TA-007: onaylı bilgi taslak olarak etiketlenmez', () => {
  assert.match(knowledgeNote({ knowledge_drafts: 0, knowledge_approved: 2 }), /2 bilimsel bilgi girdisi öğretmen onaylıdır/);
  assert.doesNotMatch(knowledgeNote({ knowledge_drafts: 0, knowledge_approved: 2 }), /taslak/);
  assert.match(knowledgeNote({ knowledge_drafts: 3 }), /3 bilimsel bilgi taslağı/);
  assert.equal(knowledgeNote({ knowledge_drafts: 0 }), '');
});

test('TA-007: konu bağlamı doğrulanarak saklanır; bozuk değer yok sayılır', () => {
  const memory = new Map<string, string>();
  const store = { getItem: (k: string) => memory.get(k) ?? null, setItem: (k: string, v: string) => { memory.set(k, v); },
    removeItem: (k: string) => { memory.delete(k); } };
  const context = { programId: 'meb-2018.matematik.1-8', programLabel: 'Matematik', grade: 8, topicId: 't1', code: 'M.8.2.2', title: 'Doğrusal Denklemler' };
  saveTopicContext(context, store);
  assert.deepEqual(readTopicContext(store), context);
  assert.equal(parseTopicContext('{"grade": 99}'), null);
  assert.equal(parseTopicContext('bozuk'), null);
  assert.equal(isTopicContext({ ...context, grade: 8.5 }), false);
});

test('TA-007: büyütülmüş tahtada odak döngüsü sınırlarda başa/sona döner', () => {
  const [a, b, c] = [{}, {}, {}] as HTMLElement[];
  assert.equal(nextFocus([a!, b!, c!], c!, false), a);
  assert.equal(nextFocus([a!, b!, c!], a!, true), c);
  assert.equal(nextFocus([a!, b!, c!], b!, false), null);
  assert.equal(nextFocus([], null, false), null);
  const html = renderToStaticMarkup(createElement(ExpandableBoard, { initiallyExpanded: true, children: 'Tahta' }));
  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-modal="true"/);
});

test('TA-007: köken bilgisi aşamalı gösterilir ve onay uydurulmaz', () => {
  const provenance = {
    curriculum_version: '2.0.0+x', knowledge_version: '1.0.0+y', match: 'topic_key', excluded_draft_knowledge: 4,
    payload_bytes: 500, included_in_prompt: true, topic_mapping: 'structural', transmission: 'emergency',
    knowledge_ids: ['math.equation-equivalence'], transmitted_knowledge_ids: [], method_policy_ids: [],
    resolution: { status: 'resolved', subject: 'mathematics', academic_year: '2026-2027', academic_year_origin: 'server_clock',
      grade: 8, program_ids: ['meb-2018.matematik.1-8'] },
  } as unknown as EducationalProvenance;
  const html = renderToStaticMarkup(createElement(ProvenanceDetails, { provenance }));
  assert.match(html, /<details/);
  assert.match(html, /meb-2018\.matematik\.1-8/);
  assert.match(html, /onaylı bilimsel bilgi girdisi kullanılmadı/);  // seçilen ama gönderilmeyen girdi "kullanıldı" sayılmaz
  assert.match(html, /Onaylı yöntem politikası yok/);
  assert.match(html, /gönderilmedi/);
});
