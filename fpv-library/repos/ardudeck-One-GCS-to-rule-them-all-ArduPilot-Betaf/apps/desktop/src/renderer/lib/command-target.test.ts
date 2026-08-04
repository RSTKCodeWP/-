import { describe, it, expect } from 'vitest';
import { isFleetCommandTarget } from './command-target';

describe('isFleetCommandTarget', () => {
  it('is false with nothing active', () => {
    expect(isFleetCommandTarget(null, 0, false)).toBe(false);
    expect(isFleetCommandTarget(null, 3, true)).toBe(false);
  });

  it('is true for a swarm even though the first drone IS the primary link', () => {
    // The regression: right-click used to be dead here, because the old predicate
    // required the primary connection to be down.
    expect(isFleetCommandTarget('t1:2:1', 3, true)).toBe(true);
  });

  it('is true for an orchestrator-only fleet with no primary link', () => {
    expect(isFleetCommandTarget('t1:1:1', 1, false)).toBe(true);
    expect(isFleetCommandTarget('t1:1:1', 4, false)).toBe(true);
  });

  it('leaves single-vehicle mode on the explicit click-the-marker gesture', () => {
    // One vehicle on a live primary link: selection stays the map's own marker click,
    // so a stray right-click on the map cannot command an unselected vehicle.
    expect(isFleetCommandTarget('t1:1:1', 1, true)).toBe(false);
  });
});
