export interface BackendProbeIdentity {
  compatible: boolean;
  occupied: boolean;
  detail?: string;
  pid?: number;
  executable?: string;
  manifestSourceDigest?: string;
  startedAt?: string;
  launchNonce?: string;
}

export interface BackendOwnership {
  schema: number;
  pid: number;
  rootPid: number;
  host: string;
  port: number;
  executable: string;
  manifestSourceDigest: string;
  tokenSha256: string;
  startedAt: string;
}

export interface ExpectedBackendIdentity {
  host: string;
  port: number;
  executable: string;
  manifestSourceDigest: string;
  tokenSha256: string;
}

export interface ExpectedBackendLaunch {
  launchNonce: string;
  manifestSourceDigest: string;
  spawnedAtMs: number;
  nowMs?: number;
}

/** Prove that a responding API came from this exact Desktop spawn attempt. */
export function backendLaunchClaimMatches(
  probe: BackendProbeIdentity,
  expected: ExpectedBackendLaunch
): boolean {
  const startedAtMs = Date.parse(probe.startedAt ?? '');
  const nowMs = expected.nowMs ?? Date.now();
  return (
    probe.compatible
    && probe.occupied === false
    && Number.isInteger(probe.pid)
    && Number(probe.pid) > 0
    && Boolean(probe.executable)
    && probe.launchNonce === expected.launchNonce
    && probe.manifestSourceDigest === expected.manifestSourceDigest
    && Number.isFinite(startedAtMs)
    // Allow a small clock/initialisation tolerance while rejecting an API that
    // predates this spawn or claims to have started in the future.
    && startedAtMs >= expected.spawnedAtMs - 5_000
    && startedAtMs <= nowMs + 5_000
  );
}

/** Strict proof that a live backend belongs to this desktop installation. */
export function backendOwnershipMatches(
  ownership: Partial<BackendOwnership>,
  probe: BackendProbeIdentity,
  expected: ExpectedBackendIdentity
): boolean {
  return (
    ownership.schema === 3
    && ownership.pid === probe.pid
    && Number.isInteger(ownership.rootPid)
    && Number(ownership.rootPid) > 0
    && ownership.host === expected.host
    && ownership.port === expected.port
    && ownership.executable?.toLowerCase() === expected.executable.toLowerCase()
    && probe.executable?.toLowerCase() === expected.executable.toLowerCase()
    && ownership.manifestSourceDigest === expected.manifestSourceDigest
    && probe.manifestSourceDigest === expected.manifestSourceDigest
    && ownership.tokenSha256 === expected.tokenSha256
    && Boolean(ownership.startedAt)
    && ownership.startedAt === probe.startedAt
  );
}
