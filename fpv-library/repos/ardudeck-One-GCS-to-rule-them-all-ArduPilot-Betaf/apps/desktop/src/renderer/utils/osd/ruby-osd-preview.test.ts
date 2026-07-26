import { describe, it, expect } from 'vitest';
import { RUBY_OSD_ELEMENTS, defaultRubyOsdParams, withElementEnabled } from './ruby-osd';
import { RUBY_VECTOR_IDS, RUBY_PREVIEW_ZONE, buildRubyPreview } from './ruby-osd-preview';

describe('ruby-osd preview layout', () => {
  it('every element is either a vector or has a zone (nothing unplaced)', () => {
    for (const el of RUBY_OSD_ELEMENTS) {
      const placed = RUBY_VECTOR_IDS.has(el.id) || !!RUBY_PREVIEW_ZONE[el.id];
      expect(placed, `element ${el.id} has no preview placement`).toBe(true);
    }
  });

  it('only includes enabled elements for the given screen', () => {
    let p = defaultRubyOsdParams();
    p = withElementEnabled(p, 0, 'battery', true);
    p = withElementEnabled(p, 0, 'altitude', true);
    p = withElementEnabled(p, 1, 'throttle', true); // different screen

    const pv = buildRubyPreview(p, 0);
    const ids = pv.chips.map((c) => c.id);
    expect(ids).toContain('battery');
    expect(ids).toContain('altitude');
    expect(ids).not.toContain('throttle'); // screen 1 only
  });

  it('routes vector elements to flags, not chips', () => {
    const p = withElementEnabled(defaultRubyOsdParams(), 0, 'horizon', true);
    const pv = buildRubyPreview(p, 0);
    expect(pv.horizon).toBe(true);
    expect(pv.chips.some((c) => c.id === 'horizon')).toBe(false);
  });
});
