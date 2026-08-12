export interface BackendProbeIdentity {
  compatible: boolean;
  occupied: boolean;
  detail?: string;
  pid?: number;
  executable?: string;
  manifestSourceDigest?: string;
  startedAt?: string;
}

export interface BackendOwnership {
  schema: number;
  pid: number;
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

/** Strict proof that a live backend belongs to this desktop installation. */
export function backendOwnershipMatches(
  ownership: Partial<BackendOwnership>,
  probe: BackendProbeIdentity,
  expected: ExpectedBackendIdentity
): boolean {
  return (
    ownership.schema === 2
    && ownership.pid === probe.pid
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
