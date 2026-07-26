/**
 * Shared types for the MAVLink signing audit log + compliance evidence pack.
 * Lives in shared/ so the main process (writer), preload (bridge) and renderer
 * (Compliance UI) all type against one definition.
 */

export type SigningAuditEvent =
  | 'key-set'
  | 'key-sent-to-fc'
  | 'signing-enabled'
  | 'signing-disabled'
  | 'key-auto-matched'
  | 'key-mismatch'
  | 'key-removed'
  | 'startup-auto-enable';

export type SigningAuditActor = 'user' | 'auto' | 'startup' | 'system';

export interface SigningAuditEntry {
  seq: number;
  id: string;
  ts: number;
  isoTime: string;
  event: SigningAuditEvent;
  actor: SigningAuditActor;
  fingerprint?: string;
  sysid?: number;
  transport?: string;
  detail: string;
  /** Hash of the previous entry (genesis = 64 zeros). */
  prevHash: string;
  /** SHA-256 over the canonical fields + prevHash. */
  hash: string;
}

export interface ChainVerification {
  ok: boolean;
  /** seq of the first entry whose recomputed hash or prevHash link fails. */
  brokenAtSeq: number | null;
  count: number;
}

export interface SecureLinkPosture {
  signingEnabled: boolean;
  hasKey: boolean;
  sentToFc: boolean;
  fcSigning: boolean;
  keyMismatch: boolean;
  activeFingerprint?: string;
  savedKeys: Array<{ fingerprint: string; label?: string; systemIds: number[] }>;
}

/** Response of MAVLINK_SIGNING_AUDIT_GET. */
export interface SigningAuditSnapshot {
  entries: SigningAuditEntry[];
  chain: ChainVerification;
  posture: SecureLinkPosture;
}
