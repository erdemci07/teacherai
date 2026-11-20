import assert from 'node:assert/strict';
import { test } from 'node:test';
import { IdempotencyKeys, outcomeOf } from '../apps/web/app/lib/idempotency.js';

function keys() {
  let next = 0;
  return new IdempotencyKeys(() => `key-${(next += 1)}`);
}

test('sonucu bilinmeyen deneme aynı anahtarla tekrarlanır', () => {
  const store = keys();
  const first = store.keyFor('generate:analysis-1');
  store.settle('generate:analysis-1', outcomeOf('network_error'));
  assert.equal(store.keyFor('generate:analysis-1'), first);
  store.settle('generate:analysis-1', outcomeOf('request_timeout'));
  assert.equal(store.keyFor('generate:analysis-1'), first);
});

test('sunucu yanıt verdiyse sonraki deneme yeni anahtar alır', () => {
  const store = keys();
  const first = store.keyFor('generate:analysis-1');
  store.settle('generate:analysis-1', outcomeOf('ai_timeout'));
  const second = store.keyFor('generate:analysis-1');
  assert.notEqual(second, first);
  store.settle('generate:analysis-1', outcomeOf(null));
  assert.notEqual(store.keyFor('generate:analysis-1'), second);
});

test('bağımsız kullanıcı işlemleri farklı anahtar alır', () => {
  const store = keys();
  assert.notEqual(store.keyFor('generate:analysis-1'), store.keyFor('generate:analysis-2'));
  assert.notEqual(store.keyFor('analyze:file-a'), store.keyFor('generate:analysis-1'));
});
