import assert from 'node:assert/strict';
import test from 'node:test';

import {
  backendOwnershipMatches,
  type BackendOwnership,
  type BackendProbeIdentity,
  type ExpectedBackendIdentity,
} from '../src/main/backendIdentity';

const expected: ExpectedBackendIdentity = {
  host: '127.0.0.1',
  port: 8799,
  executable: 'D:\\Argus\\argus-backend.exe',
  manifestSourceDigest: 'a'.repeat(64),
  tokenSha256: 'b'.repeat(64),
};

const ownership: BackendOwnership = {
  schema: 2,
  pid: 4242,
  host: expected.host,
  port: expected.port,
  executable: expected.executable,
  manifestSourceDigest: expected.manifestSourceDigest,
  tokenSha256: expected.tokenSha256,
  startedAt: '2026-08-09T13:00:00Z',
};

const probe: BackendProbeIdentity = {
  compatible: true,
  occupied: false,
  pid: ownership.pid,
  executable: expected.executable.toLowerCase(),
  manifestSourceDigest: expected.manifestSourceDigest,
  startedAt: ownership.startedAt,
};

test('accepts an exact owned backend identity', () => {
  assert.equal(backendOwnershipMatches(ownership, probe, expected), true);
});

test('rejects stale PID, executable, digest, or token records', () => {
  assert.equal(backendOwnershipMatches({ ...ownership, pid: 9 }, probe, expected), false);
  assert.equal(backendOwnershipMatches(ownership, { ...probe, executable: 'D:\\Other\\argus-backend.exe' }, expected), false);
  assert.equal(backendOwnershipMatches(ownership, { ...probe, manifestSourceDigest: 'c'.repeat(64) }, expected), false);
  assert.equal(backendOwnershipMatches({ ...ownership, tokenSha256: 'd'.repeat(64) }, probe, expected), false);
});

test('rejects legacy or incomplete ownership records', () => {
  assert.equal(backendOwnershipMatches({ ...ownership, schema: 1 }, probe, expected), false);
  assert.equal(backendOwnershipMatches({ ...ownership, startedAt: '' }, probe, expected), false);
  assert.equal(backendOwnershipMatches(ownership, { ...probe, startedAt: undefined }, expected), false);
  assert.equal(backendOwnershipMatches(ownership, { ...probe, startedAt: '2026-08-09T13:01:00Z' }, expected), false);
});
