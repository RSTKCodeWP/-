import { describe, it, expect, beforeEach } from 'vitest';
import { inspectorState, updateInspector, appendConsole } from './inspectorStore.svelte';

beforeEach(() => {
  inspectorState.messages = [];
  inspectorState.paused = false;
  inspectorState.enabled = false;
  inspectorState.consoleLines = [];
  inspectorState.consoleInput = '';
});

describe('updateInspector', () => {
  it('updates messages when not paused', () => {
    const msgs = [{ id: 0, name: 'HEARTBEAT', hz: 1, count: 10, size: 9, last_fields: {} }];
    updateInspector(msgs);
    expect(inspectorState.messages.length).toBe(1);
    expect(inspectorState.messages[0].name).toBe('HEARTBEAT');
  });

  it('does not update when paused', () => {
    updateInspector([{ id: 0, name: 'A', hz: 1, count: 1, size: 1, last_fields: {} }]);
    inspectorState.paused = true;
    updateInspector([{ id: 1, name: 'B', hz: 2, count: 2, size: 2, last_fields: {} }]);
    expect(inspectorState.messages[0].name).toBe('A');
  });

  it('replaces entire messages array', () => {
    updateInspector([
      { id: 0, name: 'A', hz: 1, count: 1, size: 1, last_fields: {} },
      { id: 1, name: 'B', hz: 2, count: 2, size: 2, last_fields: {} },
    ]);
    expect(inspectorState.messages.length).toBe(2);
    updateInspector([{ id: 2, name: 'C', hz: 3, count: 3, size: 3, last_fields: {} }]);
    expect(inspectorState.messages.length).toBe(1);
    expect(inspectorState.messages[0].name).toBe('C');
  });

  it('accepts empty array', () => {
    updateInspector([{ id: 0, name: 'A', hz: 1, count: 1, size: 1, last_fields: {} }]);
    updateInspector([]);
    expect(inspectorState.messages.length).toBe(0);
  });

  it('preserves last_fields data', () => {
    updateInspector([
      {
        id: 0,
        name: 'ATTITUDE',
        hz: 10,
        count: 100,
        size: 28,
        last_fields: { roll: 0.1, pitch: -0.2, yaw: 3.14 },
      },
    ]);
    expect(inspectorState.messages[0].last_fields).toEqual({ roll: 0.1, pitch: -0.2, yaw: 3.14 });
  });
});

describe('appendConsole', () => {
  it('appends lines', () => {
    appendConsole('line1\nline2\n');
    expect(inspectorState.consoleLines).toContain('line1');
    expect(inspectorState.consoleLines).toContain('line2');
  });

  it('trims to 500 when over 1000', () => {
    for (let i = 0; i < 1001; i++) {
      inspectorState.consoleLines.push(`line${i}`);
    }
    appendConsole('overflow');
    expect(inspectorState.consoleLines.length).toBeLessThanOrEqual(502);
  });

  it('skips empty lines', () => {
    appendConsole('\n\n\n');
    expect(inspectorState.consoleLines.length).toBe(0);
  });

  it('handles single line without newline', () => {
    appendConsole('hello');
    expect(inspectorState.consoleLines.length).toBe(1);
    expect(inspectorState.consoleLines[0]).toBe('hello');
  });

  it('handles multiple appends accumulating lines', () => {
    appendConsole('first');
    appendConsole('second');
    appendConsole('third');
    expect(inspectorState.consoleLines.length).toBe(3);
    expect(inspectorState.consoleLines).toEqual(['first', 'second', 'third']);
  });

  it('preserves lines under 1000 threshold', () => {
    for (let i = 0; i < 999; i++) {
      inspectorState.consoleLines.push(`line${i}`);
    }
    appendConsole('still-under');
    expect(inspectorState.consoleLines.length).toBe(1000);
    expect(inspectorState.consoleLines[999]).toBe('still-under');
  });
});

describe('inspectorState direct properties', () => {
  it('consoleInput defaults to empty string', () => {
    expect(inspectorState.consoleInput).toBe('');
  });

  it('enabled defaults to false', () => {
    expect(inspectorState.enabled).toBe(false);
  });

  it('can toggle enabled state', () => {
    inspectorState.enabled = true;
    expect(inspectorState.enabled).toBe(true);
    inspectorState.enabled = false;
    expect(inspectorState.enabled).toBe(false);
  });
});
