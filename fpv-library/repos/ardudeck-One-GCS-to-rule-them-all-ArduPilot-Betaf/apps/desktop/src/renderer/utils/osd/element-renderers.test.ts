import { describe, it, expect, afterEach } from 'vitest';
import { renderElement, DEFAULT_DEMO_VALUES } from './element-renderers';
import { OsdScreenBuffer } from './font-renderer';
import {
  registerModuleOsdElement,
  unregisterModuleOsdElements,
} from '../../modules/module-osd-registry';

const SLUG = 'test.osd.module';

afterEach(() => {
  unregisterModuleOsdElements(SLUG);
});

describe('renderElement module fallback', () => {
  it('renders a module-contributed element via the registry fallback', () => {
    registerModuleOsdElement(SLUG, {
      id: 'test.osd.hello',
      name: 'Hello',
      category: 'general',
      size: { width: 5, height: 1 },
      render(buffer, x, y) {
        buffer.drawString(x, y, 'HELLO');
      },
    });

    const buffer = new OsdScreenBuffer('PAL');
    renderElement(buffer, 'test.osd.hello', 2, 3, DEFAULT_DEMO_VALUES);

    const codes = 'HELLO'.split('').map((_, i) => buffer.getChar(2 + i, 3));
    expect(codes).toEqual('HELLO'.split('').map((c) => c.charCodeAt(0)));
  });

  it('ignores an unknown id that is neither built-in nor a module element', () => {
    const buffer = new OsdScreenBuffer('PAL');
    // Should not throw; the cell stays blank (space = 0x20).
    expect(() => renderElement(buffer, 'no.such.element', 0, 0, DEFAULT_DEMO_VALUES)).not.toThrow();
    expect(buffer.getChar(0, 0)).toBe(0x20);
  });

  it('still renders a built-in element unchanged', () => {
    const buffer = new OsdScreenBuffer('PAL');
    renderElement(buffer, 'battery_voltage', 1, 0, DEFAULT_DEMO_VALUES);
    // First cell of battery_voltage is the BATT symbol; must be non-blank.
    expect(buffer.getChar(1, 0)).not.toBe(0x20);
  });
});
