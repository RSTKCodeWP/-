/**
 * Pure hash-chain logic for the signing audit log. No electron / electron-store
 * dependency, so it is unit-testable in isolation. The persistence + IPC layer
 * lives in signing-audit.ts and builds on these primitives.
 */
import { createHash } from 'node:crypto';
import type { SigningAuditEntry, ChainVerification } from '../../shared/signing-audit-types.js';

export const GENESIS = '0'.repeat(64);

/** Stable string used as the hash input for an entry (excludes the hash itself). */
export function canonicalEntry(e: Omit<SigningAuditEntry, 'hash'>): string {
  return [
    e.seq,
    e.ts,
    e.event,
    e.actor,
    e.fingerprint ?? '',
    e.sysid ?? '',
    e.transport ?? '',
    e.detail,
    e.prevHash,
  ].join('|');
}

export function hashEntry(e: Omit<SigningAuditEntry, 'hash'>): string {
  return createHash('sha256').update(canonicalEntry(e)).digest('hex');
}

/** Re-walk the chain and confirm every prevHash link and recomputed hash. */
export function verifyAuditChain(entries: SigningAuditEntry[]): ChainVerification {
  let prevHash = entries.length > 0 ? entries[0]!.prevHash : GENESIS;
  for (const e of entries) {
    const { hash, ...base } = e;
    if (e.prevHash !== prevHash) {
      return { ok: false, brokenAtSeq: e.seq, count: entries.length };
    }
    if (hashEntry(base) !== hash) {
      return { ok: false, brokenAtSeq: e.seq, count: entries.length };
    }
    prevHash = e.hash;
  }
  return { ok: true, brokenAtSeq: null, count: entries.length };
}
