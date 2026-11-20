import assert from 'node:assert/strict';
import { test } from 'node:test';
import { deletionView } from '../apps/web/app/lib/account-deletion.js';

test('silme durumu arayüz mesajına ve eyleme eşlenir', () => {
  assert.equal(deletionView('completed').kind, 'done');
  assert.equal(deletionView('in_progress').kind, 'working');
  assert.equal(deletionView('pending').kind, 'working');
  const failed = deletionView('failed', 'auth');
  assert.equal(failed.kind, 'error');
  assert.ok(failed.kind === 'error' && failed.canRetry);
  assert.match(failed.message, /oturum hesabı/);
});

test('başarısızlık hiçbir zaman başarı gibi gösterilmez', () => {
  for (const step of ['lessons', 'auth', 'completion_record', null]) {
    assert.notEqual(deletionView('failed', step).kind, 'done');
  }
  assert.notEqual(deletionView(null).kind, 'done');
  assert.equal(deletionView(null, null, 'reauthentication_required').kind, 'error');
  assert.match(deletionView(null, null, 'network_error').message, /kaldığı yerden/);
});
