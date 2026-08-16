import assert from 'node:assert/strict';
import test from 'node:test';

import {
  shouldHideWindowOnClose,
  shouldStopBackendOnQuit,
} from '../src/main/windowLifecycle';

test('native close hides the Desktop shell while Argus remains active', () => {
  assert.equal(shouldHideWindowOnClose(false), true);
  assert.equal(shouldHideWindowOnClose(true), false);
});

test('only explicit stop-and-quit stops the owned backend', () => {
  assert.equal(shouldStopBackendOnQuit(false), false);
  assert.equal(shouldStopBackendOnQuit(true), true);
});
