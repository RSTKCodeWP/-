import { describe, it, expect } from 'vitest';
import { GENESIS, hashEntry, verifyAuditChain } from './signing-audit-chain';
import type { SigningAuditEntry } from '../../shared/signing-audit-types';

/** Build a valid chained entry from the previous one (mirrors recordSigningEvent). */
function chained(seq: number, prev: SigningAuditEntry | null, detail: string): SigningAuditEntry {
  const prevHash = prev ? prev.hash : GENESIS;
  const ts = 1_700_000_000_000 + seq * 1000;
  const base: Omit<SigningAuditEntry, 'hash'> = {
    seq,
    id: `id-${seq}`,
    ts,
    isoTime: new Date(ts).toISOString(),
    event: 'signing-enabled',
    actor: 'user',
    detail,
    prevHash,
  };
  return { ...base, hash: hashEntry(base) };
}

describe('verifyAuditChain', () => {
  it('verifies an intact chain', () => {
    const e1 = chained(1, null, 'first');
    const e2 = chained(2, e1, 'second');
    const e3 = chained(3, e2, 'third');
    expect(verifyAuditChain([e1, e2, e3])).toEqual({ ok: true, brokenAtSeq: null, count: 3 });
  });

  it('verifies an empty chain', () => {
    expect(verifyAuditChain([])).toEqual({ ok: true, brokenAtSeq: null, count: 0 });
  });

  it('detects an in-place edit of a field', () => {
    const e1 = chained(1, null, 'first');
    const e2 = chained(2, e1, 'second');
    // Tamper: change the detail but keep the now-stale hash.
    const tampered = { ...e2, detail: 'EDITED' };
    const v = verifyAuditChain([e1, tampered]);
    expect(v.ok).toBe(false);
    expect(v.brokenAtSeq).toBe(2);
  });

  it('detects a deleted entry (broken prevHash link)', () => {
    const e1 = chained(1, null, 'first');
    const e2 = chained(2, e1, 'second');
    const e3 = chained(3, e2, 'third');
    // Drop e2: e3.prevHash no longer matches e1.hash.
    const v = verifyAuditChain([e1, e3]);
    expect(v.ok).toBe(false);
    expect(v.brokenAtSeq).toBe(3);
  });

  it('detects a re-hashed forgery that forgets to relink downstream', () => {
    const e1 = chained(1, null, 'first');
    const e2 = chained(2, e1, 'second');
    // Forge e1 fully (recompute its own hash) but leave e2 pointing at the old hash.
    const forgedBase = { ...e1, detail: 'FORGED' };
    const forged = { ...forgedBase, hash: hashEntry(forgedBase) };
    const v = verifyAuditChain([forged, e2]);
    expect(v.ok).toBe(false);
    expect(v.brokenAtSeq).toBe(2); // e2's prevHash links to the original e1.hash
  });
});
