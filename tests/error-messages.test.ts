import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DEFAULT_ERROR_MESSAGE, ERROR_MESSAGES, errorMessage } from '../apps/web/app/lib/error-messages.js';

const OUTCOME_CODES = [
  'ai_output_truncated',
  'ai_output_filtered',
  'ai_output_incomplete',
  'ai_refused',
  'ai_invalid_output',
  'ai_timeout',
  'ai_provider_error',
];

test('her sağlayıcı sonuç kodu ayrı ve boş olmayan bir Türkçe mesaja eşlenir', () => {
  const messages = OUTCOME_CODES.map((code) => errorMessage(code));
  for (const [index, message] of messages.entries()) {
    assert.equal(message, ERROR_MESSAGES[OUTCOME_CODES[index] ?? '']);
    assert.notEqual(message, DEFAULT_ERROR_MESSAGE);
  }
  assert.equal(new Set(messages).size, OUTCOME_CODES.length);
});

test('bilinmeyen veya eksik kod varsayılan mesaja düşer', () => {
  assert.equal(errorMessage('unknown_code'), DEFAULT_ERROR_MESSAGE);
  assert.equal(errorMessage(undefined), DEFAULT_ERROR_MESSAGE);
  assert.equal(errorMessage(''), DEFAULT_ERROR_MESSAGE);
});

test('TA-005 bakım ve taşınma kodları anlaşılır mesaja eşlenir', () => {
  assert.match(errorMessage('maintenance_read_only'), /bakımda/);
  assert.match(errorMessage('service_moved'), /yeni adresine/);
});
